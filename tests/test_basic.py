import unittest

from app import create_app
from app.utils import (
    format_money,
    parse_nonnegative_amount,
    parse_positive_amount,
    valid_phone,
)


class BasicApplicationTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "APP_ENV": "testing",
                "SECRET_KEY": "test-secret-key",
            }
        )
        self.client = self.app.test_client()

    def test_public_pages_open_without_database(self):
        for page in ("/login", "/register"):
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)

    def test_private_pages_require_login(self):
        private_pages = (
            "/",
            "/transactions",
            "/transactions/new",
            "/analytics",
            "/budget/personal",
            "/budget/family",
            "/categories",
            "/categories/new",
            "/family",
            "/family/create",
            "/family/join",
            "/settings",
        )

        for page in private_pages:
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_unknown_page_returns_404(self):
        response = self.client.get("/page-that-does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Страница не найдена".encode("utf-8"), response.data)

    def test_post_without_csrf_token_is_rejected(self):
        response = self.client.post(
            "/login",
            data={"email": "test@example.com", "password": "password"},
        )

        self.assertEqual(response.status_code, 400)

    def test_security_headers_are_present(self):
        response = self.client.get("/login")

        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])


class UtilityTest(unittest.TestCase):
    def test_money_formatting(self):
        self.assertEqual(format_money("1250.5", "RUB", "expense"), "−1 250,50 ₽")

    def test_amount_validation(self):
        self.assertEqual(str(parse_positive_amount("10,25")), "10.25")
        self.assertIsNone(parse_positive_amount("-1"))
        self.assertIsNone(parse_positive_amount("1.999"))
        self.assertIsNone(parse_positive_amount("NaN"))
        self.assertEqual(str(parse_nonnegative_amount("0")), "0")
        self.assertIsNone(parse_nonnegative_amount("-0.01"))

    def test_phone_validation(self):
        self.assertTrue(valid_phone("+7 900 000-00-00"))
        self.assertTrue(valid_phone(None))
        self.assertFalse(valid_phone("phone"))


if __name__ == "__main__":
    unittest.main()
