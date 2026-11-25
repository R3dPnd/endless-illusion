-- Engagement pipeline: operator-started stages plus an approval gate.
-- ops_* and gate_* are hub/operator-owned; plan_drafts is the one agent table.
CREATE TABLE ops_engagements (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('lab','bounty')),
  scope_hosts TEXT NOT NULL DEFAULT '[]',
  scope_notes TEXT NOT NULL DEFAULT '',
  authorization TEXT NOT NULL DEFAULT '',
  program_id INTEGER REFERENCES programs(id),
  snapshot_id INTEGER REFERENCES scope_snapshots(id),
  created_at TEXT NOT NULL
);

CREATE TABLE ops_stages (
  id INTEGER PRIMARY KEY,
  engagement_id INTEGER NOT NULL REFERENCES ops_engagements(id),
  stage TEXT NOT NULL CHECK (stage IN ('discovery','planning','web','api','analysis','reporting','research')),
  status TEXT NOT NULL CHECK (status IN ('ready','running','done','failed','stopped','skipped')),
  run_id TEXT,
  armed INTEGER NOT NULL DEFAULT 0,
  question TEXT,
  created_at TEXT NOT NULL,
  finished_at TEXT
);
CREATE INDEX ops_stages_engagement ON ops_stages(engagement_id);

CREATE TABLE ops_plans (
  id INTEGER PRIMARY KEY,
  engagement_id INTEGER NOT NULL REFERENCES ops_engagements(id),
  draft_id INTEGER NOT NULL REFERENCES plan_drafts(id),
  plan TEXT NOT NULL,
  approved_at TEXT NOT NULL
);
CREATE INDEX ops_plans_engagement ON ops_plans(engagement_id);

CREATE TABLE gate_declarations (
  id INTEGER PRIMARY KEY,
  run_id TEXT,
  target TEXT,
  why TEXT,
  technique TEXT,
  risk TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX gate_declarations_run ON gate_declarations(run_id);

CREATE TABLE gate_actions (
  id INTEGER PRIMARY KEY,
  run_id TEXT,
  engagement_id INTEGER REFERENCES ops_engagements(id),
  stage TEXT,
  tool_name TEXT NOT NULL,
  input TEXT NOT NULL DEFAULT '{}',
  target TEXT,
  why TEXT,
  technique TEXT,
  risk TEXT,
  hosts TEXT NOT NULL DEFAULT '[]',
  verdict TEXT NOT NULL CHECK (verdict IN ('in','out','unknown','none')),
  status TEXT NOT NULL CHECK (status IN ('pending','approved','denied','auto_allowed','auto_denied','expired','cancelled')),
  message TEXT,
  scope_ack INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  decided_at TEXT
);
CREATE INDEX gate_actions_engagement ON gate_actions(engagement_id, status);

CREATE TABLE gate_questions (
  id INTEGER PRIMARY KEY,
  engagement_id INTEGER REFERENCES ops_engagements(id),
  stage TEXT,
  action_id INTEGER REFERENCES gate_actions(id),
  kind TEXT NOT NULL CHECK (kind IN ('ask','explain')),
  question TEXT NOT NULL,
  technique TEXT,
  fork_run_id TEXT,
  answer TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE plan_drafts (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES plan_drafts(id),
  engagement_id INTEGER NOT NULL REFERENCES ops_engagements(id),
  summary TEXT NOT NULL DEFAULT '',
  plan TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX plan_drafts_engagement ON plan_drafts(engagement_id);
