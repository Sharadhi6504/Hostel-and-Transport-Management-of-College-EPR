import unittest
import tempfile
import os
from erp.manager import ERPManager

class TestERPManager(unittest.TestCase):
    def setUp(self):
        # Use a temporary sqlite file per test run to avoid touching the repo DB
        self.tmpf = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.tmpf.name
        self.tmpf.close()
        self.mgr = ERPManager(db_path=self.db_path)

    def tearDown(self):
        try:
            self.mgr.close()
        except Exception:
            pass
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_student_hostel_transport_flow(self):
        # Add student with login
        sid = self.mgr.add_student("Alice", "R001", "CS", "12345", "Addr", username="alice", password="pass")
        self.assertIsInstance(sid, int)
        s = self.mgr.get_student(sid)
        self.assertIsNotNone(s)
        self.assertEqual(s["name"], "Alice")

        # authentication should work
        user = self.mgr.authenticate_user("alice", "pass", role='student')
        self.assertIsNotNone(user)
        self.assertEqual(user["student_id"], sid)

        # Add a room and allocate
        room_id = self.mgr.add_room("A", "101", capacity=2)
        self.assertIsInstance(room_id, int)
        alloc_id = self.mgr.allocate_room(sid, room_id)
        self.assertIsInstance(alloc_id, int)

        # allocate second student into same room (capacity 2)
        sid2 = self.mgr.add_student("Bob", "R002", "CS", "67890", "Addr2", username="bob", password="pw")
        self.mgr.allocate_room(sid2, room_id)

        # third student should fail due to capacity
        sid3 = self.mgr.add_student("Charlie", "R003", "CS", "00000", "Addr3", username="charlie", password="pw2")
        with self.assertRaises(ValueError):
            self.mgr.allocate_room(sid3, room_id)

        # Occupancy report should include the room
        occ = self.mgr.hostel_occupancy_report()
        room_ids = [r["room_id"] for r in occ]
        self.assertIn(room_id, room_ids)

        # Record hostel payment
        pay_id = self.mgr.record_hostel_payment(sid, 500.0)
        self.assertIsInstance(pay_id, int)
        payments = self.mgr.hostel_payments_for_student(sid)
        self.assertEqual(len(payments), 1)
        self.assertAlmostEqual(payments[0]["amount"], 500.0)

        # Transport: driver, bus, route, assign, payment
        driver_id = self.mgr.register_driver("Bob", "LIC123")
        bus_id = self.mgr.register_bus("KA-01-XYZ", 40, driver_id)
        route_id = self.mgr.register_route("Route-1", "Central", bus_id, fee=100.0)
        ta_id = self.mgr.assign_student_to_route(sid, route_id)
        self.assertIsInstance(ta_id, int)

        tr_pay_id = self.mgr.record_transport_payment(sid, 50.0)
        self.assertIsInstance(tr_pay_id, int)

        # Profile aggregates
        profile = self.mgr.get_student_profile(sid)
        self.assertIn("student", profile)
        self.assertAlmostEqual(profile["total_hostel_paid"], 500.0)
        self.assertAlmostEqual(profile["total_transport_paid"], 50.0)
        self.assertAlmostEqual(profile["total_route_fee"], 100.0)
        self.assertAlmostEqual(profile["total_dues"], 50.0)

if __name__ == '__main__':
    unittest.main()
