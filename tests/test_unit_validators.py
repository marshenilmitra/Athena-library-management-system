import pytest
from backend.services import add_book, create_member, pay_fine, issue_book, reserve_book

@pytest.mark.unit
@pytest.mark.parametrize("quantity,expected_err", [
    (-1, "Quantity cannot be negative."),
    (-100, "Quantity cannot be negative.")
])
def test_add_book_negative_quantity_validation(quantity, expected_err):
    admin_info = {"user_id": 1, "username": "admin", "role": "Admin"}
    with pytest.raises(ValueError, match=expected_err):
        add_book(
            isbn="978-1111111111",
            title="Book Title",
            author_id=1,
            publisher_id=1,
            category_id=1,
            publication_year=2024,
            total_quantity=quantity,
            user_info=admin_info
        )

@pytest.mark.unit
def test_pay_fine_negative_amount_validation():
    user_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
    with pytest.raises(ValueError, match="Payment amount must be greater than 0."):
        pay_fine(fine_id=1, amount_paid=-5.00, user_info=user_info)
    with pytest.raises(ValueError, match="Payment amount must be greater than 0."):
        pay_fine(fine_id=1, amount_paid=0.00, user_info=user_info)

@pytest.mark.unit
def test_issue_inactive_member_validation(book_builder, member_builder):
    from backend.db import get_db
    book_id, _ = book_builder(total_quantity=2)
    member_id, _ = member_builder()
    
    # Deactivate the member
    conn = get_db()
    conn.execute("UPDATE members SET status = 'Inactive' WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()
    
    lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
    with pytest.raises(ValueError, match="is Inactive and cannot borrow books"):
        issue_book(book_id, member_id, issued_by_user=2, user_info=lib_info)

@pytest.mark.unit
def test_issue_out_of_stock_book_validation(book_builder, member_builder):
    book_id, _ = book_builder(total_quantity=0)
    member_id, _ = member_builder()
    lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
    with pytest.raises(ValueError, match="has no available copies to issue"):
        issue_book(book_id, member_id, issued_by_user=2, user_info=lib_info)
