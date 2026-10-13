import os
import tempfile
import unittest

db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
db_file.close()
os.environ["DATABASE_URL"] = "sqlite:///" + db_file.name
os.environ["APP_ENV"] = "development"
os.environ["JWT_SECRET"] = "test-admin-secret-with-at-least-thirty-two-chars"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "root@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "test-admin-password-long-123"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Test Root"

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


class AdminApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        login = client.post("/api/auth/login", json={"email": "root@example.com", "password": "test-admin-password-long-123"})
        if login.status_code != 200:
            raise RuntimeError(f"Test administrator login failed: {login.text}")
        cls.headers = {"Authorization": "Bearer " + login.json()["access_token"]}

    def test_auth_required(self):
        response = client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401)

    def test_dashboard_and_seed_are_available_to_super_admin(self):
        response = client.get("/api/dashboard", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("shops", response.json())
        seeded = client.post("/api/dev/seed", headers=self.headers)
        self.assertEqual(seeded.status_code, 200, seeded.text)
        self.assertIn("sample", seeded.json()["message"].lower())

    def test_shop_approval_and_suspension(self):
        created = client.post("/api/shops", headers=self.headers, json={
            "name": "Test Vegetables", "owner_name": "Test Owner", "phone": "+919876543210"
        })
        self.assertEqual(created.status_code, 201, created.text)
        shop = created.json()
        approved = client.patch(f"/api/shops/{shop['id']}", headers=self.headers, json={
            "status": "approved", "is_open": True, "accepts_orders": True
        })
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "approved")
        suspended = client.patch(f"/api/shops/{shop['id']}", headers=self.headers, json={"status": "suspended"})
        self.assertEqual(suspended.status_code, 200, suspended.text)
        self.assertFalse(suspended.json()["is_open"])
        self.assertFalse(suspended.json()["accepts_orders"])

    def test_order_creation_assignment_and_status_transition(self):
        shop = client.post("/api/shops", headers=self.headers, json={"name": "Order Shop", "status": "approved"}).json()
        agent = client.post("/api/agents", headers=self.headers, json={"full_name": "Courier Test", "status": "approved"}).json()
        order = client.post("/api/orders", headers=self.headers, json={
            "public_code": "VGZ-TEST-ORDER-1", "shop_id": shop["id"], "total_amount": 120, "status": "ready_for_pickup"
        })
        self.assertEqual(order.status_code, 201, order.text)
        assigned = client.post(f"/api/orders/{order.json()['id']}/assign", headers=self.headers, json={"agent_id": agent["id"]})
        self.assertEqual(assigned.status_code, 200, assigned.text)
        self.assertEqual(assigned.json()["status"], "assigned")
        delivered = client.patch(f"/api/orders/{assigned.json()['id']}/status", headers=self.headers, json={"status": "delivered"})
        self.assertEqual(delivered.status_code, 409)

    def test_settings_validation_and_audit(self):
        invalid = client.patch("/api/settings/maintenance_mode", headers=self.headers, json={"value": "perhaps"})
        self.assertEqual(invalid.status_code, 422)
        valid = client.patch("/api/settings/maintenance_mode", headers=self.headers, json={"value": "true"})
        self.assertEqual(valid.status_code, 200, valid.text)
        audit = client.get("/api/audit?limit=50", headers=self.headers)
        self.assertEqual(audit.status_code, 200, audit.text)
        self.assertGreater(len(audit.json()), 0)

    def test_duplicate_order_code_is_rejected(self):
        response = client.post("/api/orders", headers=self.headers, json={"public_code": "VGZ-DUPLICATE-1"})
        self.assertEqual(response.status_code, 201, response.text)
        duplicate = client.post("/api/orders", headers=self.headers, json={"public_code": "VGZ-DUPLICATE-1"})
        self.assertEqual(duplicate.status_code, 409)


if __name__ == "__main__":
    unittest.main()
