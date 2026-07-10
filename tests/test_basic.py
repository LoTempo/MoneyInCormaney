import unittest

from app import create_app


class BasicApplicationTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret-key",
            }
        )
        self.client = self.app.test_client()

    def test_homepage_opens(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Обзор бюджета".encode("utf-8"), response.data)

    def test_main_pages_open(self):
        pages = (
            "/login",
            "/register",
            "/transactions",
            "/transactions/new",
            "/categories",
            "/categories/new",
            "/family",
            "/family/create",
            "/family/join",
            "/settings",
        )

        for page in pages:
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)

    def test_unknown_page_returns_404(self):
        response = self.client.get("/page-that-does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Страница не найдена".encode("utf-8"), response.data)


if __name__ == "__main__":
    unittest.main()
