-- Categories and the rules that assign them, replacing `api/categories.yaml`. A rule keys on one
-- exact description, so there is no ordering and no first-match-wins: a description either has a
-- rule or it lands in `Uncategorized`.
--
-- Only the category names are seeded here. Nothing is pre-taught, so every stored row starts
-- Uncategorized and the app learns descriptions from use.
--
-- `transactions` is rebuilt rather than altered because SQLite cannot add a foreign key or drop a
-- column in place, and `PRAGMA foreign_keys` cannot be flipped inside the migration runner's
-- transaction. Foreign keys stay on: the only parent of `transactions` (`accounts`) is untouched,
-- and the copy resets every category to `Uncategorized`, which is the honest state once the old
-- rules are gone. `is_transfer` is dropped because a row is a transfer exactly when its category is
-- `Transfers`.

CREATE TABLE categories (
    name TEXT NOT NULL PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE
) STRICT;

INSERT INTO categories (name, position) VALUES
    ('Income', 1),
    ('Rent', 2),
    ('Utilities', 3),
    ('Groceries', 4),
    ('Dining', 5),
    ('Transport', 6),
    ('Shopping', 7),
    ('Health', 8),
    ('Subscriptions', 9),
    ('Transfers', 10),
    ('Uncategorized', 11);

CREATE TABLE rules (
    description TEXT NOT NULL PRIMARY KEY,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (category) REFERENCES categories (name) ON UPDATE CASCADE ON DELETE RESTRICT
) STRICT;

CREATE TABLE transactions_new (
    connection_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    transaction_id TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    posted_date TEXT NOT NULL,
    transacted_at TEXT,
    description TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    category TEXT NOT NULL DEFAULT 'Uncategorized',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (connection_id, account_id, transaction_id),
    FOREIGN KEY (connection_id, account_id) REFERENCES accounts (connection_id, account_id) ON DELETE CASCADE,
    FOREIGN KEY (category) REFERENCES categories (name) ON UPDATE CASCADE ON DELETE RESTRICT
) STRICT;

INSERT INTO transactions_new (
    connection_id, account_id, transaction_id, posted_at, posted_date, transacted_at,
    description, amount_cents, category, created_at, updated_at
)
SELECT
    connection_id, account_id, transaction_id, posted_at, posted_date, transacted_at,
    description, amount_cents, 'Uncategorized', created_at, updated_at
FROM transactions;

DROP TABLE transactions;

ALTER TABLE transactions_new RENAME TO transactions;

-- The transfer index goes with the dropped column; `idx_transactions_category` covers the filter.
CREATE INDEX idx_transactions_posted_date ON transactions (posted_date DESC);
CREATE INDEX idx_transactions_account ON transactions (connection_id, account_id, posted_date DESC);
CREATE INDEX idx_transactions_category ON transactions (category, posted_date DESC);
