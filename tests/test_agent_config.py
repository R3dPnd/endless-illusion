"""The .claude/agents definitions agree with the policies and the ownership map."""

import json
import re

import pytest

from hub import REPO_ROOT
from hub.db.ownership import AGENTS, server_name
from hub.session import build_session_args
from hub.tool_names import SHARED_READ_TOOLS, qualified_tools_for, tool_names_for

DEFS = REPO_ROOT / ".claude" / "agents"


def frontmatter(agent):
    md = (DEFS / f"{agent}.md").read_text(encoding="utf8")  # text mode folds CRLF to \n
    m = re.match(r"^---\n([\s\S]*?)^---$", md, re.M)
    return m.group(1) if m else ""


def tools_of(agent):
    m = re.search(r"^tools:\s*(.+)$", frontmatter(agent), re.M)
    return [t.strip() for t in m.group(1).split(",") if t.strip()] if m else []


def policy(agent):
    return json.loads((REPO_ROOT / "agents" / f"{agent}.policy.json").read_text(encoding="utf8"))


def test_include_a_definition_for_every_agent_dann_included():
    assert sorted(f.name for f in DEFS.glob("*.md")) == sorted(f"{a}.md" for a in AGENTS)


@pytest.mark.parametrize("agent", AGENTS)
def test_lists_only_passive_tools_own_memory_tools_and_shared_notes(agent):
    allowed = set(policy(agent)["tools"]["default_safe"]) | set(qualified_tools_for(agent)) | set(SHARED_READ_TOOLS)
    for t in tools_of(agent):
        assert t in allowed, f"{agent}: {t}"


@pytest.mark.parametrize("agent", AGENTS)
def test_can_call_all_of_its_own_write_tools(agent):
    tools = set(tools_of(agent))
    for w in tool_names_for(agent)["write"]:
        assert f"mcp__{server_name(agent)}__{w}" in tools, f"{agent}: {w}"


@pytest.mark.parametrize("agent", AGENTS)
def test_has_no_other_agents_memory_tools(agent):
    others = [f"mcp__{server_name(a)}__" for a in AGENTS if a != agent]
    for t in tools_of(agent):
        assert not any(t.startswith(o) for o in others), f"{agent}: {t}"


@pytest.mark.parametrize("agent", AGENTS)
def test_reads_the_shared_notes_and_preloads_the_roe_quickref(agent):
    tools = set(tools_of(agent))
    for t in SHARED_READ_TOOLS:
        assert t in tools, f"{agent}: {t}"
    assert re.search(r"^skills:\n(?:  - .+\n)*  - roe-quickref$", frontmatter(agent), re.M)


def test_gives_no_specialist_bash_by_default():
    for a in AGENTS:
        assert "Bash" not in tools_of(a)


def test_lets_dann_delegate_with_the_agent_tool():
    assert "Agent" in tools_of("dann-of-thursday")
    assert "Agent" in policy("dann-of-thursday")["tools"]["default_safe"]


# ---- session argv ----


def value_of(args, flag):
    return args[args.index(flag) + 1]


def test_restricts_built_ins_with_tools_and_isolates_mcp():
    a = build_session_args(["Read", "Grep"])
    assert value_of(a, "--tools") == "Read,Grep"
    assert "--strict-mcp-config" in a


def test_never_offers_bash_unless_listed():
    assert "Bash" not in " ".join(build_session_args(["Read"]))


def test_pre_approves_mcp_tools_and_passes_the_config_and_agent():
    a = build_session_args(["Task"], mcp_config_path="/x.json", mcp_tools=["mcp__ei-dann__list_programs"], agent_def="dann-of-thursday")
    assert value_of(a, "--mcp-config") == "/x.json"
    assert value_of(a, "--allowedTools") == "Task,mcp__ei-dann__list_programs"
    assert value_of(a, "--agent") == "dann-of-thursday"
