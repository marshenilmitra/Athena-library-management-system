# Automated test suite for the LMS

## How to run

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install pytest pytest-cov pytest-mock hypothesis
venv\Scripts\python.exe -m pytest -q
venv\Scripts\python.exe -m pytest -m unit -q
venv\Scripts\python.exe -m pytest -m boundary -q
venv\Scripts\python.exe -m pytest -m integration -q
venv\Scripts\python.exe -m pytest -q --cov=backend --cov-report=term-missing
```

## Test file inventory

| File | Focus | Count |
| --- | --- | ---: |
| tests/test_smoke.py | smoke coverage for auth and routing | 3 |
| tests/test_unit_models.py | model and schema constraints | 8 |
| tests/test_unit_validators.py | validation helpers | 5 |
| tests/test_unit_fine_calc.py | fine arithmetic | 6 |
| tests/test_unit_security_helpers.py | auth/security helpers | 3 |
| tests/test_boundary.py | boundary-value analysis | 4 |
| tests/test_integration_books.py | catalog flows | 6 |
| tests/test_integration_members.py | member flows | 5 |
| tests/test_integration_transactions.py | issue/return flows | 6 |
| tests/test_integration_reports.py | reports and dashboard metrics | 4 |
| tests/test_security_rbac.py | RBAC matrix | 4 |
| tests/test_security_misc.py | CSRF, XSS, injection, headers | 8 |
| tests/test_property_hypothesis.py | property-based invariants | 4 |

## Boundary matrix

| Field / rule | File:line | Values probed | Outcome |
| --- | --- | --- | --- |
| Borrow limit | backend/services.py:286 | 2, 3, 4 | 2/3 allowed, 4 rejected |
| Fine payment | backend/services.py:520 | -1, 0, 0.50, 4.50, > balance | negative/zero rejected, partial/paid accepted, overpayment rejected |
| Unpaid-fine threshold | backend/services.py:300 | $20.00, $20.01 | exactly $20.00 allowed, $20.01 rejected |
| Book quantity | backend/services.py:366 | -1, 0, 1 | -1 rejected, 0/1 accepted |

## Known defects and questionable behavior

1. [tests/test_smoke.py](tests/test_smoke.py) pins the defect that unauthenticated access to /books should redirect to /login, but the current app returns 404 instead.
2. The app’s current auth flow uses a permissive API style for /api/books and /api/members, so some routes are harder to exercise cleanly with explicit redirect semantics.
3. The suite intentionally uses an isolated SQLite test database to avoid cross-test contamination; this is a testing harness choice rather than an application defect.
