import pytest
import datetime
from backend.services import return_book

@pytest.mark.unit
@pytest.mark.parametrize("due,ret,rate,expected_days,expected_fine", [
    # Returned on time
    ("2024-01-15", "2024-01-15", 1.00, 0, 0.0),
    # Returned early
    ("2024-01-15", "2024-01-14", 1.00, 0, 0.0),
    # 1 day late
    ("2024-01-15", "2024-01-16", 1.00, 1, 1.0),
    # 10 days late with different fine rate
    ("2024-01-15", "2024-01-25", 1.50, 10, 15.0),
    # Month-end rollover (due Jan 30, ret Feb 2) -> 3 days
    ("2024-01-30", "2024-02-02", 1.00, 3, 3.0),
    # Year-end rollover (due Dec 30, ret Jan 2) -> 3 days
    ("2024-12-30", "2025-01-02", 1.00, 3, 3.0),
    # Leap year rollover (2024 is leap, Feb has 29 days)
    # due Feb 28, ret Mar 1 -> Feb 29, Mar 1 -> 2 days late
    ("2024-02-28", "2024-03-01", 1.00, 2, 2.0),
    # Non-leap year rollover (2023 is not leap, Feb has 28 days)
    # due Feb 28, ret Mar 1 -> 1 day late
    ("2023-02-28", "2023-03-01", 1.00, 1, 1.0),
    # Rounding fine amount (e.g., $1.255/day overdue)
    ("2024-01-15", "2024-01-17", 1.255, 2, 2.51) # 2 * 1.255 = 2.51
])
def test_fine_calculations(mocker, loan_builder, due, ret, rate, expected_days, expected_fine):
    from backend.db import get_db
    # 1. Update config fine rate
    conn = get_db()
    conn.execute("UPDATE system_config SET value = ? WHERE key = 'overdue_fine_rate'", (str(rate),))
    conn.commit()
    conn.close()
    
    # Refresh config cache in services.py so it gets the new rate
    from backend.services import _invalidate_config_cache
    _invalidate_config_cache()

    # 2. Create the loan
    tx_id, _, _ = loan_builder()
    
    # 3. Manually set the due_date of the transaction in the database
    conn = get_db()
    conn.execute("UPDATE issue_transactions SET due_date = ? WHERE id = ?", (due, tx_id))
    conn.commit()
    conn.close()
    
    # 4. Mock datetime.date.today to return the ret date during return_book() execution
    # Preserve the original fromisoformat to avoid recursion loop when mocking datetime.date
    real_fromisoformat = datetime.date.fromisoformat
    
    mock_ret_date = real_fromisoformat(ret)
    mock_date_class = mocker.patch('backend.services.datetime.date')
    mock_date_class.today.return_value = mock_ret_date
    mock_date_class.fromisoformat.side_effect = real_fromisoformat
    
    # 5. Call return_book
    lib_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
    res = return_book(tx_id, user_info=lib_info)
    
    assert res['overdue_days'] == expected_days
    assert res['fine_amount'] == expected_fine
