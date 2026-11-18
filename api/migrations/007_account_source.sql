-- Accounts arrive from one of two places: a SimpleFIN fetch, or the user creating a cash account by
-- hand. The source is a number rather than a name so that the meaning of a stored row never depends
-- on a string, and it is written once: a fetch names its own source on insert and never touches the
-- column on conflict, so an account cannot move between the two.
--
-- Everything stored before this migration came from a fetch, which is the only writer that existed.
ALTER TABLE accounts ADD COLUMN source INTEGER NOT NULL DEFAULT 1 CHECK (source IN (1, 2));
