import pytest
import sqlite3
from backend.db import get_db

@pytest.mark.unit
def test_user_role_check_constraint():
    conn = get_db()
    cursor = conn.cursor()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
                ("baduser", "hash", "SuperUser", "Active")
            )
    finally:
        conn.close()

@pytest.mark.unit
def test_user_status_check_constraint():
    conn = get_db()
    cursor = conn.cursor()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
                ("baduser2", "hash", "Member", "Suspended")
            )
    finally:
        conn.close()

@pytest.mark.unit
def test_username_unique_constraint():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
            ("dupuser", "hash", "Member", "Active")
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
                ("dupuser", "hash2", "Member", "Active")
            )
    finally:
        conn.close()

@pytest.mark.unit
def test_member_email_unique_constraint(member_builder):
    member_builder(name="Member A", email="dup@example.com")
    conn = get_db()
    cursor = conn.cursor()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO members (member_id, name, email, phone, user_id, status) VALUES (?, ?, ?, ?, ?, ?)",
                ("MEM-9999", "Member B", "dup@example.com", None, None, "Active")
            )
            conn.commit()
    finally:
        conn.close()

@pytest.mark.unit
def test_book_quantity_check_constraint():
    conn = get_db()
    cursor = conn.cursor()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """INSERT INTO books 
                   (isbn, title, author_id, publisher_id, category_id, publication_year, total_quantity, available_quantity, status)
                   VALUES (?, ?, 1, 1, 1, 2024, -1, 0, 'Active')""",
                ("978-0111111111", "Negative Book")
            )
    finally:
        conn.close()

@pytest.mark.unit
def test_book_available_qty_check_constraint():
    conn = get_db()
    cursor = conn.cursor()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """INSERT INTO books 
                   (isbn, title, author_id, publisher_id, category_id, publication_year, total_quantity, available_quantity, status)
                   VALUES (?, ?, 1, 1, 1, 2024, 5, 6, 'Active')""",
                ("978-0111111111", "Too Available Book")
            )
    finally:
        conn.close()

@pytest.mark.unit
def test_cascade_delete_user_sets_member_user_id_null():
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Create user
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
            ("test_cascade_user", "hash", "Member", "Active")
        )
        user_id = cursor.lastrowid
        
        # Create member linked to user
        cursor.execute(
            "INSERT INTO members (member_id, name, email, phone, user_id, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("MEM-9988", "Cascade Member", "cascade@example.com", "123", user_id, "Active")
        )
        member_id = cursor.lastrowid
        conn.commit()
        
        # Delete user
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        
        # Check if member user_id is set to NULL
        cursor.execute("SELECT user_id FROM members WHERE id = ?", (member_id,))
        row = cursor.fetchone()
        assert row['user_id'] is None
    finally:
        conn.close()
