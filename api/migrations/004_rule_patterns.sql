-- Rules become patterns. A rule carries a `match_type` of `exact` (the whole description, which is
-- what every pre-004 rule was) or `contains` (a case-insensitive literal substring). Classification
-- is no longer a dictionary lookup: every matching rule is a candidate and the most specific one
-- wins, so `rules` gains a `match_type` column and `description` becomes `pattern`.
--
-- The backfill is one-to-one in `match_type = 'exact'`: nothing learned changes behaviour, and no
-- rule starts matching rows it did not match before. A rule is unique per (match_type, pattern)
-- case-insensitively, which is what lets one text exist as both an exact rule and a keyword rule.
--
-- `rules` is rebuilt rather than altered because the primary key changes shape, and SQLite cannot
-- change a primary key or an existing column in place.

CREATE TABLE rules_new (
    match_type TEXT NOT NULL CHECK (match_type IN ('exact', 'contains')),
    pattern TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (match_type, pattern),
    FOREIGN KEY (category) REFERENCES categories (name) ON UPDATE CASCADE ON DELETE RESTRICT
) STRICT;

INSERT INTO rules_new (match_type, pattern, category, created_at, updated_at)
SELECT 'exact', description, category, created_at, updated_at FROM rules;

DROP TABLE rules;

ALTER TABLE rules_new RENAME TO rules;

-- A pre-004 database keyed on the case-sensitive `description` column, so two rules that differ only
-- in case could exist. Keep the most recently written one before the case-insensitive index refuses
-- to be created.
DELETE FROM rules
WHERE rowid NOT IN (
    SELECT max(rowid) FROM rules GROUP BY match_type, lower(pattern)
);

CREATE UNIQUE INDEX idx_rules_pattern_nocase ON rules (match_type, pattern COLLATE NOCASE);
