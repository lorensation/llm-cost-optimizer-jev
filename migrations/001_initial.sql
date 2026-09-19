PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies(
  id TEXT PRIMARY KEY, version TEXT NOT NULL, snapshot_json TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_policy ON policies(active) WHERE active = 1;
CREATE TABLE IF NOT EXISTS requests(
  id TEXT PRIMARY KEY, idempotency_key TEXT UNIQUE, request_hash TEXT NOT NULL,
  contract_id TEXT NOT NULL, policy_id TEXT NOT NULL, status TEXT NOT NULL,
  request_json TEXT NOT NULL, result_json TEXT, cost_microusd INTEGER,
  cost_status TEXT NOT NULL DEFAULT 'estimated', created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations(
  id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id), owner TEXT NOT NULL,
  amount_microusd INTEGER NOT NULL CHECK(amount_microusd >= 0), status TEXT NOT NULL,
  final_microusd INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS calls(
  id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES requests(id), reservation_id TEXT NOT NULL REFERENCES reservations(id),
  kind TEXT NOT NULL, attempt INTEGER NOT NULL, requested_model TEXT NOT NULL,
  resolved_model TEXT, provider TEXT, status TEXT NOT NULL, input_tokens INTEGER,
  output_tokens INTEGER, cost_microusd INTEGER, latency_ms INTEGER NOT NULL,
  error_code TEXT, raw_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_jobs(
  id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE REFERENCES requests(id), status TEXT NOT NULL,
  inclusion_probability REAL NOT NULL, selection_reason TEXT NOT NULL, payload_json TEXT,
  payload_expires_at TEXT NOT NULL, lease_owner TEXT, lease_until TEXT, attempts INTEGER NOT NULL DEFAULT 0,
  result_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);

