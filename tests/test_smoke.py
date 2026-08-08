import pytest
from backend.auth import hash_password, verify_password


def test_password_hashing():
    pwd = "MySuperSecretPassword!@#123"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_successful_login(client):
    res = client.post('/api/auth/login', json={
        'username': 'admin',
        'password': 'Admin@123'
    })
    assert res.status_code == 200
    assert 'token' in res.json
    assert res.json['user']['role'] == 'Admin'


@pytest.mark.xfail(strict=True, reason="DEFECT: unauthenticated /books access should redirect to /login but the current app returns 404")
def test_unauthenticated_books_redirects_to_login(client):
    res = client.get('/books', follow_redirects=False)
    assert res.status_code == 302
    assert res.headers['Location'] == '/login'
