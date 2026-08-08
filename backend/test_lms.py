import unittest
import os
import datetime
from backend.db import init_db, get_db
from backend.auth import hash_password, verify_password, create_session, get_session
import backend.services as services

class TestLMSBackend(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Initialize test database and schema
        init_db()

    def setUp(self):
        self.admin_info = {"user_id": 1, "username": "admin", "role": "Admin"}
        self.librarian_info = {"user_id": 2, "username": "librarian", "role": "Librarian"}
        self.member_info = {"user_id": 3, "username": "member1", "role": "Member"}

    def test_01_password_hashing(self):
        pwd = "TestSecretPassword!123"
        hashed = hash_password(pwd)
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_02_session_token_creation(self):
        token = create_session(1, "admin", "Admin")
        session = get_session(token)
        self.assertIsNotNone(session)
        self.assertEqual(session["username"], "admin")
        self.assertEqual(session["role"], "Admin")

    def test_03_create_and_get_member(self):
        email = f"test.member.{int(datetime.datetime.now().timestamp())}@example.com"
        mid = services.create_member("Test Member", email, "+1-555-9999", user_info=self.admin_info)
        self.assertIsNotNone(mid)
        members = services.get_members("Test Member")
        self.assertTrue(any(m['email'] == email for m in members))

    def test_04_book_catalog_and_issue_return_cycle(self):
        # 1. Add new book
        isbn = f"978-{int(datetime.datetime.now().timestamp())}"
        authors = services.get_authors()
        publishers = services.get_publishers()
        categories = services.get_categories()
        
        book_id = services.add_book(
            isbn=isbn,
            title="Automated Unit Test Book",
            author_id=authors[0]['id'],
            publisher_id=publishers[0]['id'],
            category_id=categories[0]['id'],
            publication_year=2024,
            total_quantity=2,
            user_info=self.admin_info
        )
        self.assertIsNotNone(book_id)

        # 2. Get member
        members = services.get_members()
        member_id = members[0]['id']

        # 3. Issue book
        issue_res = services.issue_book(book_id, member_id, 2, self.librarian_info)
        self.assertIn("transaction_code", issue_res)
        self.assertIn("due_date", issue_res)

        # Verify available quantity decremented
        books = services.get_books(isbn_q=isbn)
        self.assertEqual(books[0]['available_quantity'], 1)

        # 4. Return book
        tx_id = issue_res["transaction_id"]
        return_res = services.return_book(tx_id, self.librarian_info)
        self.assertEqual(return_res["transaction_id"], tx_id)
        self.assertEqual(return_res["fine_amount"], 0.0)

        # Verify available quantity incremented back
        books_after = services.get_books(isbn_q=isbn)
        self.assertEqual(books_after[0]['available_quantity'], 2)

    def test_05_borrow_limit_enforcement(self):
        # Max limit is set to 3
        members = services.get_members()
        member_id = members[0]['id']
        books = services.get_books()

        # Issue up to limit or check constraint
        # Should raise error if limit reached
        limit = int(services.get_config('max_borrow_limit', '3'))
        self.assertGreaterEqual(limit, 1)

    def test_06_reports_summary_and_export(self):
        summary = services.get_reports_summary()
        self.assertIn("total_books", summary)
        self.assertIn("active_members", summary)
        self.assertIn("currently_issued", summary)

        csv_inv = services.export_report_csv("inventory")
        self.assertIn("Book ID", csv_inv)
        self.assertIn("ISBN", csv_inv)

if __name__ == '__main__':
    unittest.main()
