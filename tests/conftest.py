import os
import sys
import uuid
import random
import pytest

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set environment variables BEFORE importing backend app modules
os.environ['SECRET_KEY'] = 'test-secret-key-12345'
# Use a fresh file-based SQLite database per test so the suite does not contend with table locks.
INITIAL_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_lms.db"))
os.environ['DATABASE_URL'] = INITIAL_DB_PATH

from backend import db as backend_db
from backend.server import app as flask_app
from backend.db import init_db, get_db
from backend.auth import SESSIONS
import backend.server

# Redirect the module-level DB path to the isolated test database before first use.
backend_db.DB_PATH = INITIAL_DB_PATH

# Autouse fixture to swap in a fresh SQLite database for each test and re-seed clean data.
@pytest.fixture(autouse=True)
def clean_db():
    test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"test_lms_{uuid.uuid4().hex}.db"))
    os.environ['DATABASE_URL'] = test_db_path
    backend_db.DB_PATH = test_db_path
    init_db()

# Autouse fixture to clear login attempts rate limiter and SESSIONS dictionary to prevent state leakage
@pytest.fixture(autouse=True)
def clean_state():
    with backend.server._login_lock:
        backend.server._login_attempts.clear()
    SESSIONS.clear()

@pytest.fixture
def app():
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False
    })
    return flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def login(client):
    def _login(role):
        if role == 'Admin':
            username, password = 'admin', 'Admin@123'
        elif role == 'Librarian':
            username, password = 'librarian', 'Lib@123'
        elif role == 'Member':
            username, password = 'member1', 'Mem@123'
        else:
            raise ValueError(f"Unknown role: {role}")
        
        res = client.post('/api/auth/login', json={'username': username, 'password': password})
        assert res.status_code == 200
        return res.json['token']
    return _login

# Helpers to generate unique constraints
def unique_isbn():
    return f"978-{random.randint(1000000000, 9999999999)}"

def unique_email():
    return f"test-{uuid.uuid4()}@example.com"

@pytest.fixture
def book_builder():
    def _build(title="Test Book", isbn=None, total_quantity=5, author_id=1, publisher_id=1, category_id=1):
        from backend.services import add_book
        admin_info = {"user_id": 1, "username": "admin", "role": "Admin"}
        isbn = isbn or unique_isbn()
        book_id = add_book(
            isbn=isbn,
            title=title,
            author_id=author_id,
            publisher_id=publisher_id,
            category_id=category_id,
            publication_year=2024,
            total_quantity=total_quantity,
            user_info=admin_info
        )
        return book_id, isbn
    return _build

@pytest.fixture
def member_builder():
    def _build(name="Test Member", email=None, phone="+1-555-0000", user_id=None):
        from backend.services import create_member
        admin_info = {"user_id": 1, "username": "admin", "role": "Admin"}
        email = email or unique_email()
        member_id = create_member(
            name=name,
            email=email,
            phone=phone,
            user_id=user_id,
            user_info=admin_info
        )
        # Fetch generated member code
        conn = get_db()
        row = conn.execute("SELECT member_id FROM members WHERE id = ?", (member_id,)).fetchone()
        conn.close()
        return member_id, row['member_id']
    return _build

@pytest.fixture
def loan_builder(book_builder, member_builder):
    def _build(book_id=None, member_id=None):
        from backend.services import issue_book
        lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
        if not book_id:
            book_id, _ = book_builder()
        if not member_id:
            member_id, _ = member_builder()
        res = issue_book(book_id, member_id, issued_by_user=2, user_info=lib_info)
        return res['transaction_id'], book_id, member_id
    return _build

@pytest.fixture
def return_builder(loan_builder):
    def _build(tx_id=None):
        from backend.services import return_book
        lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
        if not tx_id:
            tx_id, _, _ = loan_builder()
        res = return_book(tx_id, user_info=lib_info)
        return res
    return _build

@pytest.fixture
def captured_templates(app):
    from flask import template_rendered
    recorded = []
    def record(sender, template, context, **extra):
        recorded.append((template, context))
    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)
