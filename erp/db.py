import sqlite3
import os
import hashlib
import binascii
from typing import List, Tuple, Optional

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "erp.db")


SCHEMA_STATEMENTS = [
    "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, student_id INTEGER)",
    "CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY, name TEXT NOT NULL, roll_no TEXT UNIQUE, department TEXT, contact TEXT, address TEXT)",
    "CREATE TABLE IF NOT EXISTS hostel_rooms (id INTEGER PRIMARY KEY, block TEXT, room_no TEXT, capacity INTEGER DEFAULT 1)",
    "CREATE TABLE IF NOT EXISTS hostel_allocations (id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, room_id INTEGER NOT NULL, checkin_date TEXT, checkout_date TEXT, FOREIGN KEY(student_id) REFERENCES students(id), FOREIGN KEY(room_id) REFERENCES hostel_rooms(id))",
    "CREATE TABLE IF NOT EXISTS hostel_payments (id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, amount REAL NOT NULL, date TEXT, receipt_no TEXT, FOREIGN KEY(student_id) REFERENCES students(id))",
    "CREATE TABLE IF NOT EXISTS drivers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, license_no TEXT)",
    "CREATE TABLE IF NOT EXISTS buses (id INTEGER PRIMARY KEY, registration TEXT UNIQUE, capacity INTEGER DEFAULT 20, driver_id INTEGER, FOREIGN KEY(driver_id) REFERENCES drivers(id))",
    "CREATE TABLE IF NOT EXISTS routes (id INTEGER PRIMARY KEY, name TEXT, pickup_location TEXT, bus_id INTEGER, fee REAL DEFAULT 0, FOREIGN KEY(bus_id) REFERENCES buses(id))",
    "CREATE TABLE IF NOT EXISTS transport_allocations (id INTEGER PRIMARY KEY, student_id INTEGER, route_id INTEGER, active INTEGER DEFAULT 1, FOREIGN KEY(student_id) REFERENCES students(id), FOREIGN KEY(route_id) REFERENCES routes(id))",
    "CREATE TABLE IF NOT EXISTS transport_payments (id INTEGER PRIMARY KEY, student_id INTEGER, amount REAL, date TEXT, receipt_no TEXT, FOREIGN KEY(student_id) REFERENCES students(id))",
    "CREATE TABLE IF NOT EXISTS bus_attendance (id INTEGER PRIMARY KEY, student_id INTEGER, route_id INTEGER, date TEXT, present INTEGER DEFAULT 0, FOREIGN KEY(student_id) REFERENCES students(id), FOREIGN KEY(route_id) REFERENCES routes(id))",
    "CREATE TABLE IF NOT EXISTS contact_messages (id INTEGER PRIMARY KEY, student_id INTEGER, to_role TEXT, to_id INTEGER, subject TEXT, message TEXT, created TEXT, FOREIGN KEY(student_id) REFERENCES students(id))",
    # Announcements (admin broadcasts) with optional scheduling
    "CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY, title TEXT, message TEXT, created TEXT, start_date TEXT, end_date TEXT, active INTEGER DEFAULT 1)",
    # Per-student dismissals for announcements
    "CREATE TABLE IF NOT EXISTS dismissed_announcements (id INTEGER PRIMARY KEY, announcement_id INTEGER NOT NULL, student_id INTEGER NOT NULL, dismissed_at TEXT, FOREIGN KEY(announcement_id) REFERENCES announcements(id), FOREIGN KEY(student_id) REFERENCES students(id))",
]



class Database:
    """Simple SQLite helper for the ERP.

    Responsibilities:
    - create schema (idempotent)
    - provide basic execute/query helpers
    - create/verify users with salted PBKDF2-HMAC-SHA256 password storage
    """

    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cur = self.conn.cursor()
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
        self.conn.commit()

        # Seed default admin if missing
        cur.execute("SELECT COUNT(1) as c FROM users WHERE role='admin'")
        row = cur.fetchone()
        if row and row[0] == 0:
            # store a hashed default admin password
            try:
                self.create_user("admin", "admin", "admin")
            except Exception:
                # ignore unique/insert errors during concurrent runs
                pass

        # Ensure contact_messages has new columns for threading/sender metadata
        try:
            cur.execute("PRAGMA table_info(contact_messages)")
            cols = {r[1] for r in cur.fetchall()}
            if 'sender_role' not in cols:
                cur.execute("ALTER TABLE contact_messages ADD COLUMN sender_role TEXT")
            if 'sender_id' not in cols:
                cur.execute("ALTER TABLE contact_messages ADD COLUMN sender_id INTEGER")
            if 'parent_id' not in cols:
                cur.execute("ALTER TABLE contact_messages ADD COLUMN parent_id INTEGER")
            if 'is_read' not in cols:
                cur.execute("ALTER TABLE contact_messages ADD COLUMN is_read INTEGER DEFAULT 0")
            self.conn.commit()
        except Exception:
            # ignore migration errors on older SQLite setups
            pass

        # Ensure announcements has start_date/end_date if older DB exists
        try:
            cur.execute("PRAGMA table_info(announcements)")
            cols = {r[1] for r in cur.fetchall()}
            if 'start_date' not in cols:
                cur.execute("ALTER TABLE announcements ADD COLUMN start_date TEXT")
            if 'end_date' not in cols:
                cur.execute("ALTER TABLE announcements ADD COLUMN end_date TEXT")
            self.conn.commit()
        except Exception:
            pass

    def _hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
        return f"{binascii.hexlify(salt).decode()}:{binascii.hexlify(dk).decode()}"

    def _verify_password(self, stored: str, provided: str) -> bool:
        try:
            salt_hex, dk_hex = stored.split(":")
            salt = binascii.unhexlify(salt_hex)
            dk = binascii.unhexlify(dk_hex)
            new_dk = hashlib.pbkdf2_hmac("sha256", provided.encode("utf-8"), salt, 100_000)
            return binascii.hexlify(new_dk) == binascii.hexlify(dk)
        except Exception:
            return False

    # User helpers
    def create_user(self, username: str, password: str, role: str, student_id: Optional[int] = None) -> int:
        pw = self._hash_password(password)
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO users (username,password,role,student_id) VALUES (?,?,?,?)",
            (username, pw, role, student_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def verify_user(self, username: str, password: str, role: Optional[str] = None) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        if role:
            cur.execute("SELECT * FROM users WHERE username=? AND role=?", (username, role))
        else:
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if not row:
            return None
        if self._verify_password(row["password"], password):
            return row
        return None

    def execute(self, sql: str, params: Tuple = ()) -> sqlite3.Cursor:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur

    def query(self, sql: str, params: Tuple = ()) -> List[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
