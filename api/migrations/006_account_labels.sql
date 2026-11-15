-- The label vocabulary and the labels each account carries. `labels` is the registry the input
-- autocompletes from; a label exists only while some account carries it, which the accounts service
-- prunes inside the same transaction as the replacement.
CREATE TABLE labels (
    name TEXT NOT NULL PRIMARY KEY
) STRICT;

CREATE UNIQUE INDEX idx_labels_name_nocase ON labels (name COLLATE NOCASE);

CREATE TABLE account_labels (
    connection_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (connection_id, account_id, label),
    FOREIGN KEY (connection_id, account_id) REFERENCES accounts (connection_id, account_id) ON DELETE CASCADE,
    FOREIGN KEY (label) REFERENCES labels (name) ON UPDATE CASCADE ON DELETE CASCADE
) STRICT;

CREATE INDEX idx_account_labels_label ON account_labels (label);
