def migrate(connection):
    connection.execute("ALTER TABLE payments ADD COLUMN status TEXT NOT NULL")

