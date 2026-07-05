
import sqlite3
import os
import bcrypt

DB_FILE = "data/expenses.db"

def get_connection():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_table():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            currency TEXT DEFAULT 'INR',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            merchant TEXT,
            amount REAL NOT NULL,
            original_amount REAL,
            original_currency TEXT DEFAULT 'INR',
            exchange_rate REAL DEFAULT 1.0,
            transaction_date DATE NOT NULL,
            category TEXT,
            payment_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_user_date
        ON transactions(user_id, transaction_date)
    """)

    conn.commit()
    conn.close()

def register_user(username, email, password):
    try:
        hashed = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username.lower().strip(), email.lower().strip(), hashed)
        )
        conn.commit()
        conn.close()
        return True, "Registration successful!"
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already taken. Please choose another."
        elif "email" in str(e):
            return False, "Email already registered. Please login."
        return False, "Registration failed. Please try again."
    except Exception as e:
        return False, str(e)

def login_user(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email, currency, password FROM users WHERE username = ?",
            (username.lower().strip(),)
        )
        user = cursor.fetchone()
        conn.close()
        if not user:
            return False, None, "Username not found. Please register."
        user_id, uname, email, currency, hashed = user
        if bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")):
            return True, {
                "id": user_id,
                "name": uname,
                "email": email,
                "currency": currency
            }, "Login successful!"
        return False, None, "Incorrect password. Please try again."
    except Exception as e:
        return False, None, str(e)

def update_currency(user_id, currency):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET currency = ? WHERE id = ?",
        (currency, user_id)
    )
    conn.commit()
    conn.close()

def save_transaction(transaction, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions
            (user_id, merchant, amount, original_amount, original_currency,
             exchange_rate, transaction_date, category, payment_method)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        transaction.get("merchant", "Unknown Merchant"),
        transaction.get("amount"),  # always INR
        transaction.get("original_amount", transaction.get("amount")),
        transaction.get("original_currency", "INR"),
        transaction.get("exchange_rate", 1.0),
        transaction.get("date"),
        transaction.get("category", "Others"),
        transaction.get("payment_method", "Unknown")
    ))
    conn.commit()
    conn.close()

def load_transactions(user_id, filter_type="All", start_date=None, end_date=None):
    conn = get_connection()
    cursor = conn.cursor()

    from datetime import date, timedelta
    today = date.today()

    if filter_type == "Today":
        start = today
        end = today
    elif filter_type == "This Week":
        start = today - timedelta(days=today.weekday())
        end = today
    elif filter_type == "This Month":
        start = today.replace(day=1)
        end = today
    elif filter_type == "Custom" and start_date and end_date:
        start = start_date
        end = end_date
    else:
        start = None
        end = None

    if start and end:
        cursor.execute("""
            SELECT id, merchant, amount, original_amount, original_currency,
                   transaction_date, category, payment_method, created_at
            FROM transactions
            WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
            ORDER BY transaction_date DESC, created_at DESC
        """, (user_id, start.isoformat(), end.isoformat()))
    else:
        cursor.execute("""
            SELECT id, merchant, amount, original_amount, original_currency,
                   transaction_date, category, payment_method, created_at
            FROM transactions
            WHERE user_id = ?
            ORDER BY transaction_date DESC, created_at DESC
        """, (user_id,))

    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "merchant": r[1],
            "amount": r[2],
            "original_amount": r[3],
            "original_currency": r[4],
            "date": r[5],
            "category": r[6],
            "payment_method": r[7],
            "created_at": r[8]
        }
        for r in rows
    ]

def delete_transaction(transaction_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transactions WHERE id = ? AND user_id = ?",
        (transaction_id, user_id)
    )
    conn.commit()
    conn.close()

def get_db_path():
    return os.path.abspath(DB_FILE)