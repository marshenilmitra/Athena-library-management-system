import pytest

from backend.db import get_db
import backend.services as services


@pytest.mark.integration
def test_server_error_and_role_branches(client, login):
    res = client.get('/api/books')
    assert res.status_code == 401

    member_token = login('Member')
    member_headers = {'Authorization': f'Bearer {member_token}'}
    res = client.get('/api/users', headers=member_headers)
    assert res.status_code == 403

    res = client.post('/api/authors', headers=member_headers, json={'name': 'Test', 'bio': 'x'})
    assert res.status_code == 403

    res = client.post('/api/authors', headers={'Authorization': 'Bearer not-a-real-token'}, json={'name': 'Test', 'bio': 'x'})
    assert res.status_code == 401

    res = client.post('/api/auth/login', json={'username': '', 'password': 'x'})
    assert res.status_code == 400

    res = client.post('/api/auth/login', json={'username': 'does-not-exist', 'password': 'x'})
    assert res.status_code == 401

    conn = get_db()
    conn.execute("UPDATE users SET status = 'Inactive' WHERE username = 'member1'")
    conn.commit()
    conn.close()
    res = client.post('/api/auth/login', json={'username': 'member1', 'password': 'Mem@123'})
    assert res.status_code == 403

    admin_token = login('Admin')
    res = client.get('/api/reports/export/invalid', headers={'Authorization': f'Bearer {admin_token}'})
    assert res.status_code == 400

    res = client.post('/api/auth/logout', headers={'Authorization': 'Bearer garbage'})
    assert res.status_code == 200

    res = client.get('/api/auth/me', headers={'Authorization': 'Bearer garbage'})
    assert res.status_code == 401


@pytest.mark.integration
def test_service_branch_behaviour(book_builder, member_builder):
    assert services.get_config('max_borrow_limit', '3') == '3'
    services.update_config('borrow_period_days', '21', {'user_id': 1, 'username': 'admin', 'role': 'Admin'})
    assert services.get_config('borrow_period_days', '14') == '21'
    assert services.get_all_config()

    services.create_user('dup-user', 'hash', 'Member', user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})
    with pytest.raises(ValueError):
        services.create_user('dup-user', 'hash', 'Member', user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})

    with pytest.raises(ValueError):
        services.create_member('Dup', 'john.doe@example.com', '+1', user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})

    services.add_author('Branch Author', 'bio', user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})
    services.add_publisher('Branch Publisher', 'addr', user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})
    services.add_category('Branch Category', 'desc', user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})

    with pytest.raises(ValueError):
        services.update_book(999, 'x', 1, 1, 1, 2024, 1, 'Active', user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})

    with pytest.raises(ValueError):
        services.add_book('978-0000000001', 'Bad Qty', 1, 1, 1, 2024, -1, user_info={'user_id': 1, 'username': 'admin', 'role': 'Admin'})

    book_id, _ = book_builder(title='Issueable', isbn='978-0000000002', total_quantity=1)
    member_id, _ = member_builder(email='branch-member@example.com')

    conn = get_db()
    conn.execute("UPDATE members SET status = 'Active' WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()

    tx_id = services.issue_book(book_id, member_id, issued_by_user=2, user_info={'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})['transaction_id']
    with pytest.raises(ValueError):
        services.return_book(tx_id + 999, user_info={'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    # The service allows the first return and blocks a duplicate return on the same transaction.
    services.return_book(tx_id, user_info={'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})
    with pytest.raises(ValueError):
        services.return_book(tx_id, user_info={'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    res_id = services.reserve_book(book_id, member_id, {'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})
    with pytest.raises(ValueError):
        services.reserve_book(book_id, member_id, {'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    with pytest.raises(Exception):
        services.reserve_book(999, member_id, {'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    with pytest.raises(PermissionError):
        services.cancel_reservation(res_id, {'user_id': 3, 'username': 'other', 'role': 'Member'})

    services.cancel_reservation(res_id, {'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    with pytest.raises(ValueError):
        services.cancel_reservation(res_id + 999, {'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    with pytest.raises(ValueError):
        services.pay_fine(999, 1.0, {'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    with pytest.raises(ValueError):
        services.pay_fine(1, 0.0, {'user_id': 2, 'username': 'librarian', 'role': 'Librarian'})

    assert services.get_reports_summary()
    assert services.export_report_csv('inventory')
    assert services.export_report_csv('overdue')
    assert services.export_report_csv('issued')
    assert services.get_audit_logs()
    assert services.get_fines()
    assert services.get_reservations()
    assert services.get_transactions()
