-- Bounty board: richer lead details, supplied by agents through record_program_lead
-- (the bounty-scout skill says how to find and fill them). All optional; a lead is
-- still informational only and never authorizes testing.
ALTER TABLE program_leads ADD COLUMN program_type TEXT CHECK (program_type IN ('bounty','vdp'));
ALTER TABLE program_leads ADD COLUMN rewards TEXT;
ALTER TABLE program_leads ADD COLUMN max_reward_usd INTEGER;
ALTER TABLE program_leads ADD COLUMN asset_types TEXT;
ALTER TABLE program_leads ADD COLUMN details TEXT;
ALTER TABLE program_leads ADD COLUMN program_updated TEXT;
ALTER TABLE program_leads ADD COLUMN sources TEXT;
