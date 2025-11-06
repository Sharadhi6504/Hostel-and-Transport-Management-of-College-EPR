# College ERP — Hostel & Transport Management

Lightweight college ERP implemented in Python + SQLite. It started as a CLI and now includes a Flask web UI demo. The project focuses on hostel and transport administration and a simple student-facing profile/notifications experience.

Features:
- Users: Admin and Student (the repo seeds an admin user: username `admin`, password `admin`).
- Student CRUD: add/update/delete students, basic profile data.
- Hostel: rooms, capacity checks, allocations, check-in/out, payments and simple reports.
- Transport: drivers, buses, routes, student route assignments, transport payments, attendance.

How to run:
1. Ensure Python 3.8+ is installed and available on PATH.
2. From the repository root run the CLI:

```powershell
python .\main.py
```

3. Open the app in your browser (by default http://127.0.0.1:5000). Login as the seeded admin (`admin`/`admin`) to access Announcement management under the admin dashboard.

Notes & next steps:
- Unit tests are present and can be run with:

```powershell
python -m unittest discover -v
```

Maintenance notes
- Runtime migrations: `erp/db.py` attempts safe ALTER TABLE operations to add new columns when upgrading an existing DB. This is convenient for development but you may want a formal migration strategy for production.

Contributing & next steps
- Add admin visibility to per-student dismissals if you need auditing of who dismissed which announcement.
- Add an unread/new badge on the Notifications button (easy UX improvement).
- Add tests for announcements (scheduling, dismissal persistence, notifications listing behavior).



