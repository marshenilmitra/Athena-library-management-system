import os
import io
import time
import threading
from flask import Flask, request, jsonify, send_from_directory, Response
from backend.db import init_db, get_db
from backend.auth import hash_password, verify_password, create_session, get_session, destroy_session, sweep_expired_sessions
import backend.services as services

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app = Flask(__name__, static_folder=FRONTEND_DIR)

# Read CORS allowed origin from env (defaults to all for dev convenience)
ALLOWED_ORIGIN = os.environ.get('ALLOWED_ORIGIN', '*')

# Initialize DB on server start
init_db()

# ---------------------------------------------------------------------------
# Security: CORS Headers
# ---------------------------------------------------------------------------
@app.after_request
def add_security_headers(response):
    """Attach security-hardening HTTP response headers to every response."""
    # CORS
    if ALLOWED_ORIGIN == '*':
        response.headers['Access-Control-Allow-Origin'] = '*'
    else:
        origin = request.headers.get('Origin', '')
        if origin == ALLOWED_ORIGIN:
            response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'

    # Prevent clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    # Prevent MIME-type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Enable browser XSS filter (legacy but harmless)
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Referrer policy
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Content Security Policy — restrict script/style sources
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response


@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle CORS pre-flight OPTIONS requests."""
    return jsonify({}), 200


# ---------------------------------------------------------------------------
# Security: Login Rate Limiting (in-memory, per IP)
# ---------------------------------------------------------------------------
_login_attempts: dict = {}   # ip -> [timestamp, ...]
_login_lock = threading.Lock()

RATE_LIMIT_MAX = 5       # max failed attempts
RATE_LIMIT_WINDOW = 60   # seconds window


def _check_rate_limit(ip: str) -> bool:
    """Returns True if request is allowed, False if rate limit exceeded."""
    now = time.time()
    with _login_lock:
        attempts = _login_attempts.get(ip, [])
        # Prune old attempts outside the window
        attempts = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]
        _login_attempts[ip] = attempts
        if len(attempts) >= RATE_LIMIT_MAX:
            return False
        return True


def _record_failed_login(ip: str):
    """Record a failed login attempt for rate limiting."""
    now = time.time()
    with _login_lock:
        attempts = _login_attempts.get(ip, [])
        attempts.append(now)
        _login_attempts[ip] = attempts


# ---------------------------------------------------------------------------
# Security: Report Type Allowlist
# ---------------------------------------------------------------------------
ALLOWED_REPORT_TYPES = {'inventory', 'overdue', 'issued'}


# ---------------------------------------------------------------------------
# Auth Middleware Helper
# ---------------------------------------------------------------------------
def authenticate_request(required_roles=None):
    """Validate Bearer token from Authorization header ONLY (not query params)."""
    auth_header = request.headers.get('Authorization', '')
    token = None

    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()

    # Reject any attempt to pass token via query string (security: prevents log leakage)
    if not token:
        return None, (jsonify({"error": "Unauthorized: Missing or invalid Authorization header"}), 401)

    session = get_session(token)
    if not session:
        return None, (jsonify({"error": "Unauthorized: Session expired or invalid token"}), 401)

    if required_roles and session['role'] not in required_roles:
        return None, (jsonify({"error": "Forbidden: Insufficient privileges"}), 403)

    return session, None


# ---------------------------------------------------------------------------
# Static File Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ---------------------------------------------------------------------------
# Authentication API
# ---------------------------------------------------------------------------
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    ip = request.remote_addr

    # PB-08 FIX: Sweep expired sessions on each login (amortized cleanup cost)
    sweep_expired_sessions()

    # Rate limit check BEFORE processing credentials
    if not _check_rate_limit(ip):
        return jsonify({
            "error": "Too many login attempts. Please wait 60 seconds and try again."
        }), 429

    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, password_hash, role, status FROM users WHERE username = ?",
        (username,)
    )
    user = cursor.fetchone()
    conn.close()

    # Verify credentials; use generic message to prevent username enumeration
    if not user or not verify_password(password, user['password_hash']):
        _record_failed_login(ip)
        return jsonify({"error": "Invalid username or password"}), 401

    if user['status'] != 'Active':
        return jsonify({"error": "Account is deactivated. Contact your administrator."}), 403

    token = create_session(user['id'], user['username'], user['role'])

    # Fetch member profile if user role is Member
    member_profile = None
    if user['role'] == 'Member':
        member_profile = services.get_member_by_user_id(user['id'])

    services.log_audit(user['id'], user['username'], "LOGIN", "User logged in successfully")

    return jsonify({
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "role": user['role'],
            "member_info": member_profile
        }
    })


@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1].strip()
        session = get_session(token)
        if session:
            services.log_audit(session['user_id'], session['username'], "LOGOUT", "User logged out")
        destroy_session(token)
    return jsonify({"message": "Logged out successfully"})


@app.route('/api/auth/me', methods=['GET'])
def api_me():
    session, err = authenticate_request()
    if err:
        return err
    member_profile = None
    if session['role'] == 'Member':
        member_profile = services.get_member_by_user_id(session['user_id'])
    return jsonify({"user": session, "member_info": member_profile})


# ---------------------------------------------------------------------------
# User Management API (Admin only)
# ---------------------------------------------------------------------------
@app.route('/api/users', methods=['GET'])
def api_get_users():
    session, err = authenticate_request(['Admin'])
    if err: return err
    return jsonify(services.get_users())


@app.route('/api/users', methods=['POST'])
def api_create_user():
    session, err = authenticate_request(['Admin'])
    if err: return err
    data = request.get_json() or {}
    try:
        pwd_hash = hash_password(data.get('password', 'User@123'))
        uid = services.create_user(
            username=data.get('username'),
            password_hash=pwd_hash,
            role=data.get('role', 'Member'),
            status=data.get('status', 'Active'),
            user_info=session
        )
        return jsonify({"message": "User created", "id": uid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/users/<int:uid>', methods=['PUT'])
def api_update_user(uid):
    session, err = authenticate_request(['Admin'])
    if err: return err
    data = request.get_json() or {}
    try:
        pwd_hash = hash_password(data['password']) if data.get('password') else None
        services.update_user(uid, data.get('role'), data.get('status'), pwd_hash, session)
        return jsonify({"message": "User updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# Member Management API (Admin, Librarian)
# ---------------------------------------------------------------------------
@app.route('/api/members', methods=['GET'])
def api_get_members():
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    q = request.args.get('q')
    return jsonify(services.get_members(q))


@app.route('/api/members', methods=['POST'])
def api_create_member():
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    data = request.get_json() or {}
    try:
        mid = services.create_member(
            name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone'),
            user_id=data.get('user_id'),
            user_info=session
        )
        return jsonify({"message": "Member registered", "id": mid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/members/<int:mid>', methods=['PUT'])
def api_update_member(mid):
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    data = request.get_json() or {}
    try:
        services.update_member(
            mid, data.get('name'), data.get('email'),
            data.get('phone'), data.get('status'), session
        )
        return jsonify({"message": "Member record updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# Catalog API
# ---------------------------------------------------------------------------
@app.route('/api/books', methods=['GET'])
def api_get_books():
    session, err = authenticate_request()
    if err: return err
    title_q  = request.args.get('title')
    author_q = request.args.get('author')
    isbn_q   = request.args.get('isbn')
    cat_id   = request.args.get('category_id')
    avail    = request.args.get('availability')
    return jsonify(services.get_books(title_q, author_q, isbn_q, cat_id, avail))


@app.route('/api/books', methods=['POST'])
def api_add_book():
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    data = request.get_json() or {}
    try:
        bid = services.add_book(
            isbn=data.get('isbn'),
            title=data.get('title'),
            author_id=int(data.get('author_id')),
            publisher_id=int(data.get('publisher_id')),
            category_id=int(data.get('category_id')),
            publication_year=int(data.get('publication_year', 2024)),
            total_quantity=int(data.get('total_quantity', 1)),
            user_info=session
        )
        return jsonify({"message": "Book added successfully", "id": bid}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/books/<int:bid>', methods=['PUT'])
def api_update_book(bid):
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    data = request.get_json() or {}
    try:
        services.update_book(
            book_id=bid,
            title=data.get('title'),
            author_id=int(data.get('author_id')),
            publisher_id=int(data.get('publisher_id')),
            category_id=int(data.get('category_id')),
            publication_year=int(data.get('publication_year')),
            total_quantity=int(data.get('total_quantity')),
            status=data.get('status', 'Active'),
            user_info=session
        )
        return jsonify({"message": "Book updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/authors', methods=['GET', 'POST'])
def api_authors():
    session, err = authenticate_request()
    if err: return err
    if request.method == 'POST':
        if session['role'] not in ['Admin', 'Librarian']:
            return jsonify({"error": "Forbidden"}), 403
        data = request.get_json() or {}
        services.add_author(data.get('name'), data.get('bio', ''), session)
        return jsonify({"message": "Author created"})
    return jsonify(services.get_authors())


@app.route('/api/publishers', methods=['GET', 'POST'])
def api_publishers():
    session, err = authenticate_request()
    if err: return err
    if request.method == 'POST':
        if session['role'] not in ['Admin', 'Librarian']:
            return jsonify({"error": "Forbidden"}), 403
        data = request.get_json() or {}
        services.add_publisher(data.get('name'), data.get('address', ''), session)
        return jsonify({"message": "Publisher created"})
    return jsonify(services.get_publishers())


@app.route('/api/categories', methods=['GET', 'POST'])
def api_categories():
    session, err = authenticate_request()
    if err: return err
    if request.method == 'POST':
        if session['role'] not in ['Admin', 'Librarian']:
            return jsonify({"error": "Forbidden"}), 403
        data = request.get_json() or {}
        services.add_category(data.get('name'), data.get('description', ''), session)
        return jsonify({"message": "Category created"})
    return jsonify(services.get_categories())


# ---------------------------------------------------------------------------
# Circulation API (Issue & Return)
# ---------------------------------------------------------------------------
@app.route('/api/transactions/issue', methods=['POST'])
def api_issue_book():
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    data = request.get_json() or {}
    try:
        res = services.issue_book(
            book_id=int(data.get('book_id')),
            member_id=int(data.get('member_id')),
            issued_by_user=session['user_id'],
            user_info=session
        )
        return jsonify(res), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/transactions/<int:tx_id>/return', methods=['POST'])
def api_return_book(tx_id):
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    try:
        res = services.return_book(tx_id, session)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/api/transactions', methods=['GET'])
def api_get_transactions():
    session, err = authenticate_request()
    if err: return err

    member_id = None
    if session['role'] == 'Member':
        mem = services.get_member_by_user_id(session['user_id'])
        if not mem:
            return jsonify([])
        member_id = mem['id']
    else:
        m_param = request.args.get('member_id')
        if m_param:
            member_id = int(m_param)

    status = request.args.get('status')
    q = request.args.get('q')
    return jsonify(services.get_transactions(member_id, status, q))


# ---------------------------------------------------------------------------
# Reservation API
# ---------------------------------------------------------------------------
@app.route('/api/reservations', methods=['GET', 'POST'])
def api_reservations():
    session, err = authenticate_request()
    if err: return err

    if request.method == 'POST':
        data = request.get_json() or {}
        book_id = int(data.get('book_id'))

        member_id = data.get('member_id')
        if session['role'] == 'Member':
            mem = services.get_member_by_user_id(session['user_id'])
            if not mem:
                return jsonify({"error": "No member profile linked to this account"}), 400
            member_id = mem['id']
        elif not member_id:
            return jsonify({"error": "Member ID is required"}), 400

        try:
            rid = services.reserve_book(book_id, int(member_id), session)
            return jsonify({"message": "Book reserved successfully", "id": rid}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    member_id = None
    if session['role'] == 'Member':
        mem = services.get_member_by_user_id(session['user_id'])
        if not mem:
            return jsonify([])
        member_id = mem['id']

    return jsonify(services.get_reservations(member_id))


@app.route('/api/reservations/<int:rid>/cancel', methods=['POST'])
def api_cancel_reservation(rid):
    session, err = authenticate_request()
    if err: return err
    try:
        services.cancel_reservation(rid, session)
        return jsonify({"message": "Reservation cancelled"})
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# Fines API
# ---------------------------------------------------------------------------
@app.route('/api/fines', methods=['GET'])
def api_get_fines():
    session, err = authenticate_request()
    if err: return err

    member_id = None
    if session['role'] == 'Member':
        mem = services.get_member_by_user_id(session['user_id'])
        if not mem:
            return jsonify([])
        member_id = mem['id']

    return jsonify(services.get_fines(member_id))


@app.route('/api/fines/<int:fid>/pay', methods=['POST'])
def api_pay_fine(fid):
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    data = request.get_json() or {}
    try:
        amount = float(data.get('amount_paid', 0))
        res = services.pay_fine(fid, amount, session)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------------------------------------------------------------------
# Reports & System Configuration API
# ---------------------------------------------------------------------------
@app.route('/api/reports/summary', methods=['GET'])
def api_reports_summary():
    session, err = authenticate_request()
    if err: return err
    return jsonify(services.get_reports_summary())


@app.route('/api/reports/export/<report_type>', methods=['GET'])
def api_export_report(report_type):
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err

    # SECURITY: Strict allowlist to prevent path traversal / unexpected behavior
    if report_type not in ALLOWED_REPORT_TYPES:
        return jsonify({
            "error": f"Invalid report type. Allowed types: {', '.join(sorted(ALLOWED_REPORT_TYPES))}"
        }), 400

    try:
        csv_data = services.export_report_csv(report_type)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=lms_{report_type}_report.csv"}
        )
    except Exception as e:
        return jsonify({"error": "Report generation failed"}), 500


@app.route('/api/config', methods=['GET', 'PUT'])
def api_config():
    session, err = authenticate_request(['Admin'])
    if err: return err
    if request.method == 'PUT':
        data = request.get_json() or {}
        for k, v in data.items():
            services.update_config(k, str(v), session)
        return jsonify({"message": "Settings saved"})
    return jsonify(services.get_all_config())


@app.route('/api/audit-logs', methods=['GET'])
def api_audit_logs():
    session, err = authenticate_request(['Admin'])
    if err: return err
    return jsonify(services.get_audit_logs())


# ---------------------------------------------------------------------------
# OpenAPI 3.0 Documentation
# ---------------------------------------------------------------------------
@app.route('/api/docs', methods=['GET'])
def api_docs():
    """OpenAPI 3.0 API Specification for LMS REST Services."""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Athena LMS API",
            "version": "1.0.0",
            "description": "Enterprise Library Management System REST API specification."
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        },
        "security": [{"bearerAuth": []}],
        "paths": {
            "/api/auth/login": {"post": {"summary": "Authenticate user and receive session token", "security": []}},
            "/api/auth/logout": {"post": {"summary": "Invalidate active user session"}},
            "/api/auth/me": {"get": {"summary": "Get current authenticated user profile"}},
            "/api/books": {
                "get": {"summary": "List catalog books with filter and search"},
                "post": {"summary": "Add new book title (Admin/Librarian)"}
            },
            "/api/members": {
                "get": {"summary": "List registered members (Admin/Librarian)"},
                "post": {"summary": "Register new library member (Admin/Librarian)"}
            },
            "/api/transactions/issue": {"post": {"summary": "Atomic checkout — issue book copy to member"}},
            "/api/transactions/{id}/return": {"post": {"summary": "Record book return and calculate overdue fine"}},
            "/api/reservations": {
                "get": {"summary": "Get hold queue"},
                "post": {"summary": "Place hold on out-of-stock title"}
            },
            "/api/fines": {"get": {"summary": "List fines (members see only their own)"}},
            "/api/fines/{id}/pay": {"post": {"summary": "Record fine payment (Admin/Librarian)"}},
            "/api/reports/summary": {"get": {"summary": "Get executive KPI summary metrics"}},
            "/api/reports/export/{type}": {"get": {"summary": "Download CSV data exports (inventory|overdue|issued)"}},
            "/api/config": {
                "get": {"summary": "Get system configuration (Admin)"},
                "put": {"summary": "Update system configuration (Admin)"}
            },
            "/api/audit-logs": {"get": {"summary": "Get audit event log (Admin)"}}
        }
    }
    return jsonify(spec)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'false').lower() == 'true'
    print(f"Starting Athena LMS server on http://localhost:{port} (debug={debug_mode})")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
