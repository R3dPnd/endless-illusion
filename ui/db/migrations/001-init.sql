-- Endless Illusion persistence schema v1. See docs/superpowers/specs/2026-10-15-persistence-design.md

-- ---- hub (written by the server only) ----
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  agent TEXT NOT NULL,
  task TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  authorization TEXT NOT NULL DEFAULT '',
  active_engaged INTEGER NOT NULL DEFAULT 0,
  tools TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL CHECK (status IN ('running','done','error','stopped','interrupted')),
  program_id INTEGER REFERENCES programs(id),
  snapshot_id INTEGER REFERENCES scope_snapshots(id),
  cost_usd REAL,
  duration_ms INTEGER,
  started_at TEXT NOT NULL,
  ended_at TEXT
);
CREATE INDEX runs_started ON runs(started_at);

CREATE TABLE run_events (
  run_id TEXT NOT NULL REFERENCES runs(id),
  seq INTEGER NOT NULL,
  ts INTEGER NOT NULL,
  event TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);

CREATE TABLE reports (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES runs(id),
  agent TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('subagent_report','final')),
  text TEXT NOT NULL,
  meta TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX reports_run ON reports(run_id);

-- ---- operator (written through the UI only) ----
CREATE TABLE programs (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  platform TEXT,
  url TEXT NOT NULL,
  normalized_url TEXT NOT NULL UNIQUE,
  policy_text TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL CHECK (source IN ('manual','lead','sync')),
  created_at TEXT NOT NULL
);

CREATE TABLE lead_decisions (
  normalized_url TEXT PRIMARY KEY,
  decision TEXT NOT NULL CHECK (decision IN ('tracked','dismissed')),
  program_id INTEGER REFERENCES programs(id),
  decided_at TEXT NOT NULL
);

CREATE TABLE proposal_decisions (
  proposal_id INTEGER PRIMARY KEY REFERENCES scope_proposals(id),
  decision TEXT NOT NULL CHECK (decision IN ('confirmed','rejected')),
  decided_at TEXT NOT NULL
);

CREATE TABLE scope_snapshots (
  id INTEGER PRIMARY KEY,
  program_id INTEGER NOT NULL REFERENCES programs(id),
  proposal_id INTEGER REFERENCES scope_proposals(id),
  in_scope TEXT NOT NULL,
  out_of_scope TEXT NOT NULL,
  exclusions TEXT NOT NULL,
  confirmed_at TEXT NOT NULL
);

-- ---- agent domains (append-only; corrections use supersedes) ----
CREATE TABLE program_leads (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES program_leads(id),
  name TEXT NOT NULL, platform TEXT, url TEXT NOT NULL, normalized_url TEXT NOT NULL,
  found_via TEXT NOT NULL, scope_summary TEXT NOT NULL DEFAULT ''
);
CREATE INDEX program_leads_url ON program_leads(normalized_url);

CREATE TABLE scope_proposals (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES scope_proposals(id),
  program_id INTEGER NOT NULL REFERENCES programs(id),
  in_scope TEXT NOT NULL, out_of_scope TEXT NOT NULL, exclusions TEXT NOT NULL,
  source_excerpt TEXT NOT NULL DEFAULT ''
);

CREATE TABLE submissions (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES submissions(id),
  program_id INTEGER NOT NULL REFERENCES programs(id),
  title TEXT NOT NULL,
  severity TEXT NOT NULL CHECK (severity IN ('info','low','medium','high','critical')),
  body_markdown TEXT NOT NULL,
  finding_refs TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE assets (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES assets(id),
  host TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('domain','subdomain','ip','url','service')),
  details TEXT NOT NULL DEFAULT '{}',
  engagement_id INTEGER REFERENCES engagements(id)
);
CREATE INDEX assets_host ON assets(host);

CREATE TABLE asset_observations (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES asset_observations(id),
  asset_host TEXT NOT NULL, port INTEGER, service TEXT, technology TEXT, evidence TEXT NOT NULL DEFAULT ''
);
CREATE INDEX asset_observations_host ON asset_observations(asset_host);

CREATE TABLE web_findings (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES web_findings(id),
  target TEXT NOT NULL, title TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('confirmed','suspected','not_reproduced')),
  severity TEXT NOT NULL CHECK (severity IN ('info','low','medium','high','critical')),
  description TEXT NOT NULL, reproduction TEXT NOT NULL DEFAULT '', impact TEXT NOT NULL DEFAULT '',
  remediation TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL DEFAULT '',
  program_id INTEGER REFERENCES programs(id), engagement_id INTEGER REFERENCES engagements(id)
);
CREATE INDEX web_findings_target ON web_findings(target);

CREATE TABLE api_endpoints (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES api_endpoints(id),
  base_url TEXT NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL, auth TEXT, notes TEXT
);

CREATE TABLE api_findings (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES api_findings(id),
  target TEXT NOT NULL, title TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('confirmed','suspected','not_reproduced')),
  severity TEXT NOT NULL CHECK (severity IN ('info','low','medium','high','critical')),
  description TEXT NOT NULL, reproduction TEXT NOT NULL DEFAULT '', impact TEXT NOT NULL DEFAULT '',
  remediation TEXT NOT NULL DEFAULT '', evidence TEXT NOT NULL DEFAULT '',
  program_id INTEGER REFERENCES programs(id), engagement_id INTEGER REFERENCES engagements(id)
);
CREATE INDEX api_findings_target ON api_findings(target);

CREATE TABLE cve_notes (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES cve_notes(id),
  cve_id TEXT NOT NULL, product TEXT NOT NULL, affected_versions TEXT NOT NULL,
  fixed_version TEXT, cvss TEXT, kev INTEGER NOT NULL DEFAULT 0, public_exploit INTEGER NOT NULL DEFAULT 0,
  summary TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX cve_notes_cve ON cve_notes(cve_id);

CREATE TABLE exploit_analyses (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES exploit_analyses(id),
  cve_id TEXT, title TEXT NOT NULL, mechanism TEXT NOT NULL, preconditions TEXT NOT NULL DEFAULT '',
  detection TEXT NOT NULL DEFAULT '', mitigation TEXT NOT NULL DEFAULT '', sources TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE engagements (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES engagements(id),
  name TEXT NOT NULL, program_id INTEGER REFERENCES programs(id)
);

CREATE TABLE run_engagements (
  id INTEGER PRIMARY KEY, agent TEXT NOT NULL, run_id TEXT, created_at TEXT NOT NULL,
  supersedes INTEGER REFERENCES run_engagements(id),
  linked_run_id TEXT NOT NULL, engagement_id INTEGER NOT NULL REFERENCES engagements(id)
);

-- ---- full-text search across reports and structured records ----
CREATE VIRTUAL TABLE search_fts USING fts5(kind, ref_id UNINDEXED, title, body);

CREATE TRIGGER reports_fts AFTER INSERT ON reports BEGIN
  INSERT INTO search_fts(kind, ref_id, title, body) VALUES ('report', NEW.id, NEW.agent || ' ' || NEW.kind, NEW.text);
END;
CREATE TRIGGER web_findings_fts AFTER INSERT ON web_findings BEGIN
  INSERT INTO search_fts(kind, ref_id, title, body) VALUES ('web_finding', NEW.id, NEW.title, NEW.target || ' ' || NEW.description || ' ' || NEW.impact);
END;
CREATE TRIGGER api_findings_fts AFTER INSERT ON api_findings BEGIN
  INSERT INTO search_fts(kind, ref_id, title, body) VALUES ('api_finding', NEW.id, NEW.title, NEW.target || ' ' || NEW.description || ' ' || NEW.impact);
END;
CREATE TRIGGER cve_notes_fts AFTER INSERT ON cve_notes BEGIN
  INSERT INTO search_fts(kind, ref_id, title, body) VALUES ('cve_note', NEW.id, NEW.cve_id || ' ' || NEW.product, NEW.summary);
END;
CREATE TRIGGER exploit_analyses_fts AFTER INSERT ON exploit_analyses BEGIN
  INSERT INTO search_fts(kind, ref_id, title, body) VALUES ('exploit_analysis', NEW.id, NEW.title, coalesce(NEW.cve_id, '') || ' ' || NEW.mechanism);
END;
CREATE TRIGGER submissions_fts AFTER INSERT ON submissions BEGIN
  INSERT INTO search_fts(kind, ref_id, title, body) VALUES ('submission', NEW.id, NEW.title, NEW.body_markdown);
END;
