from .db import Database
from .models import Student, HostelRoom, Bus, Route
from typing import Optional, List, Dict
import datetime

class ERPManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db = Database(db_path) if db_path else Database()

    # -- Student CRUD --
    def add_student(self, name: str, roll_no: Optional[str] = None, department: Optional[str] = None,
                    contact: Optional[str] = None, address: Optional[str] = None, username: Optional[str] = None,
                    password: Optional[str] = None) -> int:
        cur = self.db.execute(
            "INSERT INTO students (name, roll_no, department, contact, address) VALUES (?,?,?,?,?)",
            (name, roll_no, department, contact, address)
        )
        student_id = cur.lastrowid
        if username and password:
            # store hashed password using helper
            self.db.create_user(username, password, 'student', student_id)
        return student_id

    def get_student(self, student_id: int) -> Optional[Dict]:
        rows = self.db.query("SELECT * FROM students WHERE id=?", (student_id,))
        if not rows:
            return None
        r = rows[0]
        return dict(r)

    def update_student(self, student_id: int, **fields) -> bool:
        if not fields:
            return False
        keys = ",".join(f"{k}=?" for k in fields.keys())
        params = tuple(fields.values()) + (student_id,)
        self.db.execute(f"UPDATE students SET {keys} WHERE id=?", params)
        return True

    def delete_student(self, student_id: int) -> bool:
        self.db.execute("DELETE FROM users WHERE student_id=?", (student_id,))
        self.db.execute("DELETE FROM students WHERE id=?", (student_id,))
        return True

    def list_students(self) -> List[Dict]:
        rows = self.db.query("SELECT * FROM students")
        return [dict(r) for r in rows]

    # -- Hostel management --
    def add_room(self, block: str, room_no: str, capacity: int = 1) -> int:
        cur = self.db.execute("INSERT INTO hostel_rooms (block,room_no,capacity) VALUES (?,?,?)",
                              (block, room_no, capacity))
        return cur.lastrowid

    def list_rooms(self) -> List[Dict]:
        rows = self.db.query("SELECT * FROM hostel_rooms")
        return [dict(r) for r in rows]

    def allocate_room(self, student_id: int, room_id: int, checkin_date: Optional[str] = None) -> int:
        # enforce capacity: check current occupants
        rows = self.db.query("SELECT capacity FROM hostel_rooms WHERE id=?", (room_id,))
        if not rows:
            raise ValueError("Room not found")
        capacity = rows[0]["capacity"]
        occ = self.db.query("SELECT COUNT(1) as c FROM hostel_allocations WHERE room_id=? AND checkout_date IS NULL", (room_id,))
        occupants = occ[0]["c"] if occ else 0
        if occupants >= capacity:
            raise ValueError("Room is full")
        if checkin_date is None:
            checkin_date = datetime.date.today().isoformat()
        cur = self.db.execute("INSERT INTO hostel_allocations (student_id,room_id,checkin_date) VALUES (?,?,?)",
                              (student_id, room_id, checkin_date))
        return cur.lastrowid

    def authenticate_user(self, username: str, password: str, role: Optional[str] = None) -> Optional[Dict]:
        row = self.db.verify_user(username, password, role)
        if not row:
            return None
        return dict(row)

    def checkout_student(self, allocation_id: int, checkout_date: Optional[str] = None) -> bool:
        if checkout_date is None:
            checkout_date = datetime.date.today().isoformat()
        self.db.execute("UPDATE hostel_allocations SET checkout_date=? WHERE id=?", (checkout_date, allocation_id))
        return True

    def record_hostel_payment(self, student_id: int, amount: float, date: Optional[str] = None) -> int:
        if date is None:
            date = datetime.date.today().isoformat()
        receipt_no = f"H-{int(datetime.datetime.now().timestamp())}-{student_id}"
        cur = self.db.execute("INSERT INTO hostel_payments (student_id,amount,date,receipt_no) VALUES (?,?,?,?)",
                              (student_id, amount, date, receipt_no))
        return cur.lastrowid

    def hostel_payments_for_student(self, student_id: int):
        rows = self.db.query("SELECT * FROM hostel_payments WHERE student_id=?", (student_id,))
        return [dict(r) for r in rows]

    def hostel_occupancy_report(self):
        rows = self.db.query("SELECT r.id as room_id, r.block, r.room_no, r.capacity, COUNT(a.id) as occupants "
                             "FROM hostel_rooms r LEFT JOIN hostel_allocations a ON r.id=a.room_id AND a.checkout_date IS NULL "
                             "GROUP BY r.id")
        return [dict(r) for r in rows]

    def vacant_rooms_report(self):
        rows = self.db.query("SELECT r.*, (r.capacity - IFNULL(t.occupants,0)) as vacant FROM hostel_rooms r "
                             "LEFT JOIN (SELECT room_id, COUNT(id) as occupants FROM hostel_allocations WHERE checkout_date IS NULL GROUP BY room_id) t "
                             "ON r.id=t.room_id WHERE (r.capacity - IFNULL(t.occupants,0)) > 0")
        return [dict(r) for r in rows]

    # -- Transport management --
    def register_driver(self, name: str, license_no: Optional[str] = None) -> int:
        # validate unique license_no if provided
        if license_no:
            exists = self.db.query("SELECT id FROM drivers WHERE license_no=?", (license_no,))
            if exists:
                raise ValueError("License number already exists")
        cur = self.db.execute("INSERT INTO drivers (name,license_no) VALUES (?,?)", (name, license_no))
        return cur.lastrowid

    def list_drivers(self) -> List[Dict]:
        rows = self.db.query("SELECT * FROM drivers")
        return [dict(r) for r in rows]

    def update_driver(self, driver_id: int, **fields) -> bool:
        if not fields:
            return False
        # if license_no is being updated, ensure uniqueness (excluding current)
        if 'license_no' in fields and fields['license_no']:
            exists = self.db.query("SELECT id FROM drivers WHERE license_no=? AND id<>?", (fields['license_no'], driver_id))
            if exists:
                raise ValueError("License number already exists")
        keys = ",".join(f"{k}=?" for k in fields.keys())
        params = tuple(fields.values()) + (driver_id,)
        self.db.execute(f"UPDATE drivers SET {keys} WHERE id=?", params)
        return True

    def delete_driver(self, driver_id: int) -> bool:
        # unset driver from buses, then delete
        self.db.execute("UPDATE buses SET driver_id=NULL WHERE driver_id=?", (driver_id,))
        self.db.execute("DELETE FROM drivers WHERE id=?", (driver_id,))
        return True

    def register_bus(self, registration: str, capacity: int = 20, driver_id: Optional[int] = None) -> int:
        # validate unique registration
        exists = self.db.query("SELECT id FROM buses WHERE registration=?", (registration,))
        if exists:
            raise ValueError("Bus registration already exists")
        cur = self.db.execute("INSERT INTO buses (registration,capacity,driver_id) VALUES (?,?,?)",
                              (registration, capacity, driver_id))
        return cur.lastrowid

    def list_buses(self) -> List[Dict]:
        rows = self.db.query("SELECT b.*, d.name as driver_name, d.license_no FROM buses b LEFT JOIN drivers d ON b.driver_id=d.id")
        return [dict(r) for r in rows]

    def update_bus(self, bus_id: int, **fields) -> bool:
        if not fields:
            return False
        # if registration is being updated, ensure uniqueness (excluding current)
        if 'registration' in fields and fields['registration']:
            exists = self.db.query("SELECT id FROM buses WHERE registration=? AND id<>?", (fields['registration'], bus_id))
            if exists:
                raise ValueError("Bus registration already exists")
        keys = ",".join(f"{k}=?" for k in fields.keys())
        params = tuple(fields.values()) + (bus_id,)
        self.db.execute(f"UPDATE buses SET {keys} WHERE id=?", params)
        return True

    def delete_bus(self, bus_id: int) -> bool:
        # unset bus from routes, then delete
        self.db.execute("UPDATE routes SET bus_id=NULL WHERE bus_id=?", (bus_id,))
        self.db.execute("DELETE FROM buses WHERE id=?", (bus_id,))
        return True

    def register_route(self, name: str, pickup_location: str, bus_id: Optional[int] = None, fee: float = 0.0) -> int:
        cur = self.db.execute("INSERT INTO routes (name,pickup_location,bus_id,fee) VALUES (?,?,?,?)",
                              (name, pickup_location, bus_id, fee))
        return cur.lastrowid

    def assign_student_to_route(self, student_id: int, route_id: int) -> int:
        # Prevent duplicate active transport allocation for same student and route
        exists = self.db.query(
            "SELECT id FROM transport_allocations WHERE student_id=? AND route_id=? AND active=1",
            (student_id, route_id)
        )
        if exists:
            raise ValueError("Student is already assigned to this route")

        cur = self.db.execute("INSERT INTO transport_allocations (student_id,route_id,active) VALUES (?,?,?)",
                              (student_id, route_id, 1))
        return cur.lastrowid

    def record_transport_payment(self, student_id: int, amount: float, date: Optional[str] = None) -> int:
        if date is None:
            date = datetime.date.today().isoformat()
        receipt_no = f"T-{int(datetime.datetime.now().timestamp())}-{student_id}"
        cur = self.db.execute("INSERT INTO transport_payments (student_id,amount,date,receipt_no) VALUES (?,?,?,?)",
                              (student_id, amount, date, receipt_no))
        return cur.lastrowid

    def mark_bus_attendance(self, student_id: int, route_id: int, date: Optional[str] = None, present: int = 1) -> int:
        if date is None:
            date = datetime.date.today().isoformat()
        cur = self.db.execute("INSERT INTO bus_attendance (student_id,route_id,date,present) VALUES (?,?,?,?)",
                              (student_id, route_id, date, present))
        return cur.lastrowid

    def active_routes_report(self):
        rows = self.db.query("SELECT r.*, b.registration as bus_reg, COUNT(ta.id) as riders "
                             "FROM routes r LEFT JOIN buses b ON r.bus_id=b.id "
                             "LEFT JOIN transport_allocations ta ON r.id=ta.route_id AND ta.active=1 "
                             "GROUP BY r.id")
        return [dict(r) for r in rows]

    def transport_fee_report(self):
        rows = self.db.query("SELECT t.id as allocation_id, s.name as student_name, r.name as route_name, r.fee, tp.amount as paid "
                             "FROM transport_allocations t "
                             "LEFT JOIN students s ON t.student_id=s.id "
                             "LEFT JOIN routes r ON t.route_id=r.id "
                             "LEFT JOIN transport_payments tp ON tp.student_id=s.id")
        return [dict(r) for r in rows]

    # -- Integration --
    def get_student_profile(self, student_id: int) -> Dict:
        s = self.get_student(student_id)
        if not s:
            return {}
        # hostel allocation
        allocs = self.db.query("SELECT a.*, r.block, r.room_no FROM hostel_allocations a JOIN hostel_rooms r ON a.room_id=r.id WHERE a.student_id=? ORDER BY a.id DESC", (student_id,))
        transports = self.db.query("SELECT t.*, r.name as route_name, r.pickup_location, r.fee FROM transport_allocations t JOIN routes r ON t.route_id=r.id WHERE t.student_id=?", (student_id,))
        hostel_payments = self.db.query("SELECT * FROM hostel_payments WHERE student_id=?", (student_id,))
        transport_payments = self.db.query("SELECT * FROM transport_payments WHERE student_id=?", (student_id,))

        total_hostel_paid = sum(p["amount"] for p in hostel_payments)
        total_transport_paid = sum(p["amount"] for p in transport_payments)

        # dues: simple: latest route fee if any minus paid
        route_fee = 0.0
        for t in transports:
            route_fee += t["fee"]

        profile = {
            "student": s,
            "hostel_allocations": [dict(r) for r in allocs],
            "transport_allocations": [dict(r) for r in transports],
            "hostel_payments": [dict(r) for r in hostel_payments],
            "transport_payments": [dict(r) for r in transport_payments],
            "total_hostel_paid": total_hostel_paid,
            "total_transport_paid": total_transport_paid,
            "total_route_fee": route_fee,
            "total_dues": max(0.0, route_fee - total_transport_paid)
        }
        return profile

    def close(self):
        self.db.close()

    # -- Announcements (admin -> all students) --
    def create_announcement(self, title: str, message: str, active: int = 1, date: Optional[str] = None) -> int:
        if date is None:
            # store full ISO datetime so detail views can show time-of-publication
            date = datetime.datetime.now().isoformat()
        cur = self.db.execute("INSERT INTO announcements (title,message,created,start_date,end_date,active) VALUES (?,?,?,?,?,?)", (title, message, date, None, None, active))
        return cur.lastrowid

    def list_announcements(self, only_active: Optional[bool] = True, student_id: Optional[int] = None, sort: str = 'desc', include_dismissed: bool = False) -> List[Dict]:
        """List announcements.

        only_active: True = only active announcements, False = only inactive, None = all
        student_id: if provided, exclude announcements dismissed by that student
        sort: 'desc' (newest first) or 'asc' (oldest first)
        Scheduling (start_date/end_date) is applied when filtering for active announcements; when only_active is False/None scheduling is still applied unless explicitly bypassed by caller.
        """
        params: List = []
        where_clauses: List[str] = []
        today = datetime.date.today().isoformat()

        # active filter
        if only_active is True:
            where_clauses.append("active=1")
        elif only_active is False:
            where_clauses.append("active=0")

        # scheduling constraints: include only announcements valid today
        where_clauses.append("(start_date IS NULL OR date(start_date) <= date(?))")
        where_clauses.append("(end_date IS NULL OR date(end_date) >= date(?))")
        params.extend([today, today])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        order = 'DESC' if (sort or '').lower() != 'asc' else 'ASC'

        if student_id is not None:
            if include_dismissed:
                # include dismissed announcements but mark which are dismissed
                sql = f"SELECT a.*, d.id as dismissed_id FROM announcements a LEFT JOIN dismissed_announcements d ON a.id=d.announcement_id AND d.student_id=? WHERE {where_sql} ORDER BY a.created {order}"
                params = [student_id] + params
                raw_rows = self.db.query(sql, tuple(params))
                rows = []
                for r in raw_rows:
                    d = dict(r)
                    d['dismissed'] = bool(d.get('dismissed_id'))
                    # remove helper column
                    d.pop('dismissed_id', None)
                    rows.append(d)
            else:
                # exclude dismissed announcements for this student
                sql = f"SELECT a.* FROM announcements a LEFT JOIN dismissed_announcements d ON a.id=d.announcement_id AND d.student_id=? WHERE {where_sql} AND d.id IS NULL ORDER BY a.created {order}"
                params = [student_id] + params
                rows = self.db.query(sql, tuple(params))
        else:
            sql = f"SELECT * FROM announcements WHERE {where_sql} ORDER BY created {order}"
            rows = self.db.query(sql, tuple(params))
        # ensure all rows are plain dicts
        return [dict(r) if not isinstance(r, dict) else r for r in rows]

    def get_announcement(self, aid: int) -> Optional[Dict]:
        rows = self.db.query("SELECT * FROM announcements WHERE id=?", (aid,))
        if not rows:
            return None
        return dict(rows[0])

    def update_announcement(self, aid: int, **fields) -> bool:
        if not fields:
            return False
        keys = ",".join(f"{k}=?" for k in fields.keys())
        params = tuple(fields.values()) + (aid,)
        self.db.execute(f"UPDATE announcements SET {keys} WHERE id=?", params)
        return True

    def deactivate_announcement(self, aid: int) -> bool:
        self.db.execute("UPDATE announcements SET active=0 WHERE id=?", (aid,))
        return True

    def delete_announcement(self, aid: int) -> bool:
        # remove dismissals too
        self.db.execute("DELETE FROM dismissed_announcements WHERE announcement_id=?", (aid,))
        self.db.execute("DELETE FROM announcements WHERE id=?", (aid,))
        return True

    def record_dismissal(self, student_id: int, announcement_id: int, date: Optional[str] = None) -> int:
        if date is None:
            date = datetime.datetime.now().isoformat()
        cur = self.db.execute("INSERT INTO dismissed_announcements (announcement_id,student_id,dismissed_at) VALUES (?,?,?)", (announcement_id, student_id, date))
        return cur.lastrowid

    def record_contact_message(self, student_id: int, to_role: str, to_id: Optional[int], subject: str, message: str,
                               date: Optional[str] = None, sender_role: Optional[str] = None,
                               sender_id: Optional[int] = None, parent_id: Optional[int] = None) -> int:
        """Store a contact/help message.

        student_id: the student who is primarily involved (for inbox grouping)
        to_role/to_id: recipient role and optional id (e.g., 'admin' or 'driver')
        sender_role/sender_id: who sent this message (may be 'student' or 'admin')
        parent_id: optional parent message id for threading
        """
        if date is None:
            date = datetime.date.today().isoformat()
        cur = self.db.execute(
            "INSERT INTO contact_messages (student_id,to_role,to_id,subject,message,created,sender_role,sender_id,parent_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (student_id, to_role, to_id, subject, message, date, sender_role, sender_id, parent_id),
        )
        return cur.lastrowid

    def list_contact_messages(self, limit: int = 200):
        rows = self.db.query("SELECT m.*, s.name as student_name FROM contact_messages m JOIN students s ON m.student_id=s.id ORDER BY m.created DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def get_contact_message(self, msg_id: int) -> Optional[Dict]:
        rows = self.db.query("SELECT m.*, s.name as student_name FROM contact_messages m JOIN students s ON m.student_id=s.id WHERE m.id=?", (msg_id,))
        if not rows:
            return None
        return dict(rows[0])
