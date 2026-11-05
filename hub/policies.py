import json
import sys

DAY_ORDER = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def load_policies(agents_dir):
    """Agent policies from agents/*.policy.json, orchestrator first then by weekday."""
    policies = []
    for f in sorted(agents_dir.glob("*.policy.json")):
        try:
            policies.append(json.loads(f.read_text(encoding="utf8")))
        except (OSError, ValueError) as err:
            print(f"[policy] failed to read {f.name}: {err}", file=sys.stderr)

    def key(p):
        if p.get("role") == "orchestrator":
            return -1
        return DAY_ORDER.index(p["day"]) if p.get("day") in DAY_ORDER else -1

    return sorted(policies, key=key)


def get_policy(agents_dir, agent):
    return next((p for p in load_policies(agents_dir) if p.get("agent") == agent), None)
