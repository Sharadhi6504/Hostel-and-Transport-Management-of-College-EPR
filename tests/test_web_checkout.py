import unittest

from web import app as flask_app

from erp.manager import ERPManager


class CheckoutFlowTest(unittest.TestCase):
    def setUp(self):
        # use in-memory DB for isolation
        self.app = flask_app
        self.app.config["TESTING"] = True

        # create a fresh manager bound to an in-memory SQLite DB
        self.test_manager = ERPManager(db_path=':memory:')

        # replace the manager used by the web app module
        import web.app as webapp_module

        webapp_module.manager = self.test_manager

        self.client = self.app.test_client()

    def tearDown(self):
        try:
            self.test_manager.close()
        except Exception:
            pass

    def test_admin_checkout_flow(self):
        # create a student with credentials (not required for the flow but realistic)
        sid = self.test_manager.add_student(
            name="Test Student",
            roll_no="RN100",
            department="CS",
            contact="999",
            address="Nowhere",
            username="tuser",
            password="tpass",
        )

        # add a room and allocate
        room_id = self.test_manager.add_room("A", "101", capacity=1)
        alloc_id = self.test_manager.allocate_room(sid, room_id)

        # verify allocation present and not checked out
        rows = self.test_manager.db.query("SELECT * FROM hostel_allocations WHERE id=?", (alloc_id,))
        self.assertTrue(rows)
        self.assertIsNone(rows[0]["checkout_date"])

        # perform checkout via the Flask test client as admin (set session)
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user"] = {"username": "admin", "role": "admin"}

            resp = c.post(f"/allocations/{alloc_id}/checkout", follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"Student checked out", resp.data)

        # verify checkout_date is now set in DB
        rows = self.test_manager.db.query("SELECT * FROM hostel_allocations WHERE id=?", (alloc_id,))
        self.assertTrue(rows)
        self.assertIsNotNone(rows[0]["checkout_date"])


if __name__ == "__main__":
    unittest.main()
