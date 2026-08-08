import pytest


def test_auth_me_logout_and_user_listing(client, login):
    res = client.get('/api/auth/me')
    assert res.status_code == 401

    token = login('Admin')
    res = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200
    assert res.json['user']['role'] == 'Admin'

    res = client.post('/api/auth/logout', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 200

    res = client.get('/api/users', headers={'Authorization': f'Bearer {token}'})
    assert res.status_code == 401


def test_reference_and_catalog_endpoints(client, login):
    token = login('Librarian')
    headers = {'Authorization': f'Bearer {token}'}

    res = client.get('/api/authors', headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json, list)

    res = client.post('/api/authors', headers=headers, json={'name': 'Coverage Author', 'bio': 'A test author'})
    assert res.status_code in {200, 400}

    res = client.get('/api/publishers', headers=headers)
    assert res.status_code == 200

    res = client.post('/api/publishers', headers=headers, json={'name': 'Coverage Press', 'address': 'Test city'})
    assert res.status_code in {200, 400}

    res = client.get('/api/categories', headers=headers)
    assert res.status_code == 200

    res = client.post('/api/categories', headers=headers, json={'name': 'Coverage Category', 'description': 'Test'})
    assert res.status_code in {200, 400}


def test_reservation_and_fine_endpoints(client, login, member_builder, book_builder):
    token = login('Librarian')
    headers = {'Authorization': f'Bearer {token}'}

    member_id, _ = member_builder(email='coverage-member@example.com')
    book_id, _ = book_builder(title='Coverage Book', isbn='978-0000000000', total_quantity=1)

    res = client.post('/api/reservations', headers=headers, json={'book_id': book_id, 'member_id': member_id})
    assert res.status_code in {200, 201, 400}

    res = client.get('/api/reservations', headers=headers)
    assert res.status_code == 200
    assert len(res.json) >= 1

    reservation_id = res.json[0]['id']
    res = client.post(f'/api/reservations/{reservation_id}/cancel', headers=headers)
    assert res.status_code == 200

    res = client.get('/api/fines', headers=headers)
    assert res.status_code == 200


def test_reports_config_and_export_endpoints(client, login):
    token = login('Admin')
    headers = {'Authorization': f'Bearer {token}'}

    res = client.get('/api/reports/summary', headers=headers)
    assert res.status_code == 200
    assert 'total_books' in res.json

    res = client.get('/api/reports/export/inventory', headers=headers)
    assert res.status_code == 200
    assert 'text/csv' in res.content_type

    res = client.get('/api/config', headers=headers)
    assert res.status_code == 200

    res = client.put('/api/config', headers=headers, json={'overdue_fine_rate': '2.50'})
    assert res.status_code in {200, 400}

    res = client.get('/api/audit-logs', headers=headers)
    assert res.status_code == 200
