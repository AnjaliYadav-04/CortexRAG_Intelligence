-- Enterprise RAG — Kubernetes Ops Database Schema
-- PostgreSQL 16

CREATE TABLE IF NOT EXISTS clusters (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    region        TEXT NOT NULL,
    version       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'healthy',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nodes (
    id            SERIAL PRIMARY KEY,
    cluster_id    INT NOT NULL REFERENCES clusters(id),
    name          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Ready',
    cpu_total     INT NOT NULL DEFAULT 8,
    mem_total_gb  INT NOT NULL DEFAULT 32,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pods (
    id             SERIAL PRIMARY KEY,
    node_id        INT NOT NULL REFERENCES nodes(id),
    namespace      TEXT NOT NULL DEFAULT 'default',
    name           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'Running',
    restart_count  INT NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS incidents (
    id          SERIAL PRIMARY KEY,
    cluster_id  INT NOT NULL REFERENCES clusters(id),
    severity    TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low')),
    title       TEXT NOT NULL,
    opened_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS deployments (
    id              SERIAL PRIMARY KEY,
    cluster_id      INT NOT NULL REFERENCES clusters(id),
    namespace       TEXT NOT NULL DEFAULT 'default',
    name            TEXT NOT NULL,
    replicas        INT NOT NULL DEFAULT 1,
    ready_replicas  INT NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- LangGraph checkpoint table (used by PostgresSaver)
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
    thread_id   TEXT NOT NULL,
    checkpoint  JSONB NOT NULL,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (thread_id)
);

-- ── Sample data ───────────────────────────────────────────────────────────────

INSERT INTO clusters (name, region, version, status) VALUES
  ('prod-us-east-1', 'us-east-1', '1.29.4', 'healthy'),
  ('prod-eu-west-1', 'eu-west-1', '1.29.3', 'healthy'),
  ('staging-us-east-1', 'us-east-1', '1.30.0', 'degraded')
ON CONFLICT DO NOTHING;

INSERT INTO nodes (cluster_id, name, status, cpu_total, mem_total_gb) VALUES
  (1, 'node-us-east-1a', 'Ready', 16, 64),
  (1, 'node-us-east-1b', 'Ready', 16, 64),
  (1, 'node-us-east-1c', 'NotReady', 16, 64),
  (2, 'node-eu-west-1a', 'Ready', 8, 32),
  (3, 'node-staging-1a', 'Ready', 8, 16)
ON CONFLICT DO NOTHING;

INSERT INTO pods (node_id, namespace, name, status, restart_count) VALUES
  (1, 'kube-system', 'coredns-abc123', 'Running', 0),
  (1, 'monitoring', 'prometheus-0', 'Running', 2),
  (2, 'default', 'api-gateway-xyz', 'Running', 0),
  (3, 'default', 'worker-crashed-1', 'CrashLoopBackOff', 47),
  (3, 'default', 'worker-crashed-2', 'CrashLoopBackOff', 31),
  (4, 'default', 'frontend-abc', 'Running', 0),
  (5, 'staging', 'test-pod-001', 'Pending', 0)
ON CONFLICT DO NOTHING;

INSERT INTO incidents (cluster_id, severity, title, opened_at, closed_at) VALUES
  (1, 'high', 'Node node-us-east-1c NotReady', NOW() - INTERVAL '2 hours', NULL),
  (3, 'critical', 'Multiple pods in CrashLoopBackOff', NOW() - INTERVAL '1 hour', NULL),
  (2, 'low', 'Elevated API latency p99 > 500ms', NOW() - INTERVAL '3 hours', NOW() - INTERVAL '30 minutes')
ON CONFLICT DO NOTHING;

INSERT INTO deployments (cluster_id, namespace, name, replicas, ready_replicas) VALUES
  (1, 'default', 'api-gateway', 3, 3),
  (1, 'default', 'worker', 5, 3),
  (1, 'monitoring', 'prometheus', 1, 1),
  (2, 'default', 'frontend', 2, 2),
  (3, 'staging', 'test-service', 1, 0)
ON CONFLICT DO NOTHING;
