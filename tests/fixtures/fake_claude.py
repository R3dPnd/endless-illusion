"""Stand-in for the claude CLI: records argv, drains the prompt, replays a fixture."""

import json
import os
import sys
from pathlib import Path

if os.environ.get("FAKE_ARGV_FILE"):
    Path(os.environ["FAKE_ARGV_FILE"]).write_text(json.dumps(sys.argv[1:]), encoding="utf8")
sys.stdin.buffer.read()
fixture = Path(__file__).parent / os.environ.get("FAKE_FIXTURE", "run-events.jsonl")
sys.stdout.buffer.write(fixture.read_bytes())
