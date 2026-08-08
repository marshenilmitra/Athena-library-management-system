import hashlib
import os
import secrets
import time

SECRET_KEY = secrets.token_hex(32)
SESSIONS = {}  # token -> {user_id, username, role, expires_at}
SESSION_TTL = 3600 * 8  # 8 hours

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 with SHA-256 and a random salt."""
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{pwd_hash.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plain password against the stored salt:hash string."""
    try:
        salt_hex, hash_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return secrets.compare_digest(expected_hash, computed_hash)
    except Exception:
        return False

def create_session(user_id: int, username: str, role: str) -> str:
    """Generate a token and store session details."""
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + SESSION_TTL
    SESSIONS[token] = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "expires_at": expires_at
    }
    return token

def get_session(token: str):
    """Retrieve session if valid and not expired."""
    if not token or token not in SESSIONS:
        return None
    session = SESSIONS[token]
    if time.time() > session["expires_at"]:
        del SESSIONS[token]
        return None
    return session

def destroy_session(token: str):
    """Destroy session token."""
    if token in SESSIONS:
        del SESSIONS[token]
