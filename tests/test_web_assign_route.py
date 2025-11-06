import unittest

from web import app as flask_app

from erp.manager import ERPManager


class AssignRouteFlowTest(unittest.TestCase):
    def setUp(self):
        self.app = flask_app
        self.app.config["TESTING"] = True

        # fresh in-memory manager
        self.test_manager = ERPManager(db_path=':memory:')
        import importlib
        webapp_module = importlib.import_module('web.app')
        webapp_module.manager = self.test_manager

        self.client = self.app.test_client()

    def tearDown(self):
        try:
            self.test_manager.close()
        except Exception:
            pass

    def test_assign_route_and_duplicate(self):
        # create student and route
        sid = self.test_manager.add_student(name="AR Student", username=None, password=None)
        rid = self.test_manager.register_route("R1", "Gate", None, 50.0)

        # perform assign via Flask client as admin
        with self.client as c:
            with c.session_transaction() as sess:
                sess["user"] = {"username": "admin", "role": "admin"}

            resp = c.post(f"/students/{sid}/assign_route", data={"route_id": str(rid)}, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(b"Assigned to route", resp.data)

            # Try duplicate assign -> should flash an error about already assigned
            resp2 = c.post(f"/students/{sid}/assign_route", data={"route_id": str(rid)}, follow_redirects=True)
            self.assertEqual(resp2.status_code, 200)
            self.assertTrue(b"already assigned" in resp2.data or b"Assigned to route" not in resp2.data)

        # verify DB has one active allocation
        rows = self.test_manager.db.query("SELECT * FROM transport_allocations WHERE student_id=? AND route_id=? AND active=1", (sid, rid))
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
