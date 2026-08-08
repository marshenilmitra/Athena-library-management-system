import sqlite3
import os
from backend.auth import hash_password

# DB_PATH can be overridden by DATABASE_URL environment variable for cloud deployments.
# On Render, set DATABASE_URL to a path on a persistent disk (e.g., /var/data/lms.db).
_default_db_path = os.path.join(os.path.dirname(__file__), "lms.db")
DB_PATH = os.environ.get('DATABASE_URL', _default_db_path)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_db():
    """Get a database connection with foreign key support enabled and dictionary row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode=WAL;")  # WAL mode improves concurrent read performance
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize schema and seed initial configuration and default admin/librarian/member accounts."""
    conn = get_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()

    # Seed Default System Settings if not exists
    default_config = [
        ('max_borrow_limit', '3', 'Maximum books a member can borrow at once'),
        ('borrow_period_days', '14', 'Standard borrowing period in days'),
        ('overdue_fine_rate', '1.00', 'Fine amount per overdue day in USD')
    ]
    for key, value, desc in default_config:
        conn.execute(
            "INSERT OR IGNORE INTO system_config (key, value, description) VALUES (?, ?, ?)",
            (key, value, desc)
        )
    conn.commit()

    # Seed Default Users if not exists.
    # In production, override passwords via ADMIN_PASSWORD / LIBRARIAN_PASSWORD env vars.
    cursor = conn.cursor()
    admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin@123')
    librarian_password = os.environ.get('LIBRARIAN_PASSWORD', 'Lib@123')
    member_password = os.environ.get('MEMBER_PASSWORD', 'Mem@123')

    # 1. Admin
    cursor.execute("SELECT id FROM users WHERE username = ?", ('admin',))
    if not cursor.fetchone():
        admin_pwd = hash_password(admin_password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
            ('admin', admin_pwd, 'Admin', 'Active')
        )

    # 2. Librarian
    cursor.execute("SELECT id FROM users WHERE username = ?", ('librarian',))
    if not cursor.fetchone():
        lib_pwd = hash_password(librarian_password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
            ('librarian', lib_pwd, 'Librarian', 'Active')
        )

    # 3. Default Member user & record
    cursor.execute("SELECT id FROM users WHERE username = ?", ('member1',))
    if not cursor.fetchone():
        mem_pwd = hash_password(member_password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
            ('member1', mem_pwd, 'Member', 'Active')
        )
        mem_user_id = cursor.lastrowid
        cursor.execute(
            "INSERT OR IGNORE INTO members (member_id, name, email, phone, user_id, status) VALUES (?, ?, ?, ?, ?, ?)",
            ('MEM-1001', 'John Doe', 'john.doe@example.com', '+1-555-0199', mem_user_id, 'Active')
        )

    # Seed Sample Authors, Publishers, Categories, Books if catalog is empty
    cursor.execute("SELECT COUNT(*) as count FROM books")
    if cursor.fetchone()['count'] == 0:
        authors = [
            ('Robert C. Martin', 'Clean Code author'),
            ('Andrew Hunt', 'Pragmatic Programmer author'),
            ('Erich Gamma', 'Design Patterns author')
        ]
        for name, bio in authors:
            cursor.execute("INSERT OR IGNORE INTO authors (name, bio) VALUES (?, ?)", (name, bio))

        publishers = [
            ('Prentice Hall', 'USA'),
            ('Addison-Wesley', 'USA'),
            ("O'Reilly Media", 'USA')
        ]
        for name, addr in publishers:
            cursor.execute("INSERT OR IGNORE INTO publishers (name, address) VALUES (?, ?)", (name, addr))

        categories = [
            ('Software Engineering', 'Books about software design and best practices'),
            ('Computer Science', 'Foundational CS topics'),
            ('Data Science', 'Machine Learning & Analytics')
        ]
        for name, desc in categories:
            cursor.execute("INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)", (name, desc))

        conn.commit()

        # Get inserted IDs
        cursor.execute("SELECT id FROM authors WHERE name = 'Robert C. Martin'")
        author1_id = cursor.fetchone()['id']
        cursor.execute("SELECT id FROM authors WHERE name = 'Andrew Hunt'")
        author2_id = cursor.fetchone()['id']

        cursor.execute("SELECT id FROM publishers WHERE name = 'Prentice Hall'")
        pub1_id = cursor.fetchone()['id']
        cursor.execute("SELECT id FROM publishers WHERE name = 'Addison-Wesley'")
        pub2_id = cursor.fetchone()['id']

        cursor.execute("SELECT id FROM categories WHERE name = 'Software Engineering'")
        cat1_id = cursor.fetchone()['id']

        books = [
            ('978-0132350884', 'Clean Code: A Handbook of Agile Software Craftsmanship', author1_id, pub1_id, cat1_id, 2008, 5, 5),
            ('978-0201616224', 'The Pragmatic Programmer: Your Journey To Mastery', author2_id, pub2_id, cat1_id, 1999, 3, 3)
        ]
        for isbn, title, aid, pid, cid, year, total_q, avail_q in books:
            cursor.execute(
                """INSERT INTO books
                   (isbn, title, author_id, publisher_id, category_id, publication_year, total_quantity, available_quantity)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (isbn, title, aid, pid, cid, year, total_q, avail_q)
            )

    conn.commit()
    conn.close()
