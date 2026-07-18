-- ─────────────────────────────────────────────────────────────
-- Enable pgvector extension and helpful indexes
-- ─────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Optional: tune for embeddings-heavy workload
-- ALTER SYSTEM SET ivfflat.probes = 10;
