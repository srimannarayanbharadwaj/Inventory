CREATE TABLE IF NOT EXISTS categories (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
  id BIGSERIAL PRIMARY KEY,
  category TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(category, name)
);

CREATE TABLE IF NOT EXISTS transactions (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,
  tx_type TEXT NOT NULL CHECK (tx_type IN ('purchase', 'reduction')),
  category TEXT NOT NULL,
  name TEXT NOT NULL,
  qty DOUBLE PRECISION NOT NULL CHECK (qty > 0),
  created_by TEXT NOT NULL DEFAULT '',
  note TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  recovery_question TEXT NOT NULL DEFAULT '',
  recovery_answer_hash TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL,
  category TEXT NOT NULL,
  name TEXT NOT NULL,
  qty DOUBLE PRECISION NOT NULL CHECK (qty > 0),
  note TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  inventory_applied INTEGER NOT NULL DEFAULT 0 CHECK (inventory_applied IN (0, 1)),
  created_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tx_product ON transactions(category, name);
CREATE INDEX IF NOT EXISTS idx_tx_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_created_by ON orders(created_by);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
