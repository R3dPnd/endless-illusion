"""
Rewrite the `tools:` line of each .claude/agents/<agent>.md from
    agents/<agent>.policy.json default_safe  +  the agent's own memory tools.
Run after changing a policy or hub/db/ownership.py:  python -m hub.sync_agent_tools
Active toolsets are never written here; they are granted per run by the hub.
"""

import json
import re

from . import REPO_ROOT
from .db.ownership import AGENTS
from .tool_names import SHARED_READ_TOOLS, qualified_tools_for

TOOLS_LINE = re.compile(r"^(---\r?\n[\s\S]*?^)tools:[^\r\n]*", re.M)


def main():
    for agent in AGENTS:
        policy = json.loads((REPO_ROOT / "agents" / f"{agent}.policy.json").read_text(encoding="utf8"))
        tools = [*policy["tools"]["default_safe"], *qualified_tools_for(agent), *SHARED_READ_TOOLS]
        line = f"tools: {', '.join(tools)}"
        file = REPO_ROOT / ".claude" / "agents" / f"{agent}.md"
        # newline="" keeps the file's own line endings (CRLF on a Windows checkout).
        with open(file, encoding="utf8", newline="") as f:
            md = f.read()
        updated, n = TOOLS_LINE.subn(lambda m: m.group(1) + line, md, count=1)
        if n == 0:
            raise SystemExit(f"{agent}: no tools line found")
        with open(file, "w", encoding="utf8", newline="") as f:
            f.write(updated)
        print(f"{agent}: {len(tools)} tools")


if __name__ == "__main__":
    main()
