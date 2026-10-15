// Endless Illusion — agent trigger/monitor backend.
// Spawns the `claude` CLI from the repo root (so CLAUDE.md + .claude/agents/
// load), streams its stream-json events to the browser over SSE, and archives
// every run to data/endless-illusion.db.
// Binds to 127.0.0.1 only. User input is passed via stdin, never argv.

import { createApp } from "./server/app.mjs";

const PORT = Number(process.env.PORT || 8787);
const HOST = "127.0.0.1";
const claudeBin = process.env.CLAUDE_BIN || "claude";

const { app } = createApp({ claudeBin, ...(process.env.EI_DATA_DIR ? { dataDir: process.env.EI_DATA_DIR } : {}) });

app.listen(PORT, HOST, () => {
  console.log(`Endless Illusion control plane on http://${HOST}:${PORT}`);
  console.log(`claude bin: ${claudeBin}`);
});
