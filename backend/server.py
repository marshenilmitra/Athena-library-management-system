import os
import io
from flask import Flask, request, jsonify, send_from_directory, Response
from backend.db import init_db, get_db
from backend.auth import hash_password, verify_password, create_session, get_session, destroy_session
import backend.services as services

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR)

# Initialize DB on server start
init_db()

# --- Auth Middleware Helper ---
def authenticate_request(required_roles=None):
    auth_header = request.headers.get('Authorization')
    token = None
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
    
    if not token:
        # Check cookie or query param fallback
        token = request.args.get('token')

    session = get_session(token)
    if not session:
        return None, (jsonify({"error": "Unauthorized or session expired"}), 401)
    
    if required_roles and session['role'] not in required_roles:
        return None, (jsonify({"error": "Forbidden: Insufficient privileges"}), 403)
    
    return session, None

# --- Static File Routes ---
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)

# --- Authentication API ---
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, role, status FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if not user or not verify_password(password, user['password_hash']):
        return jsonify({"error": "Invalid username or password"}), 401

    if user['status'] != 'Active':
        return jsonify({"error": "Account is deactivated (BR-09)"}), 403

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
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
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

# --- User Management API (Admin only) ---
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

# --- Member Management API (Admin, Librarian) ---
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
        services.update_member(mid, data.get('name'), data.get('email'), data.get('phone'), data.get('status'), session)
        return jsonify({"message": "Member record updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- Catalog API (Public/Authenticated Search, Admin/Librarian CRUD) ---
@app.route('/api/books', methods=['GET'])
def api_get_books():
    session, err = authenticate_request()
    if err: return err
    title_q = request.args.get('title')
    author_q = request.args.get('author')
    isbn_q = request.args.get('isbn')
    cat_id = request.args.get('category_id')
    avail = request.args.get('availability')
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

# --- Circulation API (Issue & Return) ---
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
    
    # If Member role, restrict to their own member record
    member_id = None
    if session['role'] == 'Member':
        mem = services.get_member_by_user_id(session['user_id'])
        if not mem:
            return jsonify([])
        member_id = mem['id']
    else:
        m_param = request.args.get('member_id')
        if m_param: member_id = int(m_param)

    status = request.args.get('status')
    q = request.args.get('q')
    return jsonify(services.get_transactions(member_id, status, q))

# --- Reservation API ---
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
                return jsonify({"error": "No member profile linked"}), 400
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
        if not mem: return jsonify([])
        member_id = mem['id']

    return jsonify(services.get_reservations(member_id))

@app.route('/api/reservations/<int:rid>/cancel', methods=['POST'])
def api_cancel_reservation(rid):
    session, err = authenticate_request()
    if err: return err
    try:
        services.cancel_reservation(rid, session)
        return jsonify({"message": "Reservation cancelled"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- Fines API ---
@app.route('/api/fines', methods=['GET'])
def api_get_fines():
    session, err = authenticate_request()
    if err: return err
    
    member_id = None
    if session['role'] == 'Member':
        mem = services.get_member_by_user_id(session['user_id'])
        if not mem: return jsonify([])
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

# --- Reports & System Configuration API ---
@app.route('/api/reports/summary', methods=['GET'])
def api_reports_summary():
    session, err = authenticate_request()
    if err: return err
    return jsonify(services.get_reports_summary())

@app.route('/api/reports/export/<report_type>', methods=['GET'])
def api_export_report(report_type):
    session, err = authenticate_request(['Admin', 'Librarian'])
    if err: return err
    try:
        csv_data = services.export_report_csv(report_type)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename=lms_{report_type}_report.csv"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
        "paths": {
            "/api/auth/login": {"post": {"summary": "Authenticate user and receive session token"}},
            "/api/auth/logout": {"post": {"summary": "Invalidate active user session"}},
            "/api/books": {"get": {"summary": "List catalog books with filter and search"}, "post": {"summary": "Add new book title (Admin/Librarian)"}},
            "/api/transactions/issue": {"post": {"summary": "Atomic checkout issue of book copy to member"}},
            "/api/transactions/{id}/return": {"post": {"summary": "Record book return & calculate overdue fine"}},
            "/api/reservations": {"get": {"summary": "Get hold queue"}, "post": {"summary": "Place hold on out of stock title"}},
            "/api/reports/summary": {"get": {"summary": "Get executive KPI summary metrics"}},
            "/api/reports/export/{type}": {"get": {"summary": "Download CSV data exports"}}
        }
    }
    return jsonify(spec)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Library Management System server on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
