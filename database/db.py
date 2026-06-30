
import sqlite3
import os
import bcrypt

DB_FILE = "data/expenses.db"

def get_connection():
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(DB_FILE)

def create_table():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Transactions table with user_id
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            merchant TEXT,
            amount REAL,
            date TEXT,
            category TEXT,
            payment_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()

# ─── Auth Functions ───────────────────────────────────

def register_user(name, email, password):
    try:
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, hashed.decode("utf-8"))
        )
        conn.commit()
        conn.close()
        return True, "Registration successful!"
    except sqlite3.IntegrityError:
        return False, "Email already registered. Please login."
    except Exception as e:
        return False, str(e)

def login_user(email, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, password FROM users WHERE email = ?",
            (email,)
        )
        user = cursor.fetchone()
        conn.close()
        if not user:
            return False, None, "Email not found. Please register."
        user_id, name, hashed = user
        if bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")):
            return True, {"id": user_id, "name": name, "email": email}, "Login successful!"
        else:
            return False, None, "Incorrect password."
    except Exception as e:
        return False, None, str(e)

# ─── Transaction Functions ────────────────────────────

def save_transaction(transaction, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, merchant, amount, date, category, payment_method)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        transaction.get("merchant"),
        transaction.get("amount"),
        transaction.get("date"),
        transaction.get("category"),
        transaction.get("payment_method", "Unknown")
    ))
    conn.commit()
    conn.close()

def load_transactions(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, merchant, amount, date, category, payment_method
        FROM transactions
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "merchant": r[1],
            "amount": r[2],
            "date": r[3],
            "category": r[4],
            "payment_method": r[5]
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