
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
    # Income table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            monthly_salary REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # EMI table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            tenure_months INTEGER NOT NULL,
            months_paid INTEGER DEFAULT 0,
            start_date DATE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Goals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            target_date DATE,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
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

# ─── Income ───────────────────────────────────────────────────────

def save_income(user_id: int, monthly_salary: float):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO income (user_id, monthly_salary)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            monthly_salary = excluded.monthly_salary,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, monthly_salary))
    conn.commit()
    conn.close()

def get_income(user_id: int) -> float:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT monthly_salary FROM income WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0.0

# ─── EMI ──────────────────────────────────────────────────────────

def add_emi(user_id: int, name: str, amount: float,
            tenure_months: int, start_date: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO emis (user_id, name, amount, tenure_months, start_date)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, name, amount, tenure_months, start_date))
    conn.commit()
    conn.close()

def get_active_emis(user_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, amount, tenure_months, months_paid,
               start_date, status
        FROM emis
        WHERE user_id = ? AND status = 'active'
        ORDER BY created_at ASC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "amount": r[2],
            "tenure_months": r[3],
            "months_paid": r[4],
            "start_date": r[5],
            "status": r[6],
            "months_remaining": r[3] - r[4]
        }
        for r in rows
    ]

def get_all_emis(user_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, amount, tenure_months, months_paid,
               start_date, status
        FROM emis
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "amount": r[2],
            "tenure_months": r[3],
            "months_paid": r[4],
            "start_date": r[5],
            "status": r[6],
            "months_remaining": max(0, r[3] - r[4])
        }
        for r in rows
    ]

def update_emi_progress(user_id: int):
    """
    Called monthly — increments months_paid for all active EMIs.
    Marks complete when months_paid >= tenure_months.
    Returns list of newly completed EMI names.
    """
    from datetime import date
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, tenure_months, months_paid, start_date
        FROM emis WHERE user_id = ? AND status = 'active'
    """, (user_id,))
    emis = cursor.fetchall()

    completed = []
    today = date.today()

    for emi_id, name, tenure, paid, start_str in emis:
        start = date.fromisoformat(start_str)
        months_elapsed = (today.year - start.year) * 12 + (today.month - start.month)
        new_paid = min(months_elapsed, tenure)

        if new_paid >= tenure:
            cursor.execute("""
                UPDATE emis SET months_paid = ?, status = 'completed'
                WHERE id = ?
            """, (new_paid, emi_id))
            completed.append(name)
        else:
            cursor.execute("""
                UPDATE emis SET months_paid = ? WHERE id = ?
            """, (new_paid, emi_id))

    conn.commit()
    conn.close()
    return completed

def delete_emi(emi_id: int, user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM emis WHERE id = ? AND user_id = ?",
        (emi_id, user_id)
    )
    conn.commit()
    conn.close()

def get_total_emi(user_id: int) -> float:
    emis = get_active_emis(user_id)
    return sum(e["amount"] for e in emis)

# ─── Goals ────────────────────────────────────────────────────────

def add_goal(user_id: int, name: str, target_amount: float,
             target_date: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO goals (user_id, name, target_amount, target_date)
        VALUES (?, ?, ?, ?)
    """, (user_id, name, target_amount, target_date))
    conn.commit()
    conn.close()

def get_active_goals(user_id: int) -> list:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, target_amount, target_date, status, created_at
        FROM goals
        WHERE user_id = ? AND status = 'active'
        ORDER BY target_date ASC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "name": r[1],
            "target_amount": r[2],
            "target_date": r[3],
            "status": r[4],
            "created_at": r[5]
        }
        for r in rows
    ]

def complete_goal(goal_id: int, user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE goals SET status = 'completed' WHERE id = ? AND user_id = ?",
        (goal_id, user_id)
    )
    conn.commit()
    conn.close()

def delete_goal(goal_id: int, user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, user_id)
    )
    conn.commit()
    conn.close()

# ─── Disposable Income ────────────────────────────────────────────

def get_disposable_income(user_id: int) -> dict:
    salary = get_income(user_id)
    total_emi = get_total_emi(user_id)
    disposable = salary - total_emi
    return {
        "salary": salary,
        "total_emi": total_emi,
        "disposable": disposable
    }