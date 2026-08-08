/* ==========================================================================
   Athena Library Management System (LMS) - Executive Client Logic
   ========================================================================== */

let currentUser = null;
let authToken = localStorage.getItem('lms_token') || null;

// Application State Caches
let categoriesCache = [];
let authorsCache = [];
let publishersCache = [];
let booksCache = [];
let membersCache = [];
let catalogViewMode = 'grid'; // 'grid' or 'table'

// ---------------------------------------------------------------------------
// PB-10 FIX: Client-side KPI stats cache (30s TTL)
// Prevents /api/reports/summary being called on every tab switch
// ---------------------------------------------------------------------------
let _statsCacheTs = 0;
let _statsCache = null;
const STATS_CACHE_TTL_MS = 30000; // 30 seconds

// ---------------------------------------------------------------------------
// PB-11 / PB-12 FIX: Debounce utility
// Prevents excessive re-renders and API calls on rapid keystrokes
// ---------------------------------------------------------------------------
function debounce(fn, delayMs) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delayMs);
    };
}

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    setupEventListeners();
    
    if (authToken) {
        try {
            const res = await apiRequest('/api/auth/me');
            if (res.user) {
                currentUser = res.user;
                if (res.member_info) currentUser.member_info = res.member_info;
                onLoginSuccess();
                return;
            }
        } catch (e) {
            console.warn("Session restore failed:", e);
            logout();
        }
    }

    showLoginModal();
}

function setupEventListeners() {
    // Nav Tab Buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });

    // Theme Toggle & Shortcuts
    document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);
    document.getElementById('refreshBtn').addEventListener('click', refreshCurrentTab);
    document.getElementById('logoutBtn').addEventListener('click', logout);

    // Keyboard Shortcut (Ctrl + K) to focus Search Bar
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            const searchInput = document.getElementById('catalogSearchInput');
            if (searchInput) searchInput.focus();
        }
    });

    // Search and Filter Listeners
    // PB-11 FIX: Debounce search input — prevents DOM re-render on every keystroke
    document.getElementById('catalogSearchInput').addEventListener('input', debounce(filterBooks, 300));
    document.getElementById('catalogCategoryFilter').addEventListener('change', filterBooks);
    document.getElementById('catalogAvailabilityFilter').addEventListener('change', filterBooks);
    // PB-12 FIX: Debounce member search — prevents API call on every keystroke
    document.getElementById('memberSearchInput').addEventListener('input', debounce(fetchMembers, 400));

    // Form Handlers
    document.getElementById('loginForm').addEventListener('submit', handleLogin);
    document.getElementById('bookForm').addEventListener('submit', handleSaveBook);
    document.getElementById('memberForm').addEventListener('submit', handleSaveMember);
    document.getElementById('issueBookForm').addEventListener('submit', handleIssueBook);
    document.getElementById('userForm').addEventListener('submit', handleCreateUser);
    document.getElementById('payFineForm').addEventListener('submit', handlePayFine);
    document.getElementById('configForm').addEventListener('submit', handleSaveConfig);

    // Modal Open Buttons
    document.getElementById('openAddBookModalBtn').addEventListener('click', () => openBookModal());
    document.getElementById('openAddMemberModalBtn').addEventListener('click', () => openModal('memberModal'));
    document.getElementById('openAddUserModalBtn').addEventListener('click', () => openModal('userModal'));
}

// --- API Client ---
async function apiRequest(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    const config = { method, headers };
    if (body) config.body = JSON.stringify(body);

    const response = await fetch(endpoint, config);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.error || 'Server request failed');
    }
    return data;
}

// --- Authentication Flow ---
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errDiv = document.getElementById('loginError');

    errDiv.classList.add('hidden');

    try {
        const res = await apiRequest('/api/auth/login', 'POST', { username, password });
        authToken = res.token;
        localStorage.setItem('lms_token', authToken);
        currentUser = {
            user_id: res.user.id,
            username: res.user.username,
            role: res.user.role,
            member_info: res.user.member_info
        };
        closeModal('loginModal');
        onLoginSuccess();
        showToast(`Signed in successfully as ${currentUser.username}`, 'success');
    } catch (err) {
        errDiv.textContent = err.message;
        errDiv.classList.remove('hidden');
    }
}

function fillQuickLogin(username, password) {
    document.getElementById('loginUsername').value = username;
    document.getElementById('loginPassword').value = password;
}

function onLoginSuccess() {
    document.getElementById('userName').textContent = currentUser.username;
    document.getElementById('userRoleBadge').textContent = currentUser.role;
    document.getElementById('userAvatar').textContent = currentUser.username.charAt(0).toUpperCase();
    
    document.querySelectorAll('.staff-only').forEach(el => {
        if (currentUser.role === 'Admin' || currentUser.role === 'Librarian') {
            el.classList.remove('hidden');
        } else {
            el.classList.add('hidden');
        }
    });

    document.querySelectorAll('.admin-only').forEach(el => {
        if (currentUser.role === 'Admin') {
            el.classList.remove('hidden');
        } else {
            el.classList.add('hidden');
        }
    });

    loadDropdowns();
    loadStatsSummary();
    switchTab('catalog');
}

function logout() {
    if (authToken) {
        apiRequest('/api/auth/logout', 'POST').catch(() => {});
    }
    authToken = null;
    currentUser = null;
    localStorage.removeItem('lms_token');
    showLoginModal();
}

function showLoginModal() {
    document.getElementById('userCard').style.display = 'none';
    openModal('loginModal');
}

// --- Navigation & Tabs ---
function switchTab(tabName) {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

    const btn = document.querySelector(`.nav-btn[data-tab="${tabName}"]`);
    const pane = document.getElementById(`tab-${tabName}`);

    if (btn) btn.classList.add('active');
    if (pane) pane.classList.add('active');

    const titles = {
        catalog: ["Catalog Directory", "Browse inventory, filter availability, and manage reservations"],
        circulation: ["Circulation Desk", "Issue available inventory & record returns"],
        members: ["Member Registry", "Manage registered library cardholders"],
        reservations: ["Active Holds", "Queue and track holds on out-of-stock titles"],
        fines: ["Fine Ledger", "Track overdue penalties and record settlements"],
        reports: ["Executive Reports", "Operational summaries and one-click CSV exports"],
        admin: ["Control Center", "User accounts, borrowing rules, and audit logs"]
    };

    if (titles[tabName]) {
        document.getElementById('currentTabTitle').textContent = titles[tabName][0];
        document.getElementById('currentTabSubtitle').textContent = titles[tabName][1];
    }

    refreshCurrentTab();
}

function refreshCurrentTab() {
    const activePane = document.querySelector('.tab-pane.active');
    if (!activePane) return;
    const tabId = activePane.id.replace('tab-', '');

    loadStatsSummary();

    if (tabId === 'catalog') fetchBooks();
    else if (tabId === 'circulation') { fetchIssuedTransactions(); loadCirculationDropdowns(); }
    else if (tabId === 'members') fetchMembers();
    else if (tabId === 'reservations') fetchReservations();
    else if (tabId === 'fines') fetchFines();
    else if (tabId === 'reports') loadStatsSummary();
    else if (tabId === 'admin') { fetchUsers(); fetchConfig(); fetchAuditLogs(); }
}

// --- Dropdown Caching ---
async function loadDropdowns() {
    try {
        const [cats, auths, pubs] = await Promise.all([
            apiRequest('/api/categories'),
            apiRequest('/api/authors'),
            apiRequest('/api/publishers')
        ]);
        categoriesCache = cats;
        authorsCache = auths;
        publishersCache = pubs;

        const catFilter = document.getElementById('catalogCategoryFilter');
        catFilter.innerHTML = '<option value="">All Categories</option>' +
            cats.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

        document.getElementById('bookAuthor').innerHTML = auths.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
        document.getElementById('bookPublisher').innerHTML = pubs.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
        document.getElementById('bookCategory').innerHTML = cats.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    } catch (e) {
        console.error("Dropdown load failed:", e);
    }
}

async function loadCirculationDropdowns() {
    try {
        const [members, books] = await Promise.all([
            apiRequest('/api/members'),
            apiRequest('/api/books?availability=Available')
        ]);
        
        const mSel = document.getElementById('issueMemberSelect');
        mSel.innerHTML = '<option value="">-- Select Active Member --</option>' +
            members.filter(m => m.status === 'Active').map(m => `<option value="${m.id}">${m.name} (${m.member_id})</option>`).join('');

        const bSel = document.getElementById('issueBookSelect');
        bSel.innerHTML = '<option value="">-- Select Available Title --</option>' +
            books.map(b => `<option value="${b.id}">${b.title} (Avail: ${b.available_quantity})</option>`).join('');
    } catch (e) {
        console.error("Circulation dropdown error:", e);
    }
}

// --- Stats Summary KPI ---
// PB-10 FIX: 30-second client-side cache — avoids 5 DB queries on every tab switch
async function loadStatsSummary(forceRefresh = false) {
    if (!authToken) {
        document.getElementById('statsGrid').style.display = 'none';
        return;
    }
    document.getElementById('statsGrid').style.display = 'grid';

    const now = Date.now();
    if (!forceRefresh && _statsCache && (now - _statsCacheTs) < STATS_CACHE_TTL_MS) {
        // Serve from cache — no network request needed
        _applyStats(_statsCache);
        return;
    }

    try {
        const data = await apiRequest('/api/reports/summary');
        _statsCache = data;
        _statsCacheTs = now;
        _applyStats(data);
    } catch (e) {}
}

function _applyStats(data) {
    document.getElementById('statTotalBooks').textContent = data.total_books;
    document.getElementById('statAvailableCopies').textContent = data.available_copies;
    document.getElementById('statIssuedBooks').textContent = data.currently_issued;
    document.getElementById('statOverdueBooks').textContent = data.overdue_count;
}

// --- TAB: Catalog & Books (Grid vs Table View Switcher) ---
async function fetchBooks() {
    try {
        booksCache = await apiRequest('/api/books');
        renderBooks(booksCache);
    } catch (err) {
        showToast("Error loading catalog: " + err.message, 'error');
    }
}

function switchCatalogView(mode) {
    catalogViewMode = mode;
    document.getElementById('viewGridBtn').classList.toggle('active', mode === 'grid');
    document.getElementById('viewTableBtn').classList.toggle('active', mode === 'table');
    filterBooks();
}

function filterBooks() {
    const q = document.getElementById('catalogSearchInput').value.toLowerCase();
    const cat = document.getElementById('catalogCategoryFilter').value;
    const avail = document.getElementById('catalogAvailabilityFilter').value;

    const filtered = booksCache.filter(b => {
        const matchQ = b.title.toLowerCase().includes(q) || b.author_name.toLowerCase().includes(q) || b.isbn.includes(q);
        const matchCat = cat === "" || b.category_id == cat;
        const matchAvail = avail === "" || (avail === "Available" ? b.available_quantity > 0 : b.available_quantity === 0);
        return matchQ && matchCat && matchAvail;
    });

    renderBooks(filtered);
}

function renderBooks(books) {
    const container = document.getElementById('booksGrid');
    if (books.length === 0) {
        container.innerHTML = `<div class="card text-muted" style="grid-column: 1/-1; text-align: center; padding: 2rem;">No matching catalog items found.</div>`;
        return;
    }

    if (catalogViewMode === 'table') {
        container.innerHTML = `
            <div class="card" style="grid-column: 1/-1;">
                <div class="table-container">
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>ISBN</th>
                                <th>Book Title</th>
                                <th>Author</th>
                                <th>Category</th>
                                <th>Total Stock</th>
                                <th>Available</th>
                                <th>Status</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${books.map(b => {
                                const isAvail = b.available_quantity > 0;
                                const badgeClass = isAvail ? 'badge-success' : 'badge-danger';
                                let actionBtn = '';
                                if (currentUser?.role === 'Admin' || currentUser?.role === 'Librarian') {
                                    actionBtn = `<button class="btn btn-outline btn-sm" onclick="editBook(${b.id})">✏️ Edit</button>`;
                                } else if (!isAvail) {
                                    actionBtn = `<button class="btn btn-primary btn-sm" onclick="reserveBookPrompt(${b.id})">🔖 Reserve</button>`;
                                }
                                return `
                                    <tr>
                                        <td style="font-family:var(--font-mono); font-size:0.8rem;">${b.isbn}</td>
                                        <td><strong>${escapeHtml(b.title)}</strong></td>
                                        <td>${escapeHtml(b.author_name)}</td>
                                        <td><span class="category-tag">${escapeHtml(b.category_name)}</span></td>
                                        <td>${b.total_quantity}</td>
                                        <td><strong>${b.available_quantity}</strong></td>
                                        <td><span class="badge ${badgeClass}">${isAvail ? 'Available' : 'Out of Stock'}</span></td>
                                        <td>${actionBtn}</td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        return;
    }

    // Default Grid View
    container.innerHTML = books.map(b => {
        const isAvail = b.available_quantity > 0;
        const badgeClass = isAvail ? 'badge-success' : 'badge-danger';
        const badgeText = isAvail ? `${b.available_quantity} Available` : 'Out of Stock';

        let actionBtn = '';
        if (currentUser?.role === 'Admin' || currentUser?.role === 'Librarian') {
            actionBtn = `<button class="btn btn-outline btn-sm" onclick="editBook(${b.id})">✏️ Edit</button>`;
        } else if (!isAvail) {
            actionBtn = `<button class="btn btn-primary btn-sm" onclick="reserveBookPrompt(${b.id})">🔖 Reserve Hold</button>`;
        }

        return `
            <div class="book-card">
                <div class="book-header">
                    <span class="badge ${badgeClass}">${badgeText}</span>
                    <span class="category-tag">${escapeHtml(b.category_name)}</span>
                </div>
                <h4 class="book-title">${escapeHtml(b.title)}</h4>
                <p class="book-author">By ${escapeHtml(b.author_name)}</p>
                <div class="book-meta">
                    <span class="book-isbn">ISBN: ${b.isbn}</span>
                    <span style="font-weight: 500;">${b.total_quantity} copies total</span>
                </div>
                ${actionBtn ? `<div style="display:flex; justify-content:flex-end; margin-top:0.4rem;">${actionBtn}</div>` : ''}
            </div>
        `;
    }).join('');
}

function openBookModal(book = null) {
    document.getElementById('bookModalId').value = book ? book.id : '';
    document.getElementById('bookModalTitle').textContent = book ? 'Edit Book Details' : 'Add New Title';
    document.getElementById('bookIsbn').value = book ? book.isbn : '';
    document.getElementById('bookTitle').value = book ? book.title : '';
    document.getElementById('bookAuthor').value = book ? book.author_id : (authorsCache[0]?.id || '');
    document.getElementById('bookPublisher').value = book ? book.publisher_id : (publishersCache[0]?.id || '');
    document.getElementById('bookCategory').value = book ? book.category_id : (categoriesCache[0]?.id || '');
    document.getElementById('bookYear').value = book ? book.publication_year : 2024;
    document.getElementById('bookTotalQty').value = book ? book.total_quantity : 1;
    document.getElementById('bookStatus').value = book ? book.status : 'Active';

    openModal('bookModal');
}

function editBook(id) {
    const book = booksCache.find(b => b.id === id);
    if (book) openBookModal(book);
}

async function handleSaveBook(e) {
    e.preventDefault();
    const id = document.getElementById('bookModalId').value;
    const body = {
        isbn: document.getElementById('bookIsbn').value,
        title: document.getElementById('bookTitle').value,
        author_id: document.getElementById('bookAuthor').value,
        publisher_id: document.getElementById('bookPublisher').value,
        category_id: document.getElementById('bookCategory').value,
        publication_year: document.getElementById('bookYear').value,
        total_quantity: document.getElementById('bookTotalQty').value,
        status: document.getElementById('bookStatus').value
    };

    try {
        if (id) {
            await apiRequest(`/api/books/${id}`, 'PUT', body);
            showToast("Book updated successfully", 'success');
        } else {
            await apiRequest('/api/books', 'POST', body);
            showToast("Book added to catalog", 'success');
        }
        closeModal('bookModal');
        fetchBooks();
    } catch (err) {
        showToast("Error saving book: " + err.message, 'error');
    }
}

// --- TAB: Circulation (Issue / Return) ---
async function fetchIssuedTransactions() {
    try {
        const txs = await apiRequest('/api/transactions?status=Issued');
        const tbody = document.getElementById('issuedTransactionsTableBody');
        
        if (txs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-muted" style="text-align:center;">No active issued books.</td></tr>`;
            return;
        }

        tbody.innerHTML = txs.map(t => {
            const isOverdue = new Date(t.due_date) < new Date();
            const statusBadge = isOverdue ? `<span class="badge badge-danger">Overdue</span>` : `<span class="badge badge-info">Issued</span>`;
            
            return `
                <tr>
                    <td style="font-family:var(--font-mono); font-size:0.8rem;"><strong>${t.transaction_code}</strong></td>
                    <td>${escapeHtml(t.book_title)}</td>
                    <td>${escapeHtml(t.member_name)} (${t.member_code})</td>
                    <td>${t.issue_date}</td>
                    <td>${t.due_date}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <button class="btn btn-primary btn-sm" onclick="returnBook(${t.id})">↩️ Record Return</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        showToast("Failed to load active transactions: " + err.message, 'error');
    }
}

async function handleIssueBook(e) {
    e.preventDefault();
    const member_id = document.getElementById('issueMemberSelect').value;
    const book_id = document.getElementById('issueBookSelect').value;

    try {
        const res = await apiRequest('/api/transactions/issue', 'POST', { member_id, book_id });
        showToast(`Book checkout confirmed! Due date: ${res.due_date}`, 'success');
        fetchIssuedTransactions();
        loadCirculationDropdowns();
    } catch (err) {
        showToast("Issue failed: " + err.message, 'error');
    }
}

async function returnBook(tx_id) {
    if (!confirm("Confirm book return?")) return;
    try {
        const res = await apiRequest(`/api/transactions/${tx_id}/return`, 'POST');
        if (res.fine_amount > 0) {
            showToast(`Book returned! Overdue fine of $${res.fine_amount.toFixed(2)} charged.`, 'error');
        } else {
            showToast("Book returned on time with no fine.", 'success');
        }
        fetchIssuedTransactions();
        loadCirculationDropdowns();
    } catch (err) {
        showToast("Return failed: " + err.message, 'error');
    }
}

// --- TAB: Members Directory ---
async function fetchMembers() {
    const q = document.getElementById('memberSearchInput').value;
    try {
        const endpoint = q ? `/api/members?q=${encodeURIComponent(q)}` : '/api/members';
        membersCache = await apiRequest(endpoint);
        const tbody = document.getElementById('membersTableBody');

        if (membersCache.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-muted" style="text-align:center;">No members found.</td></tr>`;
            return;
        }

        tbody.innerHTML = membersCache.map(m => `
            <tr>
                <td style="font-family:var(--font-mono);"><strong>${m.member_id}</strong></td>
                <td>${escapeHtml(m.name)}</td>
                <td>${m.email}</td>
                <td>${m.phone || '-'}</td>
                <td>${m.username || 'Unlinked'}</td>
                <td><span class="badge ${m.status === 'Active' ? 'badge-success' : 'badge-danger'}">${m.status}</span></td>
                <td>
                    <button class="btn btn-outline btn-sm" onclick="toggleMemberStatus(${m.id}, '${m.status}')">
                        ${m.status === 'Active' ? 'Deactivate' : 'Activate'}
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        showToast("Error loading members: " + err.message, 'error');
    }
}

async function handleSaveMember(e) {
    e.preventDefault();
    const body = {
        name: document.getElementById('memberName').value,
        email: document.getElementById('memberEmail').value,
        phone: document.getElementById('memberPhone').value
    };

    try {
        await apiRequest('/api/members', 'POST', body);
        showToast("Member profile registered", 'success');
        closeModal('memberModal');
        fetchMembers();
    } catch (err) {
        showToast("Error adding member: " + err.message, 'error');
    }
}

async function toggleMemberStatus(id, currentStatus) {
    const newStatus = currentStatus === 'Active' ? 'Inactive' : 'Active';
    const member = membersCache.find(m => m.id === id);
    try {
        await apiRequest(`/api/members/${id}`, 'PUT', {
            name: member.name,
            email: member.email,
            phone: member.phone,
            status: newStatus
        });
        showToast(`Member status set to ${newStatus}`, 'success');
        fetchMembers();
    } catch (err) {
        showToast("Update failed: " + err.message, 'error');
    }
}

// --- TAB: Reservations ---
async function fetchReservations() {
    try {
        const resList = await apiRequest('/api/reservations');
        const tbody = document.getElementById('reservationsTableBody');

        if (resList.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-muted" style="text-align:center;">No reservations queued.</td></tr>`;
            return;
        }

        tbody.innerHTML = resList.map(r => `
            <tr>
                <td style="font-family:var(--font-mono);">#${r.id}</td>
                <td>${escapeHtml(r.book_title)}</td>
                <td>${escapeHtml(r.member_name)} (${r.member_code})</td>
                <td>${r.reservation_date}</td>
                <td><span class="badge ${r.status === 'Active' ? 'badge-warning' : 'badge-secondary'}">${r.status}</span></td>
                <td>
                    ${r.status === 'Active' ? `<button class="btn btn-outline btn-sm" onclick="cancelReservation(${r.id})">Cancel</button>` : '-'}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        showToast("Failed to load reservations: " + err.message, 'error');
    }
}

async function reserveBookPrompt(book_id) {
    if (!currentUser?.member_info) {
        alert("Only registered members can place book reservations.");
        return;
    }
    if (!confirm("Place a reservation hold for this title?")) return;
    try {
        await apiRequest('/api/reservations', 'POST', { book_id });
        showToast("Reservation hold placed!", 'success');
    } catch (err) {
        showToast("Reservation failed: " + err.message, 'error');
    }
}

async function cancelReservation(rid) {
    try {
        await apiRequest(`/api/reservations/${rid}/cancel`, 'POST');
        showToast("Reservation cancelled", 'success');
        fetchReservations();
    } catch (err) {
        showToast("Cancellation failed: " + err.message, 'error');
    }
}

// --- TAB: Fines ---
async function fetchFines() {
    try {
        const fines = await apiRequest('/api/fines');
        const tbody = document.getElementById('finesTableBody');

        if (fines.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-muted" style="text-align:center;">No fines recorded.</td></tr>`;
            return;
        }

        tbody.innerHTML = fines.map(f => {
            const rem = (f.amount - f.paid_amount).toFixed(2);
            const badgeClass = f.payment_status === 'Paid' ? 'badge-success' : (f.payment_status === 'Partial' ? 'badge-warning' : 'badge-danger');
            
            let payBtn = '';
            if (f.payment_status !== 'Paid' && (currentUser?.role === 'Admin' || currentUser?.role === 'Librarian')) {
                payBtn = `<button class="btn btn-primary btn-sm" onclick="openPayFineModal(${f.id}, ${rem})">💵 Collect Payment</button>`;
            }

            return `
                <tr>
                    <td style="font-family:var(--font-mono);">#${f.id}</td>
                    <td style="font-family:var(--font-mono);">${f.transaction_code}</td>
                    <td>${escapeHtml(f.member_name)} (${f.member_code})</td>
                    <td>${escapeHtml(f.book_title)}</td>
                    <td style="font-family:var(--font-mono); font-weight:600;">$${f.amount.toFixed(2)}</td>
                    <td style="font-family:var(--font-mono);">$${f.paid_amount.toFixed(2)}</td>
                    <td><span class="badge ${badgeClass}">${f.payment_status}</span></td>
                    <td>${payBtn}</td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        showToast("Failed to load fines: " + err.message, 'error');
    }
}

function openPayFineModal(fine_id, remaining_amount) {
    document.getElementById('payFineId').value = fine_id;
    document.getElementById('payFineBalance').textContent = `$${remaining_amount.toFixed(2)}`;
    document.getElementById('payFineAmount').value = remaining_amount.toFixed(2);
    openModal('payFineModal');
}

async function handlePayFine(e) {
    e.preventDefault();
    const fid = document.getElementById('payFineId').value;
    const amount = document.getElementById('payFineAmount').value;

    try {
        await apiRequest(`/api/fines/${fid}/pay`, 'POST', { amount_paid: amount });
        showToast("Fine payment recorded", 'success');
        closeModal('payFineModal');
        fetchFines();
    } catch (err) {
        showToast("Payment error: " + err.message, 'error');
    }
}

// --- Reports CSV Export (SECURITY: token sent via Authorization header, not URL param) ---
async function exportReport(reportType) {
    try {
        const response = await fetch(`/api/reports/export/${reportType}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || 'Export failed');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `lms_${reportType}_report.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast(`${reportType.charAt(0).toUpperCase() + reportType.slice(1)} report downloaded`, 'success');
    } catch (err) {
        showToast('Export failed: ' + err.message, 'error');
    }
}

// --- TAB: Admin & Configuration ---
async function fetchUsers() {
    try {
        const users = await apiRequest('/api/users');
        const tbody = document.getElementById('usersTableBody');
        tbody.innerHTML = users.map(u => `
            <tr>
                <td style="font-family:var(--font-mono);">#${u.id}</td>
                <td><strong>${escapeHtml(u.username)}</strong></td>
                <td><span class="badge badge-info">${u.role}</span></td>
                <td><span class="badge ${u.status === 'Active' ? 'badge-success' : 'badge-danger'}">${u.status}</span></td>
                <td>
                    ${u.username !== 'admin' ? `
                        <button class="btn btn-outline btn-sm" onclick="toggleUserStatus(${u.id}, '${u.role}', '${u.status}')">
                            ${u.status === 'Active' ? 'Deactivate' : 'Activate'}
                        </button>
                    ` : '-'}
                </td>
            </tr>
        `).join('');
    } catch (err) {}
}

async function handleCreateUser(e) {
    e.preventDefault();
    const body = {
        username: document.getElementById('userUsername').value,
        password: document.getElementById('userPassword').value,
        role: document.getElementById('userRole').value
    };

    try {
        await apiRequest('/api/users', 'POST', body);
        showToast("User account created", 'success');
        closeModal('userModal');
        fetchUsers();
    } catch (err) {
        showToast("Error creating user: " + err.message, 'error');
    }
}

async function toggleUserStatus(id, role, currentStatus) {
    const newStatus = currentStatus === 'Active' ? 'Inactive' : 'Active';
    try {
        await apiRequest(`/api/users/${id}`, 'PUT', { role, status: newStatus });
        showToast(`User status set to ${newStatus}`, 'success');
        fetchUsers();
    } catch (err) {
        showToast("Update failed: " + err.message, 'error');
    }
}

async function fetchConfig() {
    try {
        const config = await apiRequest('/api/config');
        config.forEach(item => {
            if (item.key === 'max_borrow_limit') document.getElementById('configMaxLimit').value = item.value;
            if (item.key === 'borrow_period_days') document.getElementById('configBorrowDays').value = item.value;
            if (item.key === 'overdue_fine_rate') document.getElementById('configFineRate').value = item.value;
        });
    } catch (err) {}
}

async function handleSaveConfig(e) {
    e.preventDefault();
    const body = {
        max_borrow_limit: document.getElementById('configMaxLimit').value,
        borrow_period_days: document.getElementById('configBorrowDays').value,
        overdue_fine_rate: document.getElementById('configFineRate').value
    };

    try {
        await apiRequest('/api/config', 'PUT', body);
        showToast("System settings updated", 'success');
    } catch (err) {
        showToast("Save error: " + err.message, 'error');
    }
}

async function fetchAuditLogs() {
    try {
        const logs = await apiRequest('/api/audit-logs');
        const tbody = document.getElementById('auditLogsTableBody');
        tbody.innerHTML = logs.map(l => `
            <tr>
                <td style="white-space:nowrap; font-size:0.78rem; font-family:var(--font-mono); color:var(--text-tertiary);">${l.timestamp}</td>
                <td><strong>${escapeHtml(l.username || 'System')}</strong></td>
                <td><span class="badge badge-info">${l.action}</span></td>
                <td>${escapeHtml(l.details || '')}</td>
            </tr>
        `).join('');
    } catch (err) {}
}

// --- Utilities & UI Helpers ---
function openModal(id) {
    document.getElementById(id).classList.add('show');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('show');
}

function toggleTheme() {
    const body = document.body;
    const isDark = body.getAttribute('data-theme') === 'dark';
    if (isDark) {
        body.removeAttribute('data-theme');
        document.getElementById('themeToggleBtn').textContent = '🌙';
    } else {
        body.setAttribute('data-theme', 'dark');
        document.getElementById('themeToggleBtn').textContent = '☀️';
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 4000);
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>"']/g, function(m) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
}
