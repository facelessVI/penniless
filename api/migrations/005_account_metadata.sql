-- The user's own name and note for an account, kept apart from `name`, which every fetch overwrites.
ALTER TABLE accounts ADD COLUMN display_name TEXT;

ALTER TABLE accounts ADD COLUMN description TEXT;
