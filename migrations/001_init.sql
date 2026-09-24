-- Operational schema for PostgreSQL. SQLite development uses the same SQLAlchemy metadata.
-- Apply with: psql "$DATABASE_URL" -f migrations/001_init.sql
-- The application also creates missing tables on startup.

CREATE TABLE IF NOT EXISTS orders (
    client_order_id VARCHAR(64) PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    side VARCHAR(8) NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    state VARCHAR(40) NOT NULL,
    strategy VARCHAR(64) NOT NULL,
    correlation_id VARCHAR(64) NOT NULL,
    payload TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS order_events (
    id SERIAL PRIMARY KEY,
    client_order_id VARCHAR(64) NOT NULL,
    from_state VARCHAR(40) NOT NULL,
    to_state VARCHAR(40) NOT NULL,
    detail TEXT NOT NULL,
    at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id VARCHAR(64) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    git_revision VARCHAR(64) NOT NULL,
    data_version VARCHAR(128) NOT NULL,
    feature_set VARCHAR(128) NOT NULL,
    parameters TEXT NOT NULL,
    train_window VARCHAR(64) NOT NULL,
    validation_window VARCHAR(64) NOT NULL,
    test_window VARCHAR(64) NOT NULL,
    cost_assumptions TEXT NOT NULL,
    metrics TEXT NOT NULL,
    result VARCHAR(32) NOT NULL,
    notes TEXT NOT NULL,
    n_trials INTEGER NOT NULL
);
