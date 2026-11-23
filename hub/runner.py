import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .db.archive import add_report, append_event, create_run, find_session_id, finish_run, get_run
from .db.ownership import AGENTS, OWNERSHIP
from .policies import get_policy, load_policies
from .prompt import build_followup_prompt, build_prompt
from .report import DELEGATE_TOOLS, HANDBACK_TOOLS, clean_report, result_text
from .session import build_session_args, load_shared_server, write_mcp_config
from .tool_names import SHARED_READ_TOOLS, qualified_tools_for

ORCHESTRATOR = "dann-of-thursday"
WINDOWS = os.name == "nt"


def now_ms():
    return int(time.time() * 1000)


def resolve_tools(agents_dir, orchestrated, enable_active, authorization, policy):
    """Decide the built-in toolset for a run (mirrors agents/*.policy.json)."""
    tools_cfg = policy.get("tools") or {}
    if orchestrated:
        # Union of every agent's passive toolset, plus Agent to delegate.
        passive = ["Agent"]
        for p in load_policies(agents_dir):
            for t in (p.get("tools") or {}).get("default_safe") or []:
                if t not in passive:
                    passive.append(t)
        return passive, False
    active = tools_cfg.get("authorized_active")
    if enable_active and authorization.strip() and isinstance(active, list) and active:
        return active, True
    return tools_cfg.get("default_safe") or ["Read"], False


def resolve_command(cmd):
    """`claude` may be a .cmd/.exe shim on Windows; resolve the first element to a real path."""
    cmd = [cmd] if isinstance(cmd, (str, Path)) else list(cmd)
    exe = shutil.which(str(cmd[0])) or str(cmd[0])
    return [exe, *map(str, cmd[1:])]


FRONTMATTER = re.compile(r"\A---\r?\n([\s\S]*?)^---\r?$", re.M)


def preloaded_skills(repo_root, agent):
    """
    Bodies of the skills listed under `skills:` in .claude/agents/<agent>.md,
    each read from .claude/skills/<name>/SKILL.md (frontmatter stripped).
    A missing definition or skill is skipped with a warning, never fatal.
    """
    try:
        md = (repo_root / ".claude" / "agents" / f"{agent}.md").read_text(encoding="utf8")
    except OSError:
        return []
    fm = FRONTMATTER.match(md)
    block = re.search(r"^skills:[ \t]*\r?\n((?:[ \t]+-[ \t]*.+\r?\n?)+)", fm.group(1), re.M) if fm else None
    names = re.findall(r"-[ \t]*([\w.-]+)", block.group(1)) if block else []
    bodies = []
    for name in names:
        try:
            skill = (repo_root / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf8")
        except OSError as err:
            print(f"[skills] {agent}: {err}", file=sys.stderr)
            continue
        bodies.append(f"# Skill: {name}\n\n{FRONTMATTER.sub('', skill, count=1).strip()}")
    return bodies


class Run:
    def __init__(self, **fields):
        self.__dict__.update(fields)
        self.status = "running"
        self.events = []
        self.listeners = set()
        self.lock = threading.Lock()
        self.proc = None
        self.result = None
        self.session_id = None

    def subscribe(self):
        """Buffered events so far plus a queue for the rest; None on the queue means done."""
        q = queue.Queue()
        with self.lock:
            backlog = list(self.events)
            if not self.finished:
                self.listeners.add(q)
            else:
                q.put(None)
        return backlog, q

    def unsubscribe(self, q):
        with self.lock:
            self.listeners.discard(q)

    def emit(self, evt):
        with self.lock:
            self.events.append(evt)
            for q in self.listeners:
                q.put(evt)

    def close(self):
        with self.lock:
            self.finished = True
            for q in self.listeners:
                q.put(None)
            self.listeners.clear()

    def public(self):
        return {
            "id": self.id,
            "agent": self.agent,
            "status": self.status,
            "tools": self.tools,
            "activeEngaged": self.activeEngaged,
            "parentRunId": self.parentRunId,
        }


class Runner:
    """
    Spawns claude runs, streams their events to listeners, and archives every
    run, event, and report. Archive failures surface as "warn" events and never
    stop a run.
    """

    def __init__(self, db, db_file, data_dir, claude_cmd, repo_root):
        self.db = db
        self.db_file = db_file
        self.data_dir = Path(data_dir)
        self.claude_cmd = claude_cmd
        self.repo_root = Path(repo_root)
        self.agents_dir = self.repo_root / "agents"
        self.live = {}

    def get(self, run_id):
        return self.live.get(run_id)

    def resumable(self, run_id):
        """
        What a follow-up inherits from the run it continues: agent, scope,
        authorization, the exact toolset, program link, and the claude session
        to resume. Read from the archive so it survives a hub restart; nothing
        here is taken from the follow-up request.
        """
        stored = get_run(self.db, run_id) if isinstance(run_id, str) else None
        if not stored:
            raise ValueError("no such run to continue")
        live = self.live.get(run_id)
        if (live and live.status == "running") or stored["status"] == "running":
            raise ValueError("that run is still going; wait for it to finish or stop it first")
        session_id = (live.session_id if live else None) or find_session_id(self.db, run_id)
        if not session_id:
            raise ValueError("that run has no claude session to continue")
        return {**stored, "session_id": session_id}

    def start(self, body, link=None):
        """link: {programId, snapshotId} resolved by the server from a confirmed snapshot — never taken from the request."""
        link = link or {}
        parent = self.resumable(body["continueRun"]) if body.get("continueRun") is not None else None
        task = body.get("task")
        if parent:
            # A follow-up keeps its conversation's agent, scope, and authorization.
            agent, scope, authorization = parent["agent"], parent["scope"], parent["authorization"]
            link = {"programId": parent["program_id"], "snapshotId": parent["snapshot_id"]}
        else:
            agent = body.get("agent")
            scope = body.get("scope") or ""
            authorization = body.get("authorization") or ""
        if not agent or not isinstance(task, str) or not task.strip():
            raise ValueError("agent and task are required")
        if not isinstance(scope, str) or not isinstance(authorization, str):
            raise ValueError("scope and authorization must be text")
        policy = get_policy(self.agents_dir, agent)
        if not policy:
            raise ValueError(f"unknown agent: {agent}")

        orchestrated = agent == ORCHESTRATOR
        if parent:
            # Same toolset as the run being continued: a reply can neither arm nor widen active tooling.
            tools, active_engaged = parent["tools"], parent["active_engaged"]
        else:
            tools, active_engaged = resolve_tools(self.agents_dir, orchestrated, bool(body.get("enableActive")), authorization, policy)

        # Every run carries the RoE. Direct runs also carry the agent's dossier,
        # as the subagent would; Dann gets his definition from --agent, which
        # does not preload skills, so the RoE is not otherwise in his context.
        system_prompt = None
        try:
            roe = (self.repo_root / "RULES-OF-ENGAGEMENT.md").read_text(encoding="utf8")
            if orchestrated:
                system_prompt = roe
            else:
                # Direct runs aren't spawned as subagents, so the definition's `skills:`
                # preload doesn't happen; append those skills here instead.
                parts = [(self.agents_dir / f"{agent}.md").read_text(encoding="utf8"), roe, *preloaded_skills(self.repo_root, agent)]
                system_prompt = "\n\n---\n\n".join(parts)
        except OSError as err:
            print(f"[dossier] {agent}: {err}", file=sys.stderr)

        run_id = str(uuid.uuid4())
        memory_agents = AGENTS if orchestrated else ([agent] if agent in OWNERSHIP else [])
        shared = load_shared_server(self.repo_root)
        mcp_config = (
            write_mcp_config(self.data_dir / "run-configs", run_id, memory_agents, self.db_file, shared) if memory_agents or shared else None
        )
        args = build_session_args(
            tools,
            mcp_config_path=mcp_config,
            mcp_tools=[t for a in memory_agents for t in qualified_tools_for(a)] + (SHARED_READ_TOOLS if shared else []),
            agent_def=ORCHESTRATOR if orchestrated else None,
            system_prompt=system_prompt,
            resume=parent["session_id"] if parent else None,
        )

        run = Run(
            id=run_id,
            agent=agent,
            orchestrated=orchestrated,
            activeEngaged=active_engaged,
            tools=tools,
            programId=link.get("programId"),
            snapshotId=link.get("snapshotId"),
            parentRunId=parent["id"] if parent else None,
            finished=False,
        )
        self.live[run_id] = run
        seq = [0]

        def archive(what, fn):
            try:
                fn()
            except Exception as err:  # archive problems are reported, never fatal to the run
                print(f"[archive] {what}: {err}", file=sys.stderr)
                run.emit({"kind": "warn", "text": f"archive {what} failed: {err}", "ts": now_ms()})

        def push(evt):
            run.emit(evt)
            n = seq[0]
            seq[0] += 1
            archive("event", lambda: append_event(self.db, run_id, n, evt))

        archive(
            "run",
            lambda: create_run(
                self.db,
                {
                    "id": run_id,
                    "agent": agent,
                    "task": task,
                    "scope": scope,
                    "authorization": authorization,
                    "activeEngaged": active_engaged,
                    "tools": tools,
                    "programId": run.programId,
                    "snapshotId": run.snapshotId,
                    "parentRunId": run.parentRunId,
                },
            ),
        )
        push(
            {
                "kind": "meta",
                "agent": agent,
                "orchestrated": orchestrated,
                "activeEngaged": active_engaged,
                "tools": tools,
                "parentRunId": run.parentRunId,
                "ts": now_ms(),
            }
        )

        delegations = {}  # tool_use id -> subagent id
        handbacks = {}  # delegation id -> report delivered via SubagentHandback

        def collect_reports(data):
            message = data.get("message") if isinstance(data.get("message"), dict) else {}
            content = message.get("content") if isinstance(message.get("content"), list) else []
            kind = data.get("type")
            if kind == "assistant":
                for b in content:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                    if b.get("name") in DELEGATE_TOOLS and inp.get("subagent_type"):
                        delegations[b.get("id")] = inp["subagent_type"]
                    if b.get("name") in HANDBACK_TOOLS and data.get("parent_tool_use_id") in delegations:
                        msg = inp.get("message")
                        handbacks[data["parent_tool_use_id"]] = "" if msg is None else str(msg)
            elif kind == "user":
                for b in content:
                    if not isinstance(b, dict) or b.get("type") != "tool_result":
                        continue
                    sub = delegations.get(b.get("tool_use_id"))
                    if not sub:
                        continue
                    text, stats = clean_report(result_text(b.get("content")))
                    text = handbacks.get(b.get("tool_use_id"), text)
                    if text:
                        archive(
                            "report",
                            lambda: add_report(self.db, run_id, sub, "subagent_report", text, {"stats": stats} if stats else None),
                        )
            elif kind == "result" and isinstance(data.get("result"), str):
                meta = {
                    "cost_usd": data.get("total_cost_usd"),
                    "duration_ms": data.get("duration_ms"),
                    "num_turns": data.get("num_turns"),
                    "is_error": bool(data.get("is_error")),
                }
                archive("report", lambda: add_report(self.db, run_id, agent, "final", data["result"], meta))

        def finish():
            result = run.result or {}
            archive(
                "finish",
                lambda: finish_run(self.db, run_id, run.status, result.get("total_cost_usd"), result.get("duration_ms")),
            )
            run.close()

        prompt = build_followup_prompt(task) if parent else build_prompt(agent, task, scope, authorization, orchestrated)
        try:
            proc = subprocess.Popen(
                resolve_command(self.claude_cmd) + args,
                cwd=self.repo_root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0,
            )
        except OSError as err:
            run.status = "error"
            push({"kind": "error", "text": f"spawn failed: {err}", "ts": now_ms()})
            finish()
            return run
        run.proc = proc

        def feed_prompt():
            try:
                proc.stdin.write(prompt.encode("utf8"))
                proc.stdin.close()
            except OSError:
                pass  # child may exit before reading the prompt

        def read_stderr():
            for chunk in iter(lambda: proc.stderr.read1(65536), b""):
                push({"kind": "stderr", "text": chunk.decode("utf8", "replace"), "ts": now_ms()})

        def read_stdout():
            err_thread = threading.Thread(target=read_stderr, daemon=True)
            err_thread.start()
            for raw in proc.stdout:
                line = raw.decode("utf8", "replace").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    push({"kind": "stdout", "text": line, "ts": now_ms()})
                    continue
                if not isinstance(obj, dict):
                    push({"kind": "stdout", "text": line, "ts": now_ms()})
                    continue
                if obj.get("type") == "result":
                    run.result = obj
                if isinstance(obj.get("session_id"), str) and obj["session_id"]:
                    run.session_id = obj["session_id"]
                push({"kind": "claude", "data": obj, "ts": now_ms()})
                collect_reports(obj)
            err_thread.join()
            code = proc.wait()
            run.status = "stopped" if run.status == "stopped" else ("done" if code == 0 else "error")
            push({"kind": "closed", "code": code, "status": run.status, "ts": now_ms()})
            finish()

        threading.Thread(target=feed_prompt, daemon=True).start()
        threading.Thread(target=read_stdout, daemon=True).start()
        return run

    def stop(self, run_id):
        run = self.live.get(run_id)
        if not run:
            return None
        if run.proc and run.status == "running":
            run.status = "stopped"
            kill_tree(run.proc)
        return run

    def stop_all(self):
        """Stop every live run (the desktop shell calls this on quit)."""
        for run_id in list(self.live):
            self.stop(run_id)


def kill_tree(proc):
    """Stop a run and everything it started (MCP servers, subagent shells)."""
    if proc.poll() is not None:
        return
    if WINDOWS:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        proc.kill()
