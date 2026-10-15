#!/usr/bin/env node
// Stand-in for the claude CLI: records argv, drains the prompt, replays a fixture.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

if (process.env.FAKE_ARGV_FILE) writeFileSync(process.env.FAKE_ARGV_FILE, JSON.stringify(process.argv.slice(2)));
process.stdin.resume();
process.stdin.on("end", () => {
  const fixture = path.join(path.dirname(fileURLToPath(import.meta.url)), process.env.FAKE_FIXTURE || "run-events.jsonl");
  process.stdout.write(readFileSync(fixture, "utf8"));
});
