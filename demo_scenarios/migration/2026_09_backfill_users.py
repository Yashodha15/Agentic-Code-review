"""Demo migration with intentionally unsafe operational assumptions."""


def migrate(connection) -> None:
    connection.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL")
    rows = connection.execute("SELECT id, email FROM users").fetchall()
    for user_id, email in rows:
        connection.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (email.split('@')[0], user_id),
        )
    connection.commit()

