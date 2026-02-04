-- Add checkpoints column to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS checkpoints JSONB;

-- Set default for existing rows
UPDATE jobs 
SET checkpoints = '{"ocrCheckpoint": "pending", "dischargeMedicationsCheckpoint": "pending", "dischargeSummaryCheckpoint": "pending"}'::jsonb
WHERE checkpoints IS NULL;
