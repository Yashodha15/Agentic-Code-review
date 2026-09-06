ALTER TABLE users ADD COLUMN display_name TEXT;
UPDATE users SET display_name = full_name WHERE display_name IS NULL;
ALTER TABLE users ALTER COLUMN display_name SET NOT NULL;

-- full_name remains during the compatibility window. A later migration may
-- remove it after every deployed application version reads display_name.
