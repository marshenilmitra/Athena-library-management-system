# System Architecture Document
## Library Management System (LMS)

**Based on:** SRS v1.0 (August 2026)
**Document Type:** System Architecture Design

---

## 1. Architectural Style

**Layered (N-tier) monolith with modular internal boundaries**, backed by a relational database. This is the right fit for the SRS: three user roles, moderate concurrency ("appropriate to the expected library size"), strong consistency requirements around inventory/transactions, and an explicit future path to add barcode scanning, notifications, and a mobile app without a rewrite.

Recommended concretely: a **3-tier web architecture** —

1. **Presentation tier** — browser-based UI (or desktop client)
2. **Application tier** — REST API + business logic, organized into internal modules (not separate microservices — a modular monolith keeps transactional consistency between Book, Circulation, and Fine data simple, which the SRS repeatedly stresses: NFR-10, NFR-11, BR-06, BR-07)
3. **Data tier** — a single relational database (MySQL/PostgreSQL)

Microservices are explicitly **not** recommended here: splitting Circulation/Fine/Reservation into separate services would force distributed transactions to keep inventory counts consistent (NFR-10/11), adding operational complexity the SRS's scale doesn't justify. Modularity is achieved through clean internal service boundaries instead.

---

## 2. High-Level Architecture

See the diagram above. Three tiers:

- **Client layer** — role-aware web UI (or desktop client) consumed by Admin, Librarian, and Member
- **Application layer** — six internal service modules behind a single API surface
- **Data layer** — one relational database, accessed only through the application layer

---

## 3. Application Layer — Module Breakdown

| Module | Responsibility | Key SRS refs |
|---|---|---|
| **Auth & User module** | Login/logout, password hashing, session/JWT issuance, RBAC enforcement | FR-01–10, NFR-04–06 |
| **Member module** | Member CRUD, status (active/inactive), eligibility checks | FR-11–16, BR-01, BR-08 |
| **Catalog module** | Book/Author/Publisher/Category CRUD, search & filter, availability display | FR-17–27 |
| **Circulation module** | Issue, return, due-date calculation, fine calculation, availability updates | FR-28–45, BR-02–07 |
| **Reservation module** | Place/cancel reservation, duplicate-reservation checks, queue status | FR-46–50 |
| **Reporting module** | Inventory, issued-books, overdue, member-borrowing, transaction reports; CSV/PDF export | FR-51–60 |

A cross-cutting **Audit/Logging module** wraps all state-changing operations (create/update/deactivate on User, Member, Book, Transaction) to satisfy NFR-09 without being tied to any single domain module.

### Module interaction rules
- The Circulation module is the **only** module allowed to mutate `available_quantity` on Book — this keeps BR-06/BR-07 enforceable in one place instead of scattered across the codebase.
- The Reservation module reads Catalog availability but never writes to it directly; it only writes to its own `Reservation` table.
- The Fine sub-flow (inside Circulation) is triggered exclusively by the Return operation, per FR-38/FR-45.

---

## 4. Component Diagram (textual)

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser)                        │
│         Login | Dashboard | Catalog | Issue/Return | Reports    │
└───────────────────────────┬───────────────────────────────────-┘
                             │ HTTPS / JSON (REST)
┌────────────────────────────▼──────────────────────────────────┐
│                        API Gateway Layer                       │
│   - Routes requests to controllers                             │
│   - Terminates HTTPS (NFR-08)                                  │
│   - Applies auth middleware (JWT/session validation, FR-04)    │
└───────────┬─────────────────────────────────────┬──────────────┘
            │                                     │
┌───────────▼───────────┐            ┌────────────▼─────────────┐
│   Auth & RBAC Module   │◄──────────►│    Audit/Logging Module   │
│  (password hashing,    │            │  (wraps state-changing    │
│   session mgmt)        │            │   calls across modules)   │
└───────────┬────────────┘            └────────────────────────-─┘
            │ validated user + role
┌───────────▼─────────────────────────────────────────────────────┐
│                      Domain Service Layer                       │
│  ┌───────────┐ ┌────────────┐ ┌──────────────┐ ┌─────────────┐ │
│  │  Member   │ │  Catalog   │ │ Circulation  │ │ Reservation │ │
│  │  Service  │ │  Service   │ │   Service    │ │   Service   │ │
│  └─────┬─────┘ └─────┬──────┘ └──────┬───────┘ └──────┬──────┘ │
│        │             │               │                │        │
│        └─────────────┴───────┬───────┴────────────────┘        │
│                               │                                 │
│                     ┌─────────▼─────────┐                       │
│                     │ Reporting Service │                       │
│                     └───────────────────┘                       │
└───────────────────────────────┬─────────────────────────────────┘
                                 │ ORM / parameterized SQL (NFR-06, security §13)
┌────────────────────────────────▼────────────────────────────────┐
│              Relational Database (MySQL / PostgreSQL)           │
│  User · Member · Book · Author · Publisher · Category ·         │
│  BookCopy · IssueTransaction · Reservation · Fine · FinePayment │
└───────────────────────────────────────────────────────────────-─┘
```

---

## 5. Recommended Technology Stack

| Layer | Options | Notes |
|---|---|---|
| Frontend | React / Vue (web) or a desktop framework (Electron, JavaFX, WinForms) if desktop-based | Matches "modern web browsers... if implemented as a web application" (§2.4) |
| API | Node.js + Express, or Spring Boot (Java), or Django/FastAPI (Python) | Any mainstream framework with ORM + JWT/session support satisfies the SRS |
| ORM | Sequelize/Prisma (Node), Hibernate/JPA (Java), SQLAlchemy/Django ORM (Python) | Required to satisfy NFR-06/§13 (parameterized queries) |
| Database | PostgreSQL or MySQL | Explicitly named in §2.4 |
| Auth | JWT (stateless API) or server-side sessions | bcrypt/argon2 for password hashing (FR-06, NFR-04) |
| Reporting/export | Headless PDF renderer (e.g. PDFKit/wkhtmltopdf) + CSV writer | FR-60 |
| Deployment | Single application server + managed DB instance; Docker for packaging | Keeps NFR-19 (scale without re-architecture) open |

The specific stack is a free choice — the architecture above is stack-agnostic and only requires: a relational DB, an ORM/parameterized query layer, server-side session or token auth, and role middleware.

---

## 6. Core Data Flow — Issue & Return (maps to UC-03/UC-04)

**Issue:**
1. Client sends `POST /transactions/issue { memberId, bookId }`
2. Auth middleware validates the session/token and role (Librarian/Admin)
3. Circulation service asks Member service: is member active? (BR-01) — asks Catalog: is a copy available? (BR-02) — checks borrowing limit (BR-03)
4. If all pass: Circulation service creates an `IssueTransaction` row, computes `due_date` from configured borrowing period (BR-04), decrements `available_quantity` (BR-07) — all inside **one DB transaction** (NFR-10/11)
5. Audit module logs the action; response confirms issue to client

**Return:**
1. Client sends `POST /transactions/{id}/return`
2. Circulation service loads the transaction, sets `return_date`, compares to `due_date`
3. If overdue: computes fine via configured fine rate (BR-05, FR-38), creates a `Fine` record
4. Increments `available_quantity` (BR-06), updates transaction status — again as a single atomic DB transaction
5. Audit module logs; response returns fine amount (if any) to client

This atomicity requirement (steps happening as one DB transaction, not several independent writes) is the single most important non-functional constraint in the SRS (NFR-10, NFR-11) and is why a modular monolith with one shared database, rather than split services, is the recommended shape.

---

## 7. Security Architecture (maps to §13, NFR-04–09)

- **Passwords:** bcrypt/argon2 hashing only, never plaintext (FR-06, NFR-04)
- **AuthN:** login issues a JWT or server session; expires after inactivity (§13)
- **AuthZ:** role middleware on every route — Admin/Librarian/Member permission matrix enforced centrally in the Auth module, not duplicated per controller
- **Input handling:** all queries parameterized via ORM (NFR-06, §13) — no raw string-concatenated SQL
- **Transport:** HTTPS enforced in production (NFR-08)
- **Secrets:** DB credentials via environment variables / secrets manager, never in source (NFR-07)
- **Audit trail:** all admin and transaction-affecting actions logged, with credentials excluded from log payloads (§13)

---

## 8. Deployment View

```
                 ┌──────────────────────┐
   Users ───────►│   Reverse proxy /    │
   (HTTPS)       │   Load balancer      │
                 └──────────┬───────────┘
                            │
                 ┌──────────▼───────────┐
                 │   Application server  │
                 │  (API + business      │
                 │   logic, stateless)   │
                 └──────────┬───────────┘
                            │
                 ┌──────────▼───────────┐
                 │   PostgreSQL/MySQL    │
                 │   (primary + backups) │
                 └───────────────────────┘
```

- Application server kept **stateless** (session/token validated per-request) so it can be horizontally scaled later without redesign — directly supports NFR-19/NFR-20 (future barcode scanning, mobile app, notifications can attach as new clients or services against the same API).
- Regular automated DB backups satisfy NFR-12.
- A reverse proxy (nginx or similar) terminates HTTPS and can later host rate limiting or a caching layer for search (NFR-01/02).

---

## 9. Mapping Future Enhancements (§15) onto This Architecture

Because the application layer is modular and stateless, and the client only ever talks to a versioned REST API, the future items in the SRS attach cleanly without re-architecting:

- **Barcode/QR scanning** → new client input method calling the existing Circulation endpoints
- **Email/SMS reminders** → new Notification module subscribing to Circulation events (due-soon, overdue)
- **Mobile app** → new client consuming the same REST API
- **Online fine payment** → extends the Fine/FinePayment module with a payment gateway integration
- **Recommendation engine / AI search** → new read-only service layered on top of Catalog data, no changes to core transactional modules
