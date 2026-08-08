import sqlite3
import datetime
import csv
import io
from backend.db import get_db

# Audit Log Helper
def log_audit(user_id, username, action, details):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_logs (user_id, username, action, details) VALUES (?, ?, ?, ?)",
        (user_id, username, action, details)
    )
    conn.commit()
    conn.close()

# Config Service
def get_config(key, default_val=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default_val

def update_config(key, value, user_info):
    conn = get_db()
    conn.execute("UPDATE system_config SET value = ? WHERE key = ?", (value, key))
    conn.commit()
    conn.close()
    log_audit(user_info['user_id'], user_info['username'], "UPDATE_CONFIG", f"Updated {key} to {value}")

def get_all_config():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value, description FROM system_config")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# Auth & User Service
def get_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, status, created_at FROM users ORDER BY id DESC")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return users

def create_user(username, password_hash, role, status='Active', user_info=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        raise ValueError("Username already exists.")
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, status) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, status)
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "CREATE_USER", f"Created user {username} with role {role}")
    return user_id

def update_user(user_id, role, status, password_hash=None, user_info=None):
    conn = get_db()
    if password_hash:
        conn.execute("UPDATE users SET role = ?, status = ?, password_hash = ? WHERE id = ?", (role, status, password_hash, user_id))
    else:
        conn.execute("UPDATE users SET role = ?, status = ? WHERE id = ?", (role, status, user_id))
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "UPDATE_USER", f"Updated user ID {user_id} (Role: {role}, Status: {status})")

# Member Service
def get_members(search_query=None):
    conn = get_db()
    cursor = conn.cursor()
    if search_query:
        q = f"%{search_query}%"
        cursor.execute(
            """SELECT m.*, u.username 
               FROM members m 
               LEFT JOIN users u ON m.user_id = u.id 
               WHERE m.member_id LIKE ? OR m.name LIKE ? OR m.email LIKE ? OR m.phone LIKE ?
               ORDER BY m.id DESC""",
            (q, q, q, q)
        )
    else:
        cursor.execute(
            """SELECT m.*, u.username 
               FROM members m 
               LEFT JOIN users u ON m.user_id = u.id 
               ORDER BY m.id DESC"""
        )
    members = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return members

def get_member_by_user_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM members WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_member(name, email, phone, user_id=None, user_info=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM members WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise ValueError("Member email already registered.")
    
    # Auto generate member_id: MEM-1002, etc.
    cursor.execute("SELECT MAX(id) as max_id FROM members")
    max_id = cursor.fetchone()['max_id'] or 1000
    member_id_str = f"MEM-{max_id + 1001}"
    
    cursor.execute(
        "INSERT INTO members (member_id, name, email, phone, user_id, status) VALUES (?, ?, ?, ?, ?, 'Active')",
        (member_id_str, name, email, phone, user_id)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "CREATE_MEMBER", f"Created member {member_id_str} ({name})")
    return new_id

def update_member(member_id, name, email, phone, status, user_info=None):
    conn = get_db()
    conn.execute(
        "UPDATE members SET name = ?, email = ?, phone = ?, status = ? WHERE id = ?",
        (name, email, phone, status, member_id)
    )
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "UPDATE_MEMBER", f"Updated member ID {member_id}")

# Catalog Service (Authors, Publishers, Categories, Books)
def get_authors():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM authors ORDER BY name ASC")
    res = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return res

def add_author(name, bio="", user_info=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO authors (name, bio) VALUES (?, ?)", (name, bio))
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "ADD_AUTHOR", f"Added author {name}")

def get_publishers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM publishers ORDER BY name ASC")
    res = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return res

def add_publisher(name, address="", user_info=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO publishers (name, address) VALUES (?, ?)", (name, address))
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "ADD_PUBLISHER", f"Added publisher {name}")

def get_categories():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM categories ORDER BY name ASC")
    res = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return res

def add_category(name, description="", user_info=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO categories (name, description) VALUES (?, ?)", (name, description))
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "ADD_CATEGORY", f"Added category {name}")

def get_books(title_q=None, author_q=None, isbn_q=None, category_id=None, availability=None):
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT b.*, a.name as author_name, p.name as publisher_name, c.name as category_name
        FROM books b
        JOIN authors a ON b.author_id = a.id
        JOIN publishers p ON b.publisher_id = p.id
        JOIN categories c ON b.category_id = c.id
        WHERE b.status = 'Active'
    """
    params = []
    if title_q:
        query += " AND b.title LIKE ?"
        params.append(f"%{title_q}%")
    if author_q:
        query += " AND a.name LIKE ?"
        params.append(f"%{author_q}%")
    if isbn_q:
        query += " AND b.isbn LIKE ?"
        params.append(f"%{isbn_q}%")
    if category_id:
        query += " AND b.category_id = ?"
        params.append(category_id)
    if availability == 'Available':
        query += " AND b.available_quantity > 0"
    elif availability == 'Unavailable':
        query += " AND b.available_quantity = 0"
        
    query += " ORDER BY b.id DESC"
    cursor.execute(query, params)
    books = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return books

def add_book(isbn, title, author_id, publisher_id, category_id, publication_year, total_quantity, user_info=None):
    if total_quantity < 0:
        raise ValueError("Quantity cannot be negative.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM books WHERE isbn = ?", (isbn,))
    if cursor.fetchone():
        conn.close()
        raise ValueError("ISBN already exists in catalog.")
    cursor.execute(
        """INSERT INTO books 
           (isbn, title, author_id, publisher_id, category_id, publication_year, total_quantity, available_quantity, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active')""",
        (isbn, title, author_id, publisher_id, category_id, publication_year, total_quantity, total_quantity)
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "ADD_BOOK", f"Added book '{title}' (ISBN: {isbn})")
    return new_id

def update_book(book_id, title, author_id, publisher_id, category_id, publication_year, total_quantity, status, user_info=None):
    if total_quantity < 0:
        raise ValueError("Total quantity cannot be negative.")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT total_quantity, available_quantity FROM books WHERE id = ?", (book_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Book not found.")
    
    diff = total_quantity - row['total_quantity']
    new_available = row['available_quantity'] + diff
    if new_available < 0:
        conn.close()
        raise ValueError("Cannot reduce total quantity below currently issued count.")
    
    cursor.execute(
        """UPDATE books 
           SET title = ?, author_id = ?, publisher_id = ?, category_id = ?, publication_year = ?, 
               total_quantity = ?, available_quantity = ?, status = ?
           WHERE id = ?""",
        (title, author_id, publisher_id, category_id, publication_year, total_quantity, new_available, status, book_id)
    )
    conn.commit()
    conn.close()
    if user_info:
        log_audit(user_info['user_id'], user_info['username'], "UPDATE_BOOK", f"Updated book ID {book_id}")

# Circulation Service (Issue, Return, Due-Date, Overdue Fines)
def issue_book(book_id, member_id, issued_by_user, user_info):
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        # 1. Verify Member active status (BR-01)
        cursor.execute("SELECT id, status, name, member_id FROM members WHERE id = ?", (member_id,))
        member = cursor.fetchone()
        if not member:
            raise ValueError("Member record not found.")
        if member['status'] != 'Active':
            raise ValueError(f"Member '{member['name']}' ({member['member_id']}) is Inactive and cannot borrow books (BR-01).")
        
        # 2. Verify Member borrowing limit (BR-03)
        max_limit = int(get_config('max_borrow_limit', '3'))
        cursor.execute("SELECT COUNT(*) as current_issues FROM issue_transactions WHERE member_id = ? AND status = 'Issued'", (member_id,))
        active_issues = cursor.fetchone()['current_issues']
        if active_issues >= max_limit:
            raise ValueError(f"Member has reached maximum borrowing limit of {max_limit} books (BR-03).")
        
        # 3. Verify Member has unpaid fines above threshold (BR-08)
        cursor.execute(
            """SELECT SUM(f.amount - f.paid_amount) as unpaid 
               FROM fines f 
               JOIN issue_transactions t ON f.transaction_id = t.id 
               WHERE t.member_id = ? AND f.payment_status != 'Paid'""", 
            (member_id,)
        )
        unpaid_row = cursor.fetchone()
        unpaid_total = unpaid_row['unpaid'] if unpaid_row['unpaid'] else 0.0
        if unpaid_total > 20.0: # threshold USD 20
            raise ValueError(f"Member has outstanding unpaid fines of ${unpaid_total:.2f}. Settlement required before borrowing.")

        # 4. Verify Book availability (BR-02)
        cursor.execute("SELECT id, title, available_quantity, status FROM books WHERE id = ?", (book_id,))
        book = cursor.fetchone()
        if not book or book['status'] != 'Active':
            raise ValueError("Book is inactive or not found.")
        if book['available_quantity'] <= 0:
            raise ValueError(f"Book '{book['title']}' has no available copies to issue (BR-02). Reserve it instead.")

        # 5. Atomic Update: Decrement inventory (BR-07) and create transaction (NFR-10, NFR-11)
        cursor.execute("UPDATE books SET available_quantity = available_quantity - 1 WHERE id = ?", (book_id,))
        
        borrow_days = int(get_config('borrow_period_days', '14'))
        today = datetime.date.today()
        due_date = today + datetime.timedelta(days=borrow_days)
        tx_code = f"TXN-{int(datetime.datetime.now().timestamp())}"

        cursor.execute(
            """INSERT INTO issue_transactions 
               (transaction_code, book_id, member_id, issued_by, issue_date, due_date, status) 
               VALUES (?, ?, ?, ?, ?, ?, 'Issued')""",
            (tx_code, book_id, member_id, issued_by_user, today.isoformat(), due_date.isoformat())
        )
        tx_id = cursor.lastrowid
        conn.commit()

        log_audit(user_info['user_id'], user_info['username'], "ISSUE_BOOK", f"Issued '{book['title']}' to {member['name']} ({member['member_id']}). Due date: {due_date.isoformat()}")
        return {"transaction_id": tx_id, "transaction_code": tx_code, "due_date": due_date.isoformat()}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def return_book(transaction_id, user_info):
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        # Load transaction details
        cursor.execute(
            """SELECT t.*, b.title, b.id as book_id, m.name as member_name, m.member_id as member_code
               FROM issue_transactions t 
               JOIN books b ON t.book_id = b.id 
               JOIN members m ON t.member_id = m.id 
               WHERE t.id = ?""",
            (transaction_id,)
        )
        tx = cursor.fetchone()
        if not tx:
            raise ValueError("Transaction record not found.")
        if tx['status'] == 'Returned':
            raise ValueError("This book has already been returned.")

        return_date = datetime.date.today()
        due_date = datetime.date.fromisoformat(tx['due_date'])
        
        # Calculate Fine (BR-05)
        overdue_days = (return_date - due_date).days
        fine_amount = 0.0
        fine_id = None
        if overdue_days > 0:
            rate = float(get_config('overdue_fine_rate', '1.00'))
            fine_amount = round(overdue_days * rate, 2)
            
            # Create fine entry
            cursor.execute(
                "INSERT INTO fines (transaction_id, amount, paid_amount, payment_status) VALUES (?, ?, 0.0, 'Unpaid')",
                (transaction_id, fine_amount)
            )
            fine_id = cursor.lastrowid

        # Update transaction status and increment inventory (BR-06)
        cursor.execute("UPDATE issue_transactions SET return_date = ?, status = 'Returned' WHERE id = ?", (return_date.isoformat(), transaction_id))
        cursor.execute("UPDATE books SET available_quantity = available_quantity + 1 WHERE id = ?", (tx['book_id'],))
        
        conn.commit()

        log_audit(user_info['user_id'], user_info['username'], "RETURN_BOOK", f"Returned '{tx['title']}' from {tx['member_name']}. Overdue days: {max(0, overdue_days)}, Fine: ${fine_amount:.2f}")
        return {
            "transaction_id": transaction_id,
            "return_date": return_date.isoformat(),
            "overdue_days": max(0, overdue_days),
            "fine_amount": fine_amount,
            "fine_id": fine_id
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_transactions(member_id=None, status=None, search_q=None):
    # Automatically update transaction status to 'Overdue' if due_date < today and status = 'Issued'
    conn = get_db()
    cursor = conn.cursor()
    today_str = datetime.date.today().isoformat()
    cursor.execute("UPDATE issue_transactions SET status = 'Overdue' WHERE status = 'Issued' AND due_date < ?", (today_str,))
    conn.commit()

    query = """
        SELECT t.*, b.title as book_title, b.isbn, m.name as member_name, m.member_id as member_code, u.username as issued_by_user,
               f.amount as fine_amount, f.payment_status as fine_payment_status, f.id as fine_id
        FROM issue_transactions t
        JOIN books b ON t.book_id = b.id
        JOIN members m ON t.member_id = m.id
        JOIN users u ON t.issued_by = u.id
        LEFT JOIN fines f ON t.id = f.transaction_id
        WHERE 1=1
    """
    params = []
    if member_id:
        query += " AND t.member_id = ?"
        params.append(member_id)
    if status:
        query += " AND t.status = ?"
        params.append(status)
    if search_q:
        q = f"%{search_q}%"
        query += " AND (t.transaction_code LIKE ? OR b.title LIKE ? OR m.name LIKE ? OR m.member_id LIKE ?)"
        params.extend([q, q, q, q])

    query += " ORDER BY t.id DESC"
    cursor.execute(query, params)
    txs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return txs

# Reservation Service
def reserve_book(book_id, member_id, user_info):
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Check duplicate active reservation (FR-49)
    cursor.execute("SELECT id FROM reservations WHERE book_id = ? AND member_id = ? AND status = 'Active'", (book_id, member_id))
    if cursor.fetchone():
        conn.close()
        raise ValueError("Member already has an active reservation for this book.")
    
    # 2. Check member status
    cursor.execute("SELECT status FROM members WHERE id = ?", (member_id,))
    mem = cursor.fetchone()
    if not mem or mem['status'] != 'Active':
        conn.close()
        raise ValueError("Member is inactive or not found.")
    
    cursor.execute(
        "INSERT INTO reservations (book_id, member_id, status) VALUES (?, ?, 'Active')",
        (book_id, member_id)
    )
    res_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log_audit(user_info['user_id'], user_info['username'], "RESERVE_BOOK", f"Placed reservation ID {res_id} for book ID {book_id}")
    return res_id

def cancel_reservation(reservation_id, user_info):
    conn = get_db()
    cursor = conn.cursor()

    # Load the reservation to verify ownership (SECURITY: prevent privilege escalation)
    cursor.execute(
        "SELECT r.id, r.member_id, m.user_id FROM reservations r JOIN members m ON r.member_id = m.id WHERE r.id = ?",
        (reservation_id,)
    )
    reservation = cursor.fetchone()
    if not reservation:
        conn.close()
        raise ValueError("Reservation not found.")

    # Members can only cancel their own reservations
    if user_info['role'] == 'Member':
        if reservation['user_id'] != user_info['user_id']:
            conn.close()
            raise PermissionError("You are not authorized to cancel this reservation.")

    conn.execute("UPDATE reservations SET status = 'Cancelled' WHERE id = ?", (reservation_id,))
    conn.commit()
    conn.close()
    log_audit(user_info['user_id'], user_info['username'], "CANCEL_RESERVATION", f"Cancelled reservation ID {reservation_id}")

def get_reservations(member_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT r.*, b.title as book_title, b.isbn, m.name as member_name, m.member_id as member_code
        FROM reservations r
        JOIN books b ON r.book_id = b.id
        JOIN members m ON r.member_id = m.id
        WHERE 1=1
    """
    params = []
    if member_id:
        query += " AND r.member_id = ?"
        params.append(member_id)
    query += " ORDER BY r.id DESC"
    cursor.execute(query, params)
    res = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return res

# Fine Management Service
def get_fines(member_id=None):
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT f.*, t.transaction_code, b.title as book_title, m.name as member_name, m.member_id as member_code
        FROM fines f
        JOIN issue_transactions t ON f.transaction_id = t.id
        JOIN books b ON t.book_id = b.id
        JOIN members m ON t.member_id = m.id
        WHERE 1=1
    """
    params = []
    if member_id:
        query += " AND t.member_id = ?"
        params.append(member_id)
    query += " ORDER BY f.id DESC"
    cursor.execute(query, params)
    fines = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return fines

def pay_fine(fine_id, amount_paid, user_info):
    if amount_paid <= 0:
        raise ValueError("Payment amount must be greater than 0.")
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fines WHERE id = ?", (fine_id,))
        fine = cursor.fetchone()
        if not fine:
            raise ValueError("Fine record not found.")
        
        remaining = fine['amount'] - fine['paid_amount']
        if amount_paid > remaining:
            raise ValueError(f"Payment amount (${amount_paid:.2f}) exceeds remaining fine balance (${remaining:.2f}).")
        
        new_paid = fine['paid_amount'] + amount_paid
        status = 'Paid' if new_paid >= fine['amount'] else 'Partial'

        cursor.execute("UPDATE fines SET paid_amount = ?, payment_status = ? WHERE id = ?", (new_paid, status, fine_id))
        cursor.execute(
            "INSERT INTO fine_payments (fine_id, amount_paid, collected_by) VALUES (?, ?, ?)",
            (fine_id, amount_paid, user_info['user_id'])
        )
        conn.commit()
        log_audit(user_info['user_id'], user_info['username'], "PAY_FINE", f"Collected ${amount_paid:.2f} payment for fine ID {fine_id}. Status: {status}")
        return {"fine_id": fine_id, "paid_amount": new_paid, "status": status}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Audit Log Service
def get_audit_logs():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200")
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs

# Reports Engine (Inventory, Issued, Overdue, Member History)
def get_reports_summary():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_books, SUM(total_quantity) as total_copies, SUM(available_quantity) as available_copies FROM books WHERE status = 'Active'")
    inv = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as active_members FROM members WHERE status = 'Active'")
    members_cnt = cursor.fetchone()['active_members']
    
    cursor.execute("SELECT COUNT(*) as currently_issued FROM issue_transactions WHERE status = 'Issued'")
    issued_cnt = cursor.fetchone()['currently_issued']

    today_str = datetime.date.today().isoformat()
    cursor.execute("SELECT COUNT(*) as overdue_count FROM issue_transactions WHERE (status = 'Overdue' OR (status = 'Issued' AND due_date < ?))", (today_str,))
    overdue_cnt = cursor.fetchone()['overdue_count']

    cursor.execute("SELECT SUM(amount - paid_amount) as total_unpaid_fines FROM fines WHERE payment_status != 'Paid'")
    fines_sum = cursor.fetchone()['total_unpaid_fines'] or 0.0

    conn.close()
    return {
        "total_books": inv['total_books'] or 0,
        "total_copies": inv['total_copies'] or 0,
        "available_copies": inv['available_copies'] or 0,
        "active_members": members_cnt,
        "currently_issued": issued_cnt,
        "overdue_count": overdue_cnt,
        "total_unpaid_fines": fines_sum
    }

def export_report_csv(report_type):
    conn = get_db()
    cursor = conn.cursor()
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'inventory':
        cursor.execute(
            """SELECT b.id, b.isbn, b.title, a.name as author, p.name as publisher, c.name as category, 
                      b.publication_year, b.total_quantity, b.available_quantity, b.status 
               FROM books b 
               JOIN authors a ON b.author_id = a.id 
               JOIN publishers p ON b.publisher_id = p.id 
               JOIN categories c ON b.category_id = c.id"""
        )
        writer.writerow(['Book ID', 'ISBN', 'Title', 'Author', 'Publisher', 'Category', 'Year', 'Total Copies', 'Available Copies', 'Status'])
        for r in cursor.fetchall():
            writer.writerow(list(r))

    elif report_type == 'overdue':
        today_str = datetime.date.today().isoformat()
        cursor.execute(
            """SELECT t.transaction_code, m.member_id, m.name as member_name, m.email, b.title as book_title, 
                      t.issue_date, t.due_date, 
                      (JULIANDAY('now') - JULIANDAY(t.due_date)) as days_overdue
               FROM issue_transactions t 
               JOIN members m ON t.member_id = m.id 
               JOIN books b ON t.book_id = b.id 
               WHERE t.status = 'Issued' AND t.due_date < ?""",
            (today_str,)
        )
        writer.writerow(['Transaction Code', 'Member ID', 'Member Name', 'Email', 'Book Title', 'Issue Date', 'Due Date', 'Days Overdue'])
        for r in cursor.fetchall():
            row = list(r)
            row[-1] = max(0, int(row[-1]))
            writer.writerow(row)

    elif report_type == 'issued':
        cursor.execute(
            """SELECT t.transaction_code, m.member_id, m.name as member_name, b.title as book_title, b.isbn, t.issue_date, t.due_date, t.status
               FROM issue_transactions t 
               JOIN members m ON t.member_id = m.id 
               JOIN books b ON t.book_id = b.id 
               WHERE t.status IN ('Issued', 'Overdue')"""
        )
        writer.writerow(['Transaction Code', 'Member ID', 'Member Name', 'Book Title', 'ISBN', 'Issue Date', 'Due Date', 'Status'])
        for r in cursor.fetchall():
            writer.writerow(list(r))

    conn.close()
    return output.getvalue()
