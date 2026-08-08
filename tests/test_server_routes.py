import pytest


def test_auth_me_and_unauthorized_routes(client):
    res = client.get('/api/auth/me')
    assert res.status_code == 401

    res = client.get('/api/auth/me', headers={'Authorization': 'Bearer invalid-token'})
    assert res.status_code == 401


def test_admin_and_member_catalog_routes(client, login):
    admin_token = login('Admin')
    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    res = client.get('/api/users', headers=admin_headers)
    assert res.status_code == 200

    member_token = login('Member')
    member_headers = {'Authorization': f'Bearer {member_token}'}
    res = client.get('/api/books', headers=member_headers)
    assert res.status_code == 200


def test_librarian_catalog_and_reference_routes(client, login):
    token = login('Librarian')
    headers = {'Authorization': f'Bearer {token}'}

    res = client.get('/api/authors', headers=headers)
    assert res.status_code == 200
    res = client.post('/api/authors', headers=headers, json={'name': 'Route Author', 'bio': 'bio'})
    assert res.status_code in {200, 400}

    res = client.get('/api/publishers', headers=headers)
    assert res.status_code == 200
    res = client.post('/api/publishers', headers=headers, json={'name': 'Route Publisher', 'address': 'Test'})
    assert res.status_code in {200, 400}

    res = client.get('/api/categories', headers=headers)
    assert res.status_code == 200
    res = client.post('/api/categories', headers=headers, json={'name': 'Route Category', 'description': 'desc'})
    assert res.status_code in {200, 400}


def test_circulation_reports_and_docs(client, login, book_builder, member_builder):
    token = login('Librarian')
    headers = {'Authorization': f'Bearer {token}'}

    member_id, _ = member_builder(email='route-member@example.com')
    book_id, _ = book_builder(title='Route Book', isbn='978-2000000000', total_quantity=1)

    issue_res = client.post('/api/transactions/issue', headers=headers, json={'book_id': book_id, 'member_id': member_id})
    assert issue_res.status_code in {200, 201, 400}
    tx_id = issue_res.json['transaction_id']

    res = client.get('/api/transactions', headers=headers)
    assert res.status_code == 200

    res = client.post(f'/api/transactions/{tx_id}/return', headers=headers)
    assert res.status_code in {200, 400}

    res = client.get('/api/reports/summary', headers=headers)
    assert res.status_code == 200
    res = client.get('/api/reports/export/inventory', headers=headers)
    assert res.status_code == 200
    res = client.get('/api/reports/export/invalid', headers=headers)
    assert res.status_code in {400, 401}

    res = client.options('/api/books')
    assert res.status_code == 200

    res = client.get('/api/docs')
    assert res.status_code == 200


def test_config_and_audit_routes(client, login):
    admin_token = login('Admin')
    admin_headers = {'Authorization': f'Bearer {admin_token}'}

    res = client.get('/api/config', headers=admin_headers)
    assert res.status_code == 200
    res = client.put('/api/config', headers=admin_headers, json={'borrow_period_days': '21'})
    assert res.status_code in {200, 400}
    res = client.get('/api/audit-logs', headers=admin_headers)
    assert res.status_code == 200
