from flask import Flask, render_template, request, redirect, url_for, session, flash
from erp.manager import ERPManager

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"

# Create a single manager instance for this simple demo.
manager = ERPManager()


def login_required(roles=None):
    from functools import wraps

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            u = session.get("user")
            if not u:
                return redirect(url_for("login"))
            if roles and u.get("role") not in roles:
                flash("Unauthorized", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)

        return wrapped

    return decorator


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")
        user = manager.authenticate_user(username, password, role=role)
        if not user:
            flash("Invalid credentials", "danger")
            return render_template("login.html")
        session["user"] = {"username": username, "role": role, "student_id": user.get("student_id")}
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required()
def dashboard():
    user = session.get("user")
    if user.get("role") == "admin":
        # count unread payment notifications for admin (subjects contain 'payment')
        try:
            row = manager.db.query("SELECT COUNT(1) as c FROM contact_messages WHERE to_role='admin' AND is_read=0 AND subject LIKE '%payment%'")
            unread_payments = row[0]["c"] if row else 0
        except Exception:
            unread_payments = 0
        return render_template("admin_dashboard.html", user=user, unread_payments=unread_payments)
    # student view
    student_id = user.get("student_id")
    profile = manager.get_student_profile(student_id) if student_id else {}
    # also provide available routes for enrollment
    routes = manager.active_routes_report()
    # provide drivers for contact/help selection
    drivers = manager.list_drivers()
    # fetch admin announcements (global notifications for students)
    try:
        # pass student_id so announcements the student dismissed are excluded
        announcements = manager.list_announcements(only_active=True, student_id=student_id)
    except Exception:
        announcements = []
    return render_template("student_dashboard.html", profile=profile, routes=routes, drivers=drivers, announcements=announcements)


@app.route("/students")
@login_required(roles=["admin"])
def students():
    students = manager.list_students()
    return render_template("students.html", students=students)


@app.route("/students/<int:student_id>")
@login_required(roles=["admin"])
def student_detail(student_id):
    s = manager.get_student(student_id)
    if not s:
        flash("Student not found", "danger")
        return redirect(url_for('students'))
    rooms = manager.list_rooms()
    routes = manager.active_routes_report()
    # provide buses and drivers for transport assignment UI
    buses = manager.list_buses()
    drivers = manager.list_drivers()
    # current allocations
    allocs = manager.db.query("SELECT a.*, r.block, r.room_no FROM hostel_allocations a JOIN hostel_rooms r ON a.room_id=r.id WHERE a.student_id=? AND a.checkout_date IS NULL", (student_id,))
    transports = manager.db.query("SELECT t.*, r.name as route_name FROM transport_allocations t JOIN routes r ON t.route_id=r.id WHERE t.student_id=? AND t.active=1", (student_id,))
    return render_template(
        "student_detail.html",
        student=s,
        rooms=rooms,
        routes=routes,
        buses=buses,
        drivers=drivers,
        allocs=[dict(a) for a in allocs],
        transports=[dict(t) for t in transports],
    )


@app.route("/students/<int:student_id>/assign_room", methods=["POST"])
@login_required(roles=["admin"])
def assign_room(student_id):
    room_id = int(request.form.get("room_id"))
    try:
        aid = manager.allocate_room(student_id, room_id)
        flash(f"Allocated room (id {aid})", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('student_detail', student_id=student_id))


@app.route('/admin/announcements/add', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def add_announcement():
    if request.method == 'POST':
        title = request.form.get('title') or ''
        message = request.form.get('message') or ''
        active = 1 if request.form.get('active') else 0
        if not title.strip() or not message.strip():
            flash('Title and message are required', 'danger')
            return render_template('add_announcement.html')
        try:
            aid = manager.create_announcement(title.strip(), message.strip(), active=active)
            flash(f'Announcement created (id {aid})', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('add_announcement.html')
    return render_template('add_announcement.html')


@app.route('/admin/announcements', methods=['GET'])
@login_required(roles=['admin'])
def announcements_list():
    try:
        announcements = manager.list_announcements(only_active=False)
    except Exception:
        announcements = []
    return render_template('announcements_list.html', announcements=announcements)


@app.route('/admin/announcements/<int:aid>/edit', methods=['GET', 'POST'])
@login_required(roles=['admin'])
def edit_announcement(aid):
    ann = manager.get_announcement(aid)
    if not ann:
        flash('Announcement not found', 'danger')
        return redirect(url_for('announcements_list'))
    if request.method == 'POST':
        title = request.form.get('title') or ''
        message = request.form.get('message') or ''
        start_date = request.form.get('start_date') or None
        end_date = request.form.get('end_date') or None
        active = 1 if request.form.get('active') else 0
        if not title.strip() or not message.strip():
            flash('Title and message required', 'danger')
            return render_template('add_announcement.html', announcement=ann)
        try:
            manager.update_announcement(aid, title=title.strip(), message=message.strip(), start_date=start_date, end_date=end_date, active=active)
            flash('Announcement updated', 'success')
            return redirect(url_for('announcements_list'))
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('add_announcement.html', announcement=ann)
    return render_template('add_announcement.html', announcement=ann)


@app.route('/admin/announcements/<int:aid>/deactivate', methods=['POST'])
@login_required(roles=['admin'])
def deactivate_announcement(aid):
    try:
        manager.deactivate_announcement(aid)
        flash('Announcement deactivated', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    return redirect(url_for('announcements_list'))


@app.route('/admin/announcements/<int:aid>/delete', methods=['POST'])
@login_required(roles=['admin'])
def delete_announcement(aid):
    try:
        manager.delete_announcement(aid)
        flash('Announcement deleted', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    return redirect(url_for('announcements_list'))


@app.route('/student/announcements/dismiss', methods=['POST'])
@login_required(roles=['student'])
def dismiss_announcement():
    user = session.get('user')
    student_id = user.get('student_id')
    ann_id = request.form.get('announcement_id')
    if not ann_id:
        flash('Missing announcement id', 'danger')
        return redirect(url_for('dashboard'))
    try:
        manager.record_dismissal(student_id, int(ann_id))
        flash('Announcement dismissed', 'success')
    except Exception as e:
        flash(str(e), 'danger')
    return redirect(url_for('dashboard'))


@app.route('/student/notifications')
@login_required(roles=['student'])
def student_notifications():
    user = session.get('user')
    student_id = user.get('student_id')
    # support sorting/filtering via query params: ?sort=newest|oldest&show=active|all|inactive
    sort = (request.args.get('sort') or 'newest').lower()
    show = (request.args.get('show') or 'active').lower()
    sort_param = 'desc' if sort == 'newest' else 'asc'
    if show == 'active':
        only_active_param = True
    elif show == 'inactive':
        only_active_param = False
    else:
        only_active_param = None
    try:
        # Include dismissed announcements on the Notifications page so students
        # can still view announcements they've previously dismissed from the
        # dashboard.
        announcements = manager.list_announcements(only_active=only_active_param, student_id=student_id, sort=sort_param, include_dismissed=True)
    except Exception:
        announcements = []
    return render_template('student_notifications.html', announcements=announcements)


@app.route('/student/notifications/<int:aid>', methods=['GET'])
@login_required(roles=['student'])
def student_notification_detail(aid):
    ann = manager.get_announcement(aid)
    if not ann:
        flash('Notification not found', 'danger')
        return redirect(url_for('student_notifications'))
    # mark whether this student previously dismissed this announcement
    user = session.get('user')
    student_id = user.get('student_id')
    try:
        row = manager.db.query("SELECT id FROM dismissed_announcements WHERE announcement_id=? AND student_id=?", (aid, student_id))
        ann['dismissed'] = bool(row)
    except Exception:
        ann['dismissed'] = False
    return render_template('student_notification_detail.html', announcement=ann)


@app.route("/students/<int:student_id>/assign_route", methods=["POST"])
@login_required(roles=["admin"])
def assign_route(student_id):
    route_id_raw = request.form.get("route_id")
    if not route_id_raw:
        flash("Please select a route", "danger")
        return redirect(url_for('student_detail', student_id=student_id))
    try:
        route_id = int(route_id_raw)
    except (ValueError, TypeError):
        flash("Invalid route selection", "danger")
        return redirect(url_for('student_detail', student_id=student_id))

    try:
        aid = manager.assign_student_to_route(student_id, route_id)
        flash(f"Assigned to route (id {aid})", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('student_detail', student_id=student_id))


@app.route("/students/<int:student_id>/assign_transport", methods=["POST"])
@login_required(roles=["admin"])
def assign_transport(student_id):
    # Fields: route_id (required), bus_id (optional), driver_id (optional), driver_name, driver_contact, pickup_location
    route_id_raw = request.form.get("route_id")
    if not route_id_raw:
        flash("Please select a route", "danger")
        return redirect(url_for('student_detail', student_id=student_id))
    try:
        route_id = int(route_id_raw)
    except (ValueError, TypeError):
        flash("Invalid route selection", "danger")
        return redirect(url_for('student_detail', student_id=student_id))

    bus_id = None
    bus_id_raw = request.form.get("bus_id")
    if bus_id_raw:
        try:
            bus_id = int(bus_id_raw)
        except (ValueError, TypeError):
            flash("Invalid bus selection", "danger")
            return redirect(url_for('student_detail', student_id=student_id))

    driver_id = None
    driver_id_raw = request.form.get("driver_id")
    if driver_id_raw:
        try:
            driver_id = int(driver_id_raw)
        except (ValueError, TypeError):
            driver_id = None

    driver_name = request.form.get("driver_name")
    driver_contact = request.form.get("driver_contact")
    pickup_location = request.form.get("pickup_location")

    # If driver_id not provided but driver_name is, create driver (and add contact column if missing)
    try:
        # ensure drivers table has 'contact' column (safe to ignore if already exists)
        cols = [r[1] for r in manager.db.query("PRAGMA table_info(drivers)")]
        if 'contact' not in cols:
            manager.db.execute("ALTER TABLE drivers ADD COLUMN contact TEXT")
    except Exception:
        # ignore migration errors
        pass

    try:
        if not driver_id and driver_name:
            # register_driver accepts (name, license_no) - we will leave license empty and store contact after
            did = manager.register_driver(driver_name, None)
            driver_id = did
            if driver_contact:
                manager.db.execute("UPDATE drivers SET contact=? WHERE id=?", (driver_contact, driver_id))
        elif driver_id and driver_contact:
            # update contact if provided
            try:
                manager.db.execute("UPDATE drivers SET contact=? WHERE id=?", (driver_contact, driver_id))
            except Exception:
                pass

        # validate bus/route compatibility: if route already has a bus assigned, it must match selected bus
        route_rows = manager.db.query("SELECT * FROM routes WHERE id=?", (route_id,))
        if not route_rows:
            raise ValueError("Route not found")
        route_row = route_rows[0]
        existing_bus_for_route = route_row["bus_id"]

        if existing_bus_for_route and bus_id and int(existing_bus_for_route) != int(bus_id):
            # incompatible: route expects a different bus
            flash("Selected bus is not assigned to this route. Either select the route's bus or update the route bus first.", "danger")
            return redirect(url_for('student_detail', student_id=student_id))

        # attach driver to bus if provided
        if bus_id and driver_id:
            manager.db.execute("UPDATE buses SET driver_id=? WHERE id=?", (driver_id, bus_id))

        # update route bus/pickup if route had no bus or pickup_location provided
        if pickup_location or (bus_id and not existing_bus_for_route):
            # set provided values only
            if pickup_location and bus_id and not existing_bus_for_route:
                manager.db.execute("UPDATE routes SET bus_id=?, pickup_location=? WHERE id=?", (bus_id, pickup_location, route_id))
            elif pickup_location:
                manager.db.execute("UPDATE routes SET pickup_location=? WHERE id=?", (pickup_location, route_id))
            elif bus_id and not existing_bus_for_route:
                manager.db.execute("UPDATE routes SET bus_id=? WHERE id=?", (bus_id, route_id))

        # finally assign student to route (will enforce duplicate prevention)
        aid = manager.assign_student_to_route(student_id, route_id)

        # build confirmation summary
        bus_info = None
        driver_info = None
        if bus_id:
            brows = manager.db.query("SELECT * FROM buses WHERE id=?", (bus_id,))
            if brows:
                bus_info = brows[0]
        if driver_id:
            drows = manager.db.query("SELECT * FROM drivers WHERE id=?", (driver_id,))
            if drows:
                driver_info = drows[0]

        parts = [f"alloc id {aid}", f"route: {route_row['name']}" if route_row.get('name') else f"route id {route_id}"]
        if bus_info:
            parts.append(f"bus: {bus_info['registration']}")
        if driver_info:
            dn = driver_info.get('name')
            dc = driver_info.get('contact') if 'contact' in driver_info.keys() else None
            if dc:
                parts.append(f"driver: {dn} ({dc})")
            else:
                parts.append(f"driver: {dn}")
        if pickup_location:
            parts.append(f"pickup: {pickup_location}")

        flash("Assigned transport — " + ", ".join(parts), "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for('student_detail', student_id=student_id))


@app.route("/allocations/<int:alloc_id>/checkout", methods=["POST"])
@login_required(roles=["admin"])
def checkout_allocation(alloc_id):
    # lookup allocation->student for redirect
    row = manager.db.query("SELECT student_id FROM hostel_allocations WHERE id=?", (alloc_id,))
    if not row:
        flash("Allocation not found", "danger")
        return redirect(url_for('students'))
    student_id = row[0]["student_id"]
    try:
        manager.checkout_student(alloc_id)
        flash("Student checked out", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for('student_detail', student_id=student_id))


@app.route("/students/add", methods=["GET", "POST"])
@login_required(roles=["admin"])
def add_student():
    if request.method == "POST":
        name = request.form.get("name")
        roll = request.form.get("roll_no")
        dept = request.form.get("department")
        contact = request.form.get("contact")
        address = request.form.get("address")
        username = request.form.get("username") or None
        password = request.form.get("password") or None
        sid = manager.add_student(name, roll, dept, contact, address, username, password)
        flash(f"Added student id {sid}", "success")
        return redirect(url_for("students"))
    return render_template("add_student.html")


@app.route("/rooms")
@login_required(roles=["admin"])
def rooms():
    rooms = manager.list_rooms()
    return render_template("rooms.html", rooms=rooms)


@app.route("/drivers")
@login_required(roles=["admin"])
def drivers():
    drivers = manager.list_drivers()
    return render_template("drivers.html", drivers=drivers)


@app.route("/drivers/add", methods=["GET", "POST"])
@login_required(roles=["admin"])
def add_driver():
    if request.method == "POST":
        name = request.form.get("name")
        lic = request.form.get("license_no")
        contact = request.form.get("contact")
        try:
            # ensure drivers table has contact column
            try:
                cols = [r[1] for r in manager.db.query("PRAGMA table_info(drivers)")]
                if 'contact' not in cols:
                    manager.db.execute("ALTER TABLE drivers ADD COLUMN contact TEXT")
            except Exception:
                pass

            did = manager.register_driver(name, lic)
            if contact:
                manager.db.execute("UPDATE drivers SET contact=? WHERE id=?", (contact, did))
            flash(f"Added driver id {did}", "success")
            return redirect(url_for("drivers"))
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("add_driver.html", name=name, license_no=lic, contact=contact)
    return render_template("add_driver.html")


@app.route("/drivers/<int:driver_id>/edit", methods=["GET", "POST"])
@login_required(roles=["admin"])
def edit_driver(driver_id):
    if request.method == "POST":
        name = request.form.get("name")
        license_no = request.form.get("license_no")
        contact = request.form.get("contact")
        try:
            manager.update_driver(driver_id, name=name, license_no=license_no)
            # store/update contact column if present
            try:
                cols = [r[1] for r in manager.db.query("PRAGMA table_info(drivers)")]
                if 'contact' in cols:
                    manager.db.execute("UPDATE drivers SET contact=? WHERE id=?", (contact, driver_id))
            except Exception:
                pass
            flash("Driver updated", "success")
            return redirect(url_for("drivers"))
        except ValueError as e:
            flash(str(e), "danger")
            driver = {"id": driver_id, "name": name, "license_no": license_no, "contact": contact}
            return render_template("edit_driver.html", driver=driver)
    # GET
    drivers = manager.list_drivers()
    driver = next((d for d in drivers if d['id'] == driver_id), None)
    if not driver:
        flash("Driver not found", "danger")
        return redirect(url_for('drivers'))
    return render_template("edit_driver.html", driver=driver)


@app.route("/drivers/<int:driver_id>/delete", methods=["POST"])
@login_required(roles=["admin"])
def delete_driver(driver_id):
    manager.delete_driver(driver_id)
    flash("Driver deleted", "success")
    return redirect(url_for("drivers"))


@app.route("/buses")
@login_required(roles=["admin"])
def buses():
    buses = manager.list_buses()
    return render_template("buses.html", buses=buses)


@app.route("/buses/add", methods=["GET", "POST"])
@login_required(roles=["admin"])
def add_bus():
    if request.method == "POST":
        reg = request.form.get("registration")
        cap = int(request.form.get("capacity") or 20)
        driver_id = request.form.get("driver_id")
        driver_id = int(driver_id) if driver_id else None
        try:
            bid = manager.register_bus(reg, cap, driver_id)
            flash(f"Added bus id {bid}", "success")
            return redirect(url_for("buses"))
        except ValueError as e:
            flash(str(e), "danger")
            drivers = manager.list_drivers()
            return render_template("add_bus.html", drivers=drivers, registration=reg, capacity=cap, driver_id=driver_id)
    drivers = manager.list_drivers()
    return render_template("add_bus.html", drivers=drivers)


@app.route("/buses/<int:bus_id>/edit", methods=["GET", "POST"])
@login_required(roles=["admin"])
def edit_bus(bus_id):
    if request.method == "POST":
        registration = request.form.get("registration")
        capacity = int(request.form.get("capacity") or 0)
        driver_id = request.form.get("driver_id")
        driver_id = int(driver_id) if driver_id else None
        try:
            manager.update_bus(bus_id, registration=registration, capacity=capacity, driver_id=driver_id)
            flash("Bus updated", "success")
            return redirect(url_for("buses"))
        except ValueError as e:
            flash(str(e), "danger")
            drivers = manager.list_drivers()
            bus = {"id": bus_id, "registration": registration, "capacity": capacity, "driver_id": driver_id}
            return render_template("edit_bus.html", bus=bus, drivers=drivers)
    buses = manager.list_buses()
    bus = next((b for b in buses if b['id'] == bus_id), None)
    if not bus:
        flash("Bus not found", "danger")
        return redirect(url_for('buses'))
    drivers = manager.list_drivers()
    return render_template("edit_bus.html", bus=bus, drivers=drivers)


@app.route("/buses/<int:bus_id>/delete", methods=["POST"])
@login_required(roles=["admin"])
def delete_bus(bus_id):
    manager.delete_bus(bus_id)
    flash("Bus deleted", "success")
    return redirect(url_for("buses"))


@app.route("/rooms/add", methods=["GET", "POST"])
@login_required(roles=["admin"])
def add_room():
    if request.method == "POST":
        block = request.form.get("block")
        room_no = request.form.get("room_no")
        capacity = int(request.form.get("capacity") or 1)
        rid = manager.add_room(block, room_no, capacity)
        flash(f"Added room id {rid}", "success")
        return redirect(url_for("rooms"))
    return render_template("add_room.html")


@app.route("/routes")
@login_required(roles=["admin"])
def routes_list():
    routes = manager.active_routes_report()
    return render_template("routes.html", routes=routes)


@app.route('/transport')
@login_required(roles=["admin"])
def transport_index():
    return render_template('transport_index.html')


@app.route('/admin/messages')
@login_required(roles=["admin"])
def admin_messages():
    messages = manager.list_contact_messages()
    return render_template('messages.html', messages=messages)


@app.route('/admin/messages/<int:msg_id>', methods=['GET', 'POST'])
@login_required(roles=["admin"])
def admin_message_detail(msg_id):
    msg = manager.get_contact_message(msg_id)
    if not msg:
        flash('Message not found', 'danger')
        return redirect(url_for('admin_messages'))

    # Build thread for this student's messages and extract subtree rooted at this message
    all_rows = manager.db.query("SELECT * FROM contact_messages WHERE student_id=? ORDER BY created ASC", (msg['student_id'],))
    msgs = [dict(r) for r in all_rows]
    id_map = {m['id']: m for m in msgs}
    for m in msgs:
        m.setdefault('children', [])
    roots = []
    for m in msgs:
        pid = m.get('parent_id')
        if pid:
            parent = id_map.get(pid)
            if parent:
                parent['children'].append(m)
            else:
                roots.append(m)
        else:
            roots.append(m)

    # find subtree for this msg_id (if msg is a child, find its root)
    def find_root(mid):
        cur = id_map.get(mid)
        while cur and cur.get('parent_id'):
            cur = id_map.get(cur.get('parent_id'))
        return cur

    root = find_root(msg_id)
    subtree = root if root else msg

    # mark root and its direct descendants as read (best-effort)
    try:
        manager.db.execute('UPDATE contact_messages SET is_read=1 WHERE id=? OR parent_id=?', (subtree['id'], subtree['id']))
    except Exception:
        pass

    if request.method == 'POST':
        # send reply to student: create a message record targeted at student
        subject = request.form.get('subject') or f"Re: {msg.get('subject','') }"
        message = request.form.get('message') or ''
        if not message.strip():
            flash('Reply cannot be empty', 'danger')
            return render_template('message_detail.html', root=subtree)
        try:
            # record reply: associate with root of thread
            mid = manager.record_contact_message(msg['student_id'], 'student', msg['student_id'], subject, message,
                                                 sender_role='admin', sender_id=None, parent_id=subtree['id'])
            flash(f'Reply sent (id {mid})', 'success')
        except Exception as e:
            flash(str(e), 'danger')

        return redirect(url_for('admin_messages'))

    return render_template('message_detail.html', root=subtree)


@app.route('/student/messages')
@login_required(roles=["student"])
def student_messages():
    user = session.get('user')
    student_id = user.get('student_id')
    if not student_id:
        flash('Student identity missing', 'danger')
        return redirect(url_for('dashboard'))

    roots = _build_threads_for_student(student_id)
    return render_template('student_messages.html', threads=roots)


@app.route('/student/messages/<int:msg_id>', methods=['GET', 'POST'])
@login_required(roles=["student"])
def student_message_detail(msg_id):
    user = session.get('user')
    student_id = user.get('student_id')
    if not student_id:
        flash('Student identity missing', 'danger')
        return redirect(url_for('dashboard'))

    # load all messages for this student and build tree
    all_rows = manager.db.query("SELECT * FROM contact_messages WHERE student_id=? ORDER BY created ASC", (student_id,))
    msgs = [dict(r) for r in all_rows]
    id_map = {m['id']: m for m in msgs}
    for m in msgs:
        m.setdefault('children', [])
    for m in msgs:
        pid = m.get('parent_id')
        if pid and pid in id_map:
            id_map[pid]['children'].append(m)

    target = id_map.get(msg_id)
    if not target:
        flash('Message not found', 'danger')
        return redirect(url_for('student_messages'))

    # find root of this thread
    root = target
    while root.get('parent_id'):
        root = id_map.get(root['parent_id'], root)

    # mark as read for student view as well
    try:
        manager.db.execute('UPDATE contact_messages SET is_read=1 WHERE id=? OR parent_id=?', (root['id'], root['id']))
    except Exception:
        pass

    if request.method == 'POST':
        subject = request.form.get('subject') or f"Re: {root.get('subject','') }"
        message = request.form.get('message') or ''
        if not message.strip():
            flash('Reply cannot be empty', 'danger')
            return render_template('student_message_detail.html', root=root)
        try:
            mid = manager.record_contact_message(student_id, 'admin', None, subject, message,
                                                 sender_role='student', sender_id=student_id, parent_id=root['id'])
            flash(f'Reply sent (id {mid})', 'success')
        except Exception as e:
            flash(str(e), 'danger')
        return redirect(url_for('student_messages'))

    return render_template('student_message_detail.html', root=root)


def _build_threads_for_student(student_id):
    rows = manager.db.query("SELECT * FROM contact_messages WHERE student_id=? ORDER BY created ASC", (student_id,))
    msgs = [dict(r) for r in rows]
    id_map = {m['id']: m for m in msgs}
    for m in msgs:
        m.setdefault('children', [])
    roots = []
    for m in msgs:
        pid = m.get('parent_id')
        if pid and pid in id_map:
            id_map[pid]['children'].append(m)
        else:
            roots.append(m)
    # newest first
    roots.sort(key=lambda x: x.get('created') or '', reverse=True)
    return roots


@app.route("/routes/add", methods=["GET", "POST"])
@login_required(roles=["admin"])
def add_route():
    if request.method == "POST":
        name = request.form.get("name")
        pickup = request.form.get("pickup")
        fee = float(request.form.get("fee") or 0)
        bus_id = request.form.get("bus_id")
        bus_id = int(bus_id) if bus_id else None
        rid = manager.register_route(name, pickup, bus_id, fee)
        flash(f"Added route id {rid}", "success")
        return redirect(url_for("routes_list"))
    return render_template("add_route.html")


@app.route('/routes/<int:route_id>/edit', methods=['GET', 'POST'])
@login_required(roles=["admin"])
def edit_route(route_id):
    # GET: render form with current route, buses; POST: update bus_id and pickup_location
    routes = manager.active_routes_report()
    route = next((r for r in routes if r['id'] == route_id), None)
    if not route:
        flash('Route not found', 'danger')
        return redirect(url_for('routes_list'))

    if request.method == 'POST':
        bus_id_raw = request.form.get('bus_id')
        pickup = request.form.get('pickup_location')
        bus_id = int(bus_id_raw) if bus_id_raw else None
        try:
            if bus_id:
                manager.db.execute('UPDATE routes SET bus_id=? WHERE id=?', (bus_id, route_id))
            else:
                manager.db.execute('UPDATE routes SET bus_id=NULL WHERE id=?', (route_id,))
            if pickup is not None:
                manager.db.execute('UPDATE routes SET pickup_location=? WHERE id=?', (pickup, route_id))
            flash('Route updated', 'success')
            return redirect(url_for('routes_list'))
        except Exception as e:
            flash(str(e), 'danger')

    buses = manager.list_buses()
    return render_template('edit_route.html', route=route, buses=buses)


@app.route("/transport/enroll", methods=["POST"])
@login_required(roles=["student"])
def transport_enroll():
    user = session.get("user")
    student_id = user.get("student_id")
    route_id_raw = request.form.get("route_id")
    if not route_id_raw:
        flash("Please select a route", "danger")
        return redirect(url_for("dashboard"))
    try:
        route_id = int(route_id_raw)
    except (ValueError, TypeError):
        flash("Invalid route selection", "danger")
        return redirect(url_for("dashboard"))

    try:
        manager.assign_student_to_route(student_id, route_id)
        flash("Enrolled to route", "success")
    except Exception as e:
        flash(str(e), "danger")
    return redirect(url_for("dashboard"))


@app.route("/transport/pay", methods=["POST"])
@login_required(roles=["student"])
def transport_pay():
    user = session.get("user")
    student_id = user.get("student_id")
    amount = float(request.form.get("amount"))
    try:
        pid = manager.record_transport_payment(student_id, amount)
        # fetch payment details to notify admin
        prow = manager.db.query('SELECT * FROM transport_payments WHERE id=?', (pid,))
        if prow:
            p = dict(prow[0])
            student = manager.get_student(student_id) or {}
            sname = student.get('name') or f'#{student_id}'
            subject = f"Transport payment received from {sname}"
            message = f"Student {sname} (id {student_id}) paid {p.get('amount')} on {p.get('date')}. Receipt: {p.get('receipt_no') or ''}"
            try:
                manager.record_contact_message(student_id, 'admin', None, subject, message, sender_role='student', sender_id=student_id)
            except Exception:
                pass
        flash("Payment recorded", "success")
        return redirect(url_for('payment_receipt', ptype='transport', pid=pid))
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('dashboard'))


@app.route('/student/contact', methods=['POST'])
@login_required(roles=["student"])
def student_contact():
    user = session.get('user')
    student_id = user.get('student_id')
    if not student_id:
        flash('Student identity missing', 'danger')
        return redirect(url_for('dashboard'))

    to_role = request.form.get('to_role') or 'admin'
    to_id_raw = request.form.get('to_id')
    to_id = int(to_id_raw) if to_id_raw else None
    subject = request.form.get('subject') or ''
    message = request.form.get('message') or ''

    if not message.strip():
        flash('Message cannot be empty', 'danger')
        return redirect(url_for('dashboard'))

    try:
        mid = manager.record_contact_message(student_id, to_role, to_id, subject, message,
                                             sender_role='student', sender_id=student_id)
        flash('Message sent. Reference id: {}'.format(mid), 'success')
    except Exception as e:
        flash(str(e), 'danger')

    return redirect(url_for('dashboard'))


@app.route('/student/contact', methods=['GET'])
@login_required(roles=["student"])
def student_contact_page():
    user = session.get('user')
    student_id = user.get('student_id')
    if not student_id:
        flash('Student identity missing', 'danger')
        return redirect(url_for('dashboard'))
    # provide drivers list for 'send to' options
    drivers = manager.list_drivers()
    return render_template('student_contact.html', drivers=drivers)


@app.route('/student/pay', methods=['GET'])
@login_required(roles=["student"])
def student_pay_page():
    user = session.get('user')
    student_id = user.get('student_id')
    if not student_id:
        flash('Student identity missing', 'danger')
        return redirect(url_for('dashboard'))
    profile = manager.get_student_profile(student_id)
    return render_template('student_pay.html', profile=profile)


@app.route('/hostel/pay', methods=['POST'])
@login_required(roles=["student"])
def hostel_pay():
    user = session.get('user')
    student_id = user.get('student_id')
    amount_raw = request.form.get('amount')
    try:
        amount = float(amount_raw)
    except Exception:
        flash('Invalid amount', 'danger')
        return redirect(url_for('student_pay_page'))
    try:
        pid = manager.record_hostel_payment(student_id, amount)
        # notify admin about hostel payment
        hrow = manager.db.query('SELECT * FROM hostel_payments WHERE id=?', (pid,))
        if hrow:
            h = dict(hrow[0])
            student = manager.get_student(student_id) or {}
            sname = student.get('name') or f'#{student_id}'
            subject = f"Hostel payment received from {sname}"
            message = f"Student {sname} (id {student_id}) paid {h.get('amount')} on {h.get('date')}. Receipt: {h.get('receipt_no') or ''}"
            try:
                manager.record_contact_message(student_id, 'admin', None, subject, message, sender_role='student', sender_id=student_id)
            except Exception:
                pass
        flash('Hostel payment recorded', 'success')
        return redirect(url_for('payment_receipt', ptype='hostel', pid=pid))
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('student_pay_page'))


if __name__ == "__main__":
    app.run(debug=True)


@app.route('/payment/receipt/<ptype>/<int:pid>')
@login_required(roles=["student"]) 
def payment_receipt(ptype, pid):
    user = session.get('user')
    student_id = user.get('student_id')
    if ptype == 'transport':
        rows = manager.db.query('SELECT * FROM transport_payments WHERE id=? AND student_id=?', (pid, student_id))
        if not rows:
            flash('Receipt not found', 'danger')
            return redirect(url_for('student_pay_page'))
        p = dict(rows[0])
        p['type'] = 'Transport'
    elif ptype == 'hostel':
        rows = manager.db.query('SELECT * FROM hostel_payments WHERE id=? AND student_id=?', (pid, student_id))
        if not rows:
            flash('Receipt not found', 'danger')
            return redirect(url_for('student_pay_page'))
        p = dict(rows[0])
        p['type'] = 'Hostel'
    else:
        flash('Unknown payment type', 'danger')
        return redirect(url_for('student_pay_page'))

    return render_template('payment_receipt.html', payment=p)
