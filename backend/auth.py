import hashlib
import os
import secrets
import time

# SECRET_KEY must be set via SECRET_KEY environment variable in production.
# A random fallback is used in development only — sessions will not persist across restarts.
SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

if not os.environ.get('SECRET_KEY'):
    import sys
    print(
        "[WARN] SECRET_KEY not set in environment. Using an ephemeral key. "
        "Sessions will be invalidated on every restart. Set SECRET_KEY env var in production.",
        file=sys.stderr
    )

# NOTE: In-memory session store is suitable for single-worker development only.
# For production multi-worker deployments (Render with multiple workers, etc.),
# replace SESSIONS with a Redis-backed store (e.g., flask-session with Redis).
SESSIONS: dict = {}  # token -> {user_id, username, role, expires_at}
SESSION_TTL = 3600 * 8  # 8 hours


def sweep_expired_sessions():
    """
    PB-08 FIX: Purge all expired session entries from the in-memory dict.
    Call this periodically (e.g., on login) to prevent unbounded memory growth
    from sessions that were never explicitly logged out (browser closed, etc.).
    """
    now = time.time()
    expired_tokens = [t for t, s in SESSIONS.items() if now > s["expires_at"]]
    for token in expired_tokens:
        SESSIONS.pop(token, None)
    return len(expired_tokens)


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a cryptographically random 16-byte salt."""
    salt = os.urandom(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 260000)
    return f"{salt.hex()}:{pwd_hash.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time verification of a plain password against the stored salt:hash string."""
    try:
        salt_hex, hash_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        # Handle both old 100k iterations and new 260k iterations
        for iterations in (260000, 100000):
            computed_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
            if secrets.compare_digest(expected_hash, computed_hash):
                return True
        return False
    except Exception:
        return False


def create_session(user_id: int, username: str, role: str) -> str:
    """Generate a cryptographically secure URL-safe token and store session details."""
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
    """Retrieve session data if the token is valid and not expired. Returns None otherwise."""
    if not token or token not in SESSIONS:
        return None
    session = SESSIONS[token]
    if time.time() > session["expires_at"]:
        del SESSIONS[token]
        return None
    return session


def destroy_session(token: str):
    """Immediately invalidate a session token."""
    SESSIONS.pop(token, None)
