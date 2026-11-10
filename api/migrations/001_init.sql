-- v0 schema. Every key is composite because SimpleFIN guarantees transaction ids only within an
-- account and account ids only within a connection.

CREATE TABLE accounts (
    connection_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    connection_name TEXT NOT NULL,
    name TEXT NOT NULL,
    currency TEXT NOT NULL,
    balance_cents INTEGER NOT NULL,
    available_balance_cents INTEGER,
    balance_date TEXT NOT NULL,
    include_in_cash INTEGER NOT NULL DEFAULT 1 CHECK (include_in_cash IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (connection_id, account_id)
) STRICT;

CREATE TABLE account_balances (
    connection_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    balance_date TEXT NOT NULL,
    balance_cents INTEGER NOT NULL,
    available_balance_cents INTEGER,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (connection_id, account_id, balance_date),
    FOREIGN KEY (connection_id, account_id) REFERENCES accounts (connection_id, account_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE transactions (
    connection_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    posted_date TEXT NOT NULL,
    transacted_at TEXT,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'Uncategorized',
    is_transfer INTEGER NOT NULL DEFAULT 0 CHECK (is_transfer IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (connection_id, account_id, transaction_id),
    FOREIGN KEY (connection_id, account_id) REFERENCES accounts (connection_id, account_id) ON DELETE CASCADE
) STRICT;

CREATE TABLE data_fetches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    transaction_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_message TEXT
) STRICT;

CREATE INDEX idx_transactions_posted_date ON transactions (posted_date DESC);

CREATE INDEX idx_transactions_account ON transactions (connection_id, account_id, posted_date DESC);

CREATE INDEX idx_transactions_category ON transactions (category, posted_date DESC);

CREATE INDEX idx_transactions_transfer ON transactions (posted_date, is_transfer);

CREATE INDEX idx_account_balances_account ON account_balances (connection_id, account_id, balance_date DESC);

CREATE INDEX idx_data_fetches_connection ON data_fetches (connection_id, fetched_at DESC);
