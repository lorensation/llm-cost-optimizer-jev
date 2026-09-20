ALTER TABLE audit_jobs ADD COLUMN needs_human_review INTEGER NOT NULL DEFAULT 0;
ALTER TABLE audit_jobs ADD COLUMN human_review_json TEXT;
