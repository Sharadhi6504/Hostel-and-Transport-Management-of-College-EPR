from .manager import ERPManager
import getpass

class CLI:
    def __init__(self):
        self.manager = ERPManager()

    def run(self):
        print("College ERP — Hostel & Transport Management")
        while True:
            print("\nLogin as:\n1) Admin\n2) Student\n3) Exit")
            choice = input("Choose: ").strip()
            if choice == '1':
                self.admin_login()
            elif choice == '2':
                self.student_login()
            elif choice == '3':
                print("Bye")
                self.manager.close()
                break
            else:
                print("Invalid choice")

    def admin_login(self):
        username = input("admin username: ")
        password = getpass.getpass("password: ")
        user = self.manager.authenticate_user(username, password, role='admin')
        if not user:
            print("Invalid admin credentials")
            return
        print(f"Welcome admin {username}")
        self.admin_menu()

    def admin_menu(self):
        while True:
            print("\nAdmin Menu:\n1) Students CRUD\n2) Hostel: rooms/allocations/payments/reports\n3) Transport: drivers/buses/routes/allocations/payments/reports\n4) Back")
            ch = input("Choose: ")
            if ch == '1':
                self.students_crud()
            elif ch == '2':
                self.hostel_menu()
            elif ch == '3':
                self.transport_menu()
            elif ch == '4':
                break
            else:
                print("Invalid")

    def students_crud(self):
        while True:
            print("\nStudents:\n1) Add student\n2) List students\n3) View student\n4) Delete student\n5) Back")
            ch = input("Choose: ")
            if ch == '1':
                name = input("Name: ")
                roll = input("Roll no: ")
                dept = input("Department: ")
                contact = input("Contact: ")
                addr = input("Address: ")
                username = input("Create login username (optional): ")
                password = None
                if username:
                    password = getpass.getpass("Set password: ")
                sid = self.manager.add_student(name, roll, dept, contact, addr, username, password)
                print("Added student id:", sid)
            elif ch == '2':
                students = self.manager.list_students()
                for s in students:
                    print(s)
            elif ch == '3':
                sid = input("Student id: ")
                s = self.manager.get_student(int(sid))
                print(s)
            elif ch == '4':
                sid = input("Student id to delete: ")
                self.manager.delete_student(int(sid))
                print("Deleted")
            elif ch == '5':
                break
            else:
                print("Invalid")

    def hostel_menu(self):
        while True:
            print("\nHostel Menu:\n1) Add room\n2) List rooms\n3) Allocate room\n4) Checkout student\n5) Record payment\n6) Occupancy report\n7) Vacant rooms\n8) Back")
            ch = input("Choose: ")
            if ch == '1':
                block = input("Block: ")
                room_no = input("Room no: ")
                cap = int(input("Capacity: "))
                rid = self.manager.add_room(block, room_no, cap)
                print("Room id:", rid)
            elif ch == '2':
                for r in self.manager.list_rooms():
                    print(r)
            elif ch == '3':
                sid = int(input("Student id: "))
                rid = int(input("Room id: "))
                aid = self.manager.allocate_room(sid, rid)
                print("Allocation id:", aid)
            elif ch == '4':
                aid = int(input("Allocation id: "))
                self.manager.checkout_student(aid)
                print("Checked out")
            elif ch == '5':
                sid = int(input("Student id: "))
                amt = float(input("Amount: "))
                pid = self.manager.record_hostel_payment(sid, amt)
                print("Payment recorded id:", pid)
            elif ch == '6':
                for r in self.manager.hostel_occupancy_report():
                    print(r)
            elif ch == '7':
                for r in self.manager.vacant_rooms_report():
                    print(r)
            elif ch == '8':
                break
            else:
                print("Invalid")

    def transport_menu(self):
        while True:
            print("\nTransport Menu:\n1) Register driver\n2) Register bus\n3) Register route\n4) Assign student to route\n5) Record transport payment\n6) Mark bus attendance\n7) Active routes report\n8) Fee report\n9) Back")
            ch = input("Choose: ")
            if ch == '1':
                name = input("Driver name: ")
                lic = input("License no: ")
                did = self.manager.register_driver(name, lic)
                print("Driver id:", did)
            elif ch == '2':
                reg = input("Bus reg: ")
                cap = int(input("Capacity: "))
                driver_id = input("Driver id (optional): ")
                driver_id = int(driver_id) if driver_id else None
                bid = self.manager.register_bus(reg, cap, driver_id)
                print("Bus id:", bid)
            elif ch == '3':
                name = input("Route name: ")
                pickup = input("Pickup location: ")
                fee = float(input("Fee: "))
                bus_id = input("Bus id (optional): ")
                bus_id = int(bus_id) if bus_id else None
                rid = self.manager.register_route(name, pickup, bus_id, fee)
                print("Route id:", rid)
            elif ch == '4':
                sid = int(input("Student id: "))
                rid = int(input("Route id: "))
                aid = self.manager.assign_student_to_route(sid, rid)
                print("Assigned id:", aid)
            elif ch == '5':
                sid = int(input("Student id: "))
                amt = float(input("Amount: "))
                pid = self.manager.record_transport_payment(sid, amt)
                print("Payment id:", pid)
            elif ch == '6':
                sid = int(input("Student id: "))
                rid = int(input("Route id: "))
                self.manager.mark_bus_attendance(sid, rid)
                print("Attendance marked")
            elif ch == '7':
                for r in self.manager.active_routes_report():
                    print(r)
            elif ch == '8':
                for r in self.manager.transport_fee_report():
                    print(r)
            elif ch == '9':
                break
            else:
                print("Invalid")

    def student_login(self):
        username = input("username: ")
        password = getpass.getpass("password: ")
        user = self.manager.authenticate_user(username, password, role='student')
        if not user:
            print("Invalid student credentials")
            return
        student_id = user["student_id"]
        print(f"Welcome student {username}")
        self.student_menu(student_id)

    def student_menu(self, student_id: int):
        while True:
            print("\nStudent Menu:\n1) View profile\n2) View hostel payments\n3) View transport payments\n4) Logout")
            ch = input("Choose: ")
            if ch == '1':
                profile = self.manager.get_student_profile(student_id)
                for k, v in profile.items():
                    print(k, ":", v)
            elif ch == '2':
                for p in self.manager.hostel_payments_for_student(student_id):
                    print(p)
            elif ch == '3':
                for p in self.manager.db.query("SELECT * FROM transport_payments WHERE student_id=?", (student_id,)):
                    print(dict(p))
            elif ch == '4':
                break
            else:
                print("Invalid")
