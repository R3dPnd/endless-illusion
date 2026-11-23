-- A follow-up message in the chat resumes the previous run's claude session;
-- parent_run_id links the follow-up run to the run it continued.
ALTER TABLE runs ADD COLUMN parent_run_id TEXT REFERENCES runs(id);
