-- LMS Database Schema (SQLite compatible)
PRAGMA foreign_keys = ON;

-- Users table (System Users: Admin, Librarian, Member logins)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Admin', 'Librarian', 'Member')),
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Members table (Library Cardholders)
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    user_id INTEGER UNIQUE,
    registration_date DATE DEFAULT (DATE('now')),
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Authors table
CREATE TABLE IF NOT EXISTS authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    bio TEXT
);

-- Publishers table
CREATE TABLE IF NOT EXISTS publishers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    address TEXT
);

-- Categories table
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT
);

-- Books table
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    publisher_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    publication_year INTEGER,
    total_quantity INTEGER NOT NULL CHECK (total_quantity >= 0),
    available_quantity INTEGER NOT NULL CHECK (available_quantity >= 0 AND available_quantity <= total_quantity),
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES authors(id),
    FOREIGN KEY (publisher_id) REFERENCES publishers(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Issue Transactions table
CREATE TABLE IF NOT EXISTS issue_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_code TEXT UNIQUE NOT NULL,
    book_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    issued_by INTEGER NOT NULL,
    issue_date DATE NOT NULL DEFAULT (DATE('now')),
    due_date DATE NOT NULL,
    return_date DATE,
    status TEXT NOT NULL DEFAULT 'Issued' CHECK (status IN ('Issued', 'Returned', 'Overdue', 'Cancelled')),
    FOREIGN KEY (book_id) REFERENCES books(id),
    FOREIGN KEY (member_id) REFERENCES members(id),
    FOREIGN KEY (issued_by) REFERENCES users(id)
);

-- Reservations table
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    reservation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Fulfilled', 'Cancelled', 'Expired')),
    FOREIGN KEY (book_id) REFERENCES books(id),
    FOREIGN KEY (member_id) REFERENCES members(id)
);

-- Fines table
CREATE TABLE IF NOT EXISTS fines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER UNIQUE NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    paid_amount REAL NOT NULL DEFAULT 0.0 CHECK (paid_amount >= 0 AND paid_amount <= amount),
    payment_status TEXT NOT NULL DEFAULT 'Unpaid' CHECK (payment_status IN ('Unpaid', 'Partial', 'Paid')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES issue_transactions(id)
);

-- Fine Payments history table
CREATE TABLE IF NOT EXISTS fine_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fine_id INTEGER NOT NULL,
    amount_paid REAL NOT NULL CHECK (amount_paid > 0),
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    collected_by INTEGER NOT NULL,
    FOREIGN KEY (fine_id) REFERENCES fines(id),
    FOREIGN KEY (collected_by) REFERENCES users(id)
);

-- System Configuration table
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT
);

-- Audit Logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for high-performance lookup (NFR-02)
CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_members_member_id ON members(member_id);
CREATE INDEX IF NOT EXISTS idx_members_email ON members(email);
CREATE INDEX IF NOT EXISTS idx_transactions_status ON issue_transactions(status);
CREATE INDEX IF NOT EXISTS idx_transactions_due_date ON issue_transactions(due_date);
