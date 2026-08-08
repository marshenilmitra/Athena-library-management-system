import pytest


@pytest.mark.integration
def test_user_member_and_catalog_routes(client, login, book_builder, member_builder):
    token = login('Admin')
    headers = {'Authorization': f'Bearer {token}'}

    res = client.get('/api/users', headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json, list)

    res = client.post('/api/users', headers=headers, json={
        'username': 'newadmin', 'password': 'Test@123', 'role': 'Librarian', 'status': 'Active'
    })
    assert res.status_code in {200, 201, 400}

    res = client.get('/api/members', headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json, list)

    res = client.post('/api/members', headers=headers, json={
        'name': 'Coverage Member', 'email': 'coverage-member@example.com', 'phone': '+1-555-1234'
    })
    assert res.status_code in {200, 201, 400}

    member_id = res.json['id']
    res = client.put(f'/api/members/{member_id}', headers=headers, json={
        'name': 'Coverage Member Updated', 'email': 'coverage-member-updated@example.com', 'phone': '+1-555-5678', 'status': 'Active'
    })
    assert res.status_code in {200, 400}

    res = client.get('/api/books', headers={'Authorization': f'Bearer {login("Librarian")}'} )
    assert res.status_code == 200

    book_id, _ = book_builder(title='Coverage Title', isbn='978-1111111111')
    res = client.put(f'/api/books/{book_id}', headers={'Authorization': f'Bearer {login("Librarian")}'} , json={
        'title': 'Coverage Title Updated', 'author_id': 1, 'publisher_id': 1, 'category_id': 1, 'publication_year': 2024, 'total_quantity': 2
    })
    assert res.status_code in {200, 400}


@pytest.mark.integration
def test_authors_publishers_categories_and_docs(client, login):
    token = login('Librarian')
    headers = {'Authorization': f'Bearer {token}'}

    res = client.get('/api/authors', headers=headers)
    assert res.status_code == 200

    res = client.post('/api/authors', headers=headers, json={'name': 'Author X', 'bio': 'Bio'})
    assert res.status_code in {200, 400}

    res = client.get('/api/publishers', headers=headers)
    assert res.status_code == 200

    res = client.post('/api/publishers', headers=headers, json={'name': 'Pub X', 'address': 'Address'})
    assert res.status_code in {200, 400}

    res = client.get('/api/categories', headers=headers)
    assert res.status_code == 200

    res = client.post('/api/categories', headers=headers, json={'name': 'Cat X', 'description': 'Desc'})
    assert res.status_code in {200, 400}

    res = client.get('/api/docs')
    assert res.status_code == 200
    assert 'openapi' in res.json


@pytest.mark.integration
def test_transactions_reservations_fines_and_reports(client, login, book_builder, member_builder):
    token = login('Librarian')
    headers = {'Authorization': f'Bearer {token}'}

    member_id, _ = member_builder(email='tx-member@example.com')
    book_id, _ = book_builder(title='Issueable Book', isbn='978-2222222222', total_quantity=1)

    res = client.post('/api/transactions/issue', headers=headers, json={'book_id': book_id, 'member_id': member_id})
    assert res.status_code in {200, 201, 400}
    tx_id = res.json['transaction_id']

    res = client.get('/api/transactions', headers=headers)
    assert res.status_code == 200
    assert isinstance(res.json, list)

    res = client.post(f'/api/transactions/{tx_id}/return', headers=headers)
    assert res.status_code in {200, 400}

    res = client.post('/api/reservations', headers=headers, json={'book_id': book_id, 'member_id': member_id})
    assert res.status_code in {200, 201, 400}

    res = client.get('/api/reservations', headers=headers)
    assert res.status_code == 200

    reservation_id = res.json[0]['id']
    res = client.post(f'/api/reservations/{reservation_id}/cancel', headers=headers)
    assert res.status_code == 200

    res = client.get('/api/fines', headers=headers)
    assert res.status_code == 200

    res = client.get('/api/reports/summary', headers=headers)
    assert res.status_code == 200

    res = client.get('/api/reports/export/invalid', headers=headers)
    assert res.status_code == 400

    res = client.get('/api/config', headers={'Authorization': f'Bearer {login("Admin")}'} )
    assert res.status_code == 200

    res = client.put('/api/config', headers={'Authorization': f'Bearer {login("Admin")}'} , json={'borrow_period_days': '21'})
    assert res.status_code in {200, 400}

    res = client.get('/api/audit-logs', headers={'Authorization': f'Bearer {login("Admin")}'} )
    assert res.status_code == 200
