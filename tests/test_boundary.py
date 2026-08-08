import pytest
import sqlite3
import datetime
from backend.services import issue_book, pay_fine, add_book, return_book
from backend.db import get_db

# Keep a reference to the real datetime class to avoid recursion in mock
real_datetime = datetime.datetime

class MockDateTime:
    _counter = 1718000000
    @classmethod
    def now(cls):
        cls._counter += 5  # increment by 5 seconds
        return real_datetime.fromtimestamp(cls._counter)

@pytest.mark.boundary
def test_borrow_limit_boundaries(mocker, book_builder, member_builder):
    mocker.patch('backend.services.datetime.datetime', MockDateTime)
    
    from backend.services import get_config
    # Standard limit = 3
    limit = int(get_config('max_borrow_limit', '3'))
    assert limit == 3
    
    member_id, _ = member_builder()
    lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
    
    # Borrow 1st, 2nd, 3rd books (within limit)
    b1, _ = book_builder()
    b2, _ = book_builder()
    b3, _ = book_builder()
    
    # 2 books: allowed
    issue_book(b1, member_id, issued_by_user=2, user_info=lib_info)
    issue_book(b2, member_id, issued_by_user=2, user_info=lib_info)
    
    # 3rd book: allowed (reaches limit)
    issue_book(b3, member_id, issued_by_user=2, user_info=lib_info)
    
    # 4th book (exceeds limit): must block
    b4, _ = book_builder()
    with pytest.raises(ValueError, match="Member has reached maximum borrowing limit"):
        issue_book(b4, member_id, issued_by_user=2, user_info=lib_info)

@pytest.mark.boundary
def test_fine_payment_boundaries(mocker, loan_builder):
    mocker.patch('backend.services.datetime.datetime', MockDateTime)
    
    # 1. Create a fine by returning a book late
    tx_id, _, _ = loan_builder()
    
    # Set due date to 5 days ago to generate a $5.00 fine
    conn = get_db()
    conn.execute("UPDATE issue_transactions SET due_date = ? WHERE id = ?", (
        (datetime.date.today() - datetime.timedelta(days=5)).isoformat(),
        tx_id
    ))
    conn.commit()
    conn.close()
    
    lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
    ret_res = return_book(tx_id, user_info=lib_info)
    fine_id = ret_res['fine_id']
    assert ret_res['fine_amount'] == 5.00
    
    # Pay negative value -> ValueError
    with pytest.raises(ValueError, match="amount must be greater than 0"):
        pay_fine(fine_id, -1.00, user_info=lib_info)
        
    # Pay 0 -> ValueError
    with pytest.raises(ValueError, match="amount must be greater than 0"):
        pay_fine(fine_id, 0.00, user_info=lib_info)
        
    # Pay $4.50 (Partial) -> allowed
    res_partial = pay_fine(fine_id, 4.50, user_info=lib_info)
    assert res_partial['status'] == 'Partial'
    
    # Pay remaining $0.50 (Paid) -> allowed
    res_paid = pay_fine(fine_id, 0.50, user_info=lib_info)
    assert res_paid['status'] == 'Paid'
    
    # Pay extra (exceeds remaining balance of 0.00) -> ValueError
    with pytest.raises(ValueError, match="exceeds remaining fine balance"):
        pay_fine(fine_id, 0.01, user_info=lib_info)

@pytest.mark.boundary
def test_unpaid_fines_borrow_threshold_boundary(mocker, book_builder, member_builder, loan_builder):
    mocker.patch('backend.services.datetime.datetime', MockDateTime)
    
    # Unpaid fine threshold is $20.00. Borrowing blocked if fine > $20.00.
    member_id, _ = member_builder()
    lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
    
    # 1. Test fine = $20.00 (exactly at limit - allowed)
    tx_id1, book_id1, _ = loan_builder(member_id=member_id)
    conn = get_db()
    conn.execute("UPDATE issue_transactions SET due_date = ? WHERE id = ?", (
        (datetime.date.today() - datetime.timedelta(days=20)).isoformat(),
        tx_id1
    ))
    conn.commit()
    conn.close()
    return_book(tx_id1, user_info=lib_info) # Fine generated: $20.00
    
    b_test1, _ = book_builder()
    # Fine is exactly $20.00, check if allowed (threshold is > 20.0)
    issue_book(b_test1, member_id, issued_by_user=2, user_info=lib_info) # should pass
    
    # 2. Test fine = $20.01 (over limit - blocked)
    # Clear the first issue and return it
    tx_id2 = get_db().execute("SELECT id FROM issue_transactions WHERE book_id = ? AND member_id = ? AND status = 'Issued'", (b_test1, member_id)).fetchone()['id']
    return_book(tx_id2, user_info=lib_info)
    
    # Create another fine to push total unpaid fines to $20.01
    tx_id3, book_id3, _ = loan_builder(member_id=member_id)
    conn = get_db()
    conn.execute("UPDATE issue_transactions SET due_date = ? WHERE id = ?", (
        (datetime.date.today() - datetime.timedelta(days=1)).isoformat(),
        tx_id3
    ))
    conn.commit()
    conn.close()
    return_book(tx_id3, user_info=lib_info) # Fine generated
    
    # Make the aggregate unpaid balance exactly $20.01 so the boundary is exercised.
    conn = get_db()
    conn.execute("DELETE FROM fines")
    conn.execute("INSERT INTO fines (transaction_id, amount, paid_amount, payment_status) VALUES (?, ?, 0.0, 'Unpaid')", (tx_id3, 20.01))
    conn.commit()
    conn.close()
    
    b_test2, _ = book_builder()
    with pytest.raises(ValueError, match=r"outstanding unpaid fines of \$20\.01"):
        issue_book(b_test2, member_id, issued_by_user=2, user_info=lib_info)

@pytest.mark.boundary
def test_book_quantity_boundaries():
    admin_info = {"user_id": 1, "username": "admin", "role": "Admin"}
    # min quantity = 0 (allowed)
    bid = add_book("978-9999999999", "Zero Book", 1, 1, 1, 2024, 0, user_info=admin_info)
    assert bid is not None
    
    # min-1 quantity = -1 (raises ValueError)
    with pytest.raises(ValueError, match="Quantity cannot be negative."):
        add_book("978-9999999998", "Negative Book", 1, 1, 1, 2024, -1, user_info=admin_info)
