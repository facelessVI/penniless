-- Category names are identifiers: two names that differ only in case would be two look-alike entries
-- in every select, so the API refuses them with a readable 400. This index holds the same rule for a
-- hand-edited database, where nothing else would catch it.
CREATE UNIQUE INDEX categories_name_nocase ON categories (name COLLATE NOCASE);
