-- A declaration authorizes exactly one gated action: mark it consumed.
ALTER TABLE gate_declarations ADD COLUMN used_at TEXT;
ALTER TABLE gate_declarations ADD COLUMN action_id INTEGER REFERENCES gate_actions(id);
CREATE INDEX gate_declarations_unused ON gate_declarations(run_id, used_at);
