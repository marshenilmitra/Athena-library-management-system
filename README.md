# 📚 Athena LMS - Enterprise Library Management System

[![Python](https://img.shields.io/badge/Python-3.14-blue.svg?logo=python)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask_3.1-emerald.svg?logo=flask)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-SQLite%20%7C%20PostgreSQL-indigo.svg)](https://www.sqlite.org/)
[![Tests](https://img.shields.io/badge/Unit_Tests-6_Passed-brightgreen.svg)]()
[![License](https://img.shields.io/badge/License-MIT-orange.svg)]()
**🔗 Live Demo:** https://lms-3s3q.onrender.com
> Note: hosted on Render's free tier — first load may take ~30-50s to wake up if idle.
> A production-ready, full-stack **Enterprise Library Management System (LMS)** compliant with SRS v1.0 specifications and N-tier layered architecture. Designed with high data density, real-time analytics, RBAC permissions, atomic transaction handling, fine ledger processing, and CSV reporting.

---

## 🌟 Architecture & Key Features

### 🏛️ 3-Tier Layered Architecture
```mermaid
graph TD
    Client["🎨 Web Client SPA (HTML5, CSS3, JS ES6+)"] -->|HTTPS / JSON REST API| Gateway["🛡️ Auth & Middleware Gateway"]
    Gateway -->|Session / RBAC Check| Controller["⚡ Flask REST Controllers"]
    
    subgraph Domain Services
        Controller --> AuthSvc["Auth & User Module"]
        Controller --> MemberSvc["Member Registry Module"]
        Controller --> CatalogSvc["Book Catalog Module"]
        Controller --> CircSvc["Circulation Module (Issue/Return)"]
        Controller --> ResSvc["Reservation Module"]
        Controller --> FineSvc["Fine Ledger Module"]
        Controller --> ReportSvc["Reporting Engine"]
    end
    
    CircSvc -->|Atomic DB Tx| DB[("🗄️ Relational Database (SQLite/PostgreSQL)")]
    CatalogSvc --> DB
    MemberSvc --> DB
    FineSvc --> DB
```

### 🗄️ Database Entity-Relationship (ER) Diagram
```mermaid
erDiagram
    USERS ||--o{ MEMBERS : "links user profile"
    MEMBERS ||--o{ ISSUE_TRANSACTIONS : "borrows"
    BOOKS ||--o{ ISSUE_TRANSACTIONS : "checked out in"
    BOOKS ||--o{ RESERVATIONS : "reserved by"
    MEMBERS ||--o{ RESERVATIONS : "places hold"
    ISSUE_TRANSACTIONS ||--o| FINES : "generates fine on return"
    FINES ||--o{ FINE_PAYMENTS : "collects payment"
    AUTHORS ||--o{ BOOKS : "writes"
    PUBLISHERS ||--o{ BOOKS : "publishes"
    CATEGORIES ||--o{ BOOKS : "categorizes"

    USERS {
        int id PK
        string username
        string password_hash
        string role
        string status
    }
    MEMBERS {
        int id PK
        string member_id UK
        string name
        string email UK
        string status
    }
    BOOKS {
        int id PK
        string isbn UK
        string title
        int total_quantity
        int available_quantity
    }
    ISSUE_TRANSACTIONS {
        int id PK
        string transaction_code UK
        date issue_date
        date due_date
        date return_date
        string status
    }
    FINES {
        int id PK
        double amount
        double paid_amount
        string payment_status
    }
```

---

## ✨ Functional Highlights

- 🔐 **Role-Based Access Control (RBAC)**: Distinct permissions for `Admin`, `Librarian`, and `Member` sessions.
- ⚡ **Atomic Book Circulation**: Guaranteed single-transaction checkout and return enforcing:
  - Member active status check (BR-01)
  - Maximum borrowing limit check (BR-03)
  - Outstanding fine threshold restriction (BR-08)
  - Automatic inventory decrement on issue (BR-07) and increment on return (BR-06)
- 💰 **Overdue Fine Engine**: Dynamic overdue day calculation upon return based on configurable daily rates ($1.00/day).
- 🔖 **Hold & Reservation Queuing**: Prevents duplicate holds on out-of-stock titles (FR-46-50).
- 📊 **Executive Analytics & Data Export**: Interactive SVG velocity charts, inventory distribution, and one-click CSV report exports (`Inventory`, `Overdue Books`, `Issued Transactions`).
- 📜 **Enterprise Audit Logging**: Structured JSON logging capturing all administrative, book creation, and transaction actions (NFR-09).

---

## ⚡ Quickstart & Local Setup

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/library-management-system.git
cd library-management-system

# Install Python requirements
python -m pip install flask werkzeug
```

### 2. Run Automated Unit Tests
```bash
python -m unittest backend/test_lms.py
```

### 3. Launch Web Application Server
```bash
python -m backend.server
```
Visit **`http://localhost:5000`** in your browser.

---

## 🔑 Quick Demo Login Credentials

| Role | Username | Default Password | Access Level |
|---|---|---|---|
| 🔑 **Admin** | `admin` | `Admin@123` | Full system control, user management, audit logs, system configuration |
| 📖 **Librarian** | `librarian` | `Lib@123` | Member registration, book management, circulation issue & return, fine collection |
| 👤 **Member** | `member1` | `Mem@123` | Catalog search, active hold reservation, borrowing history, fine ledger |

---

## 🛰️ REST API Specification Summary

| Endpoint | Method | Role Required | Description |
|---|---|---|---|
| `/api/auth/login` | `POST` | Public | Authenticate user & issue session token |
| `/api/books` | `GET` | Authenticated | Search & filter book catalog |
| `/api/books` | `POST` | Admin / Librarian | Add new book title |
| `/api/transactions/issue` | `POST` | Admin / Librarian | Atomic checkout issue to member card |
| `/api/transactions/{id}/return` | `POST` | Admin / Librarian | Record return & calculate overdue fine |
| `/api/reservations` | `POST` | Member | Place hold reservation on out-of-stock title |
| `/api/fines/{id}/pay` | `POST` | Admin / Librarian | Record fine payment collection |
| `/api/reports/export/{type}` | `GET` | Admin / Librarian | Download CSV report export |
| `/api/docs` | `GET` | Public | OpenAPI 3.0 API Specification JSON schema |

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
## Author
**Marshenil Mitra** — [GitHub](https://github.com/marshenilmitra) · [LinkedIn](https://www.linkedin.com/in/marshenilmitra)
