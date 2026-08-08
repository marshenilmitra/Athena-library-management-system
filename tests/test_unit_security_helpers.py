import pytest
import time
from backend.auth import create_session, get_session, verify_password
from backend.server import _check_rate_limit, _record_failed_login

@pytest.mark.unit
def test_verify_password_invalid_hash_formats():
    # Test garbage inputs to verify_password do not crash, just return False
    assert verify_password("pass", "") is False
    assert verify_password("pass", "nocolon") is False
    assert verify_password("pass", "too:many:colons") is False
    assert verify_password("pass", "invalidhex:invalidhex") is False

@pytest.mark.unit
def test_session_ttl_expiration(mocker):
    # 1. Create a valid session
    token = create_session(1, "admin", "Admin")
    assert get_session(token) is not None
    
    # 2. Mock time to advance 8 hours + 1 second
    current_time = time.time()
    mocker.patch('backend.auth.time.time', return_value=current_time + 3600 * 8 + 1)
    
    # 3. Retrieve session again and check it has expired
    assert get_session(token) is None

@pytest.mark.unit
def test_rate_limiter_limit_and_reset(mocker):
    ip = "192.168.1.100"
    
    # Send 5 failed login attempts
    for _ in range(5):
        assert _check_rate_limit(ip) is True
        _record_failed_login(ip)
        
    # The 6th attempt should block (returns False)
    assert _check_rate_limit(ip) is False
    
    # Advance time by 61 seconds
    current_time = time.time()
    mocker.patch('backend.server.time.time', return_value=current_time + 61)
    
    # Rate limit should reset, allowing requests again
    assert _check_rate_limit(ip) is True
