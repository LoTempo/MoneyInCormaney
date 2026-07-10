import os
import re
import secrets
import unittest
from contextlib import ExitStack
from datetime import date
from unittest.mock import patch

import psycopg
from psycopg.rows import dict_row

from app import create_app


class NoCommitConnection:
    """Run real SQL while preventing application routes from committing test data."""

    def __init__(self, connection):
        self.connection = connection

    def execute(self, *args, **kwargs):
        return self.connection.execute(*args, **kwargs)

    def commit(self):
        pass

    def rollback(self):
        pass


@unittest.skipUnless(
    os.getenv("RUN_DATABASE_TESTS") == "1",
    "Set RUN_DATABASE_TESTS=1 to run PostgreSQL integration tests.",
)
class DatabaseIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "APP_ENV": "testing"})
        config = self.app.config
        self.connection = psycopg.connect(
            host=config["DATABASE_HOST"],
            port=config["DATABASE_PORT"],
            dbname=config["DATABASE_NAME"],
            user=config["DATABASE_USER"],
            password=config["DATABASE_PASSWORD"],
            row_factory=dict_row,
        )
        self.database = NoCommitConnection(self.connection)
        self.patches = ExitStack()
        for module_name in (
            "app.analytics",
            "app.auth",
            "app.budget",
            "app.categories",
            "app.dashboard",
            "app.family",
            "app.settings",
            "app.transactions",
        ):
            self.patches.enter_context(
                patch(f"{module_name}.get_db", return_value=self.database)
            )

        self.clients = {
            "owner": self.app.test_client(),
            "member": self.app.test_client(),
            "removed": self.app.test_client(),
        }
        self.test_marker = secrets.token_hex(8)
        self.emails = {}

    def tearDown(self):
        self.patches.close()
        self.connection.rollback()
        remaining = self.connection.execute(
            "SELECT COUNT(*) AS count FROM users WHERE email LIKE %s",
            (f"integration-{self.test_marker}-%",),
        ).fetchone()["count"]
        self.connection.rollback()
        self.connection.close()
        self.assertEqual(remaining, 0, "Integration test data was not rolled back.")

    def csrf_from(self, client, path):
        response = client.get(path)
        self.assertEqual(response.status_code, 200, path)
        match = re.search(rb'name="_csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(match, path)
        return match.group(1).decode("utf-8")

    def register(self, client_name):
        client = self.clients[client_name]
        email = f"integration-{self.test_marker}-{client_name}@example.test"
        self.emails[client_name] = email
        token = self.csrf_from(client, "/register")
        response = client.post(
            "/register",
            data={
                "_csrf_token": token,
                "name": client_name.title(),
                "email": email,
                "phone": "+7 900 111-22-33",
                "password": "Test-password-123",
                "password_confirm": "Test-password-123",
                "agreement": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        return self.connection.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,),
        ).fetchone()["id"]

    def create_category(self, client, name, category_type, scope, parent_id=""):
        token = self.csrf_from(client, f"/categories/new?scope={scope}")
        response = client.post(
            "/categories/new",
            data={
                "_csrf_token": token,
                "scope": scope,
                "name": name,
                "type": category_type,
                "parent_id": str(parent_id) if parent_id else "",
                "icon": "T",
                "color": "#2563eb",
            },
        )
        self.assertEqual(response.status_code, 302)
        return self.connection.execute(
            "SELECT id FROM categories WHERE name = %s",
            (name,),
        ).fetchone()["id"]

    def create_transaction(
        self,
        client,
        scope,
        form_type,
        category_id,
        amount,
        description,
        expense_source="budget",
    ):
        token = self.csrf_from(client, f"/transactions/new?scope={scope}")
        return client.post(
            "/transactions/new",
            data={
                "_csrf_token": token,
                "scope": scope,
                "type": form_type,
                "expense_source": expense_source,
                "amount": str(amount),
                "date": date.today().isoformat(),
                "category_id": str(category_id),
                "description": description,
                "note": "Integration test",
            },
        )

    def join_family(self, client, invite_code):
        token = self.csrf_from(client, "/family/join")
        response = client.post(
            "/family/join",
            data={"_csrf_token": token, "invite_code": invite_code},
        )
        self.assertEqual(response.status_code, 302)

    def test_personal_family_savings_limits_analytics_and_permissions(self):
        owner_id = self.register("owner")
        owner = self.clients["owner"]

        # Family is optional: all personal pages work immediately after registration.
        for path in ("/", "/transactions", "/categories", "/analytics", "/budget/personal"):
            self.assertEqual(owner.get(path).status_code, 200, path)

        expense_category = self.create_category(
            owner, "Personal Expense", "expense", "personal"
        )
        savings_category = self.create_category(
            owner, "Personal Savings", "savings", "personal"
        )

        token = self.csrf_from(owner, "/")
        response = owner.post(
            "/budget/personal/limit",
            data={
                "_csrf_token": token,
                "spending_limit": "5000",
                "return_to": "home",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.assertEqual(
            self.create_transaction(
                owner,
                "personal",
                "expense",
                expense_category,
                "1250",
                "Personal limit expense",
            ).status_code,
            302,
        )
        self.assertEqual(
            self.create_transaction(
                owner,
                "personal",
                "savings_deposit",
                savings_category,
                "2000",
                "Personal savings deposit",
            ).status_code,
            302,
        )
        self.assertEqual(
            self.create_transaction(
                owner,
                "personal",
                "expense",
                savings_category,
                "500",
                "Personal savings spend",
                expense_source="savings",
            ).status_code,
            302,
        )

        personal_page = owner.get("/budget/personal")
        self.assertIn("3 750,00".encode("utf-8"), personal_page.data)
        self.assertIn("1 500,00".encode("utf-8"), personal_page.data)

        overdraw = self.create_transaction(
            owner,
            "personal",
            "expense",
            savings_category,
            "1600",
            "Rejected savings overdraw",
            expense_source="savings",
        )
        self.assertEqual(overdraw.status_code, 200)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) AS count FROM transactions WHERE description = %s",
                ("Rejected savings overdraw",),
            ).fetchone()["count"],
            0,
        )

        token = self.csrf_from(owner, "/")
        owner.post(
            "/budget/personal/limit",
            data={
                "_csrf_token": token,
                "spending_limit": "1000",
                "return_to": "home",
            },
        )
        negative_balance_page = owner.get("/budget/personal")
        self.assertIn("−250,00".encode("utf-8"), negative_balance_page.data)
        self.assertIn(b"amount--negative", negative_balance_page.data)

        # Create a family and two additional members.
        token = self.csrf_from(owner, "/family/create")
        response = owner.post(
            "/family/create",
            data={"_csrf_token": token, "family_name": "Integration Family"},
        )
        self.assertEqual(response.status_code, 302)
        family = self.connection.execute(
            "SELECT id, invite_code FROM families WHERE created_by = %s",
            (owner_id,),
        ).fetchone()

        member_id = self.register("member")
        removed_id = self.register("removed")
        self.join_family(self.clients["member"], family["invite_code"])
        self.join_family(self.clients["removed"], family["invite_code"])

        family_expense = self.create_category(
            owner, "Family Expense", "expense", "family"
        )
        family_savings = self.create_category(
            owner, "Family Savings", "savings", "family"
        )

        token = self.csrf_from(owner, "/")
        self.assertEqual(
            owner.post(
                "/budget/family/limit",
                data={
                    "_csrf_token": token,
                    "spending_limit": "10000",
                    "return_to": "home",
                },
            ).status_code,
            302,
        )

        member = self.clients["member"]
        token = self.csrf_from(member, "/family")
        self.assertEqual(
            member.post(
                "/budget/family/limit",
                data={
                    "_csrf_token": token,
                    "spending_limit": "1",
                    "return_to": "home",
                },
            ).status_code,
            403,
        )

        self.assertEqual(
            self.create_transaction(
                owner,
                "family",
                "savings_deposit",
                family_savings,
                "3000",
                "Owner family savings",
            ).status_code,
            302,
        )
        self.assertEqual(
            self.create_transaction(
                owner,
                "family",
                "expense",
                family_savings,
                "1000",
                "Family savings spend",
                expense_source="savings",
            ).status_code,
            302,
        )

        member_private_category = self.create_category(
            member, "Member Private Expense", "expense", "personal"
        )
        self.assertEqual(
            self.create_transaction(
                member,
                "personal",
                "expense",
                member_private_category,
                "100",
                "Member private transaction",
            ).status_code,
            302,
        )
        self.assertEqual(
            self.create_transaction(
                member,
                "family",
                "expense",
                family_expense,
                "700",
                "Member family expense",
            ).status_code,
            302,
        )
        member_transaction = self.connection.execute(
            "SELECT id FROM transactions WHERE description = 'Member family expense'"
        ).fetchone()["id"]

        # Family operation is visible to owner, but only the member-author can edit it.
        owner_family_list = owner.get("/transactions?scope=family")
        self.assertIn(b"Member family expense", owner_family_list.data)
        self.assertIn("# Семейная".encode("utf-8"), owner_family_list.data)
        self.assertEqual(owner.get(f"/transactions/{member_transaction}/edit").status_code, 403)
        self.assertEqual(member.get(f"/transactions/{member_transaction}/edit").status_code, 200)
        self.assertNotIn(
            b"Member private transaction",
            owner.get("/transactions?scope=all").data,
        )
        self.assertIn(
            b"Member private transaction",
            member.get("/transactions?scope=personal").data,
        )

        family_budget_page = owner.get("/budget/family")
        self.assertIn("9 300,00".encode("utf-8"), family_budget_page.data)
        self.assertIn("2 000,00".encode("utf-8"), family_budget_page.data)

        analytics = owner.get("/analytics?scope=all&period=year&group_by=month")
        self.assertEqual(analytics.status_code, 200)
        self.assertIn("Личная статистика".encode("utf-8"), analytics.data)
        self.assertIn("Семейная статистика".encode("utf-8"), analytics.data)

        # Owner removes one member; old invite code is rotated and access disappears.
        removed = self.clients["removed"]
        old_code = family["invite_code"]
        token = self.csrf_from(owner, "/family")
        response = owner.post(
            f"/family/members/{removed_id}/remove",
            data={"_csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        new_code = self.connection.execute(
            "SELECT invite_code FROM families WHERE id = %s",
            (family["id"],),
        ).fetchone()["invite_code"]
        self.assertNotEqual(old_code, new_code)
        self.assertEqual(removed.get("/budget/family").status_code, 302)

        # The remaining member leaves voluntarily; personal data remains accessible.
        token = self.csrf_from(member, "/family")
        self.assertEqual(
            member.post("/family/leave", data={"_csrf_token": token}).status_code,
            302,
        )
        self.assertEqual(member.get("/budget/personal").status_code, 200)
        self.assertEqual(member.get("/budget/family").status_code, 302)

        # The historical family operation remains visible to the family owner.
        self.assertIn(
            b"Member family expense",
            owner.get("/transactions?scope=family").data,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) AS count FROM family_members WHERE user_id = %s",
                (member_id,),
            ).fetchone()["count"],
            0,
        )

        # The last owner can explicitly dissolve the family; personal data survives.
        token = self.csrf_from(owner, "/family")
        self.assertEqual(
            owner.post(
                "/family/dissolve",
                data={
                    "_csrf_token": token,
                    "family_name": "Integration Family",
                },
            ).status_code,
            302,
        )
        self.assertEqual(owner.get("/budget/personal").status_code, 200)
        self.assertEqual(owner.get("/budget/family").status_code, 302)
