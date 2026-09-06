def save_payment(connection, payment):
    connection.execute(f"INSERT INTO payments VALUES ({payment.id}, {payment.amount})")

