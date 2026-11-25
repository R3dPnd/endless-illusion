"""
Stand-in for the claude CLI: records argv (and EI_RUN_ID), drains the prompt,
optionally blocks while FAKE_HOLD_FILE exists, replays a fixture, and exits
with FAKE_EXIT (default 0).
"""

import json
import os
import sys
import time
from pathlib import Path

if os.environ.get("FAKE_ARGV_FILE"):
    Path(os.environ["FAKE_ARGV_FILE"]).write_text(json.dumps(sys.argv[1:]), encoding="utf8")
if os.environ.get("FAKE_ENV_FILE"):
    Path(os.environ["FAKE_ENV_FILE"]).write_text(json.dumps({"EI_RUN_ID": os.environ.get("EI_RUN_ID")}), encoding="utf8")
prompt = sys.stdin.buffer.read()
if os.environ.get("FAKE_STDIN_FILE"):
    Path(os.environ["FAKE_STDIN_FILE"]).write_bytes(prompt)
hold = os.environ.get("FAKE_HOLD_FILE")
while hold and Path(hold).exists():
    time.sleep(0.05)
fixture = Path(__file__).parent / os.environ.get("FAKE_FIXTURE", "run-events.jsonl")
sys.stdout.buffer.write(fixture.read_bytes())
sys.stdout.buffer.flush()
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
