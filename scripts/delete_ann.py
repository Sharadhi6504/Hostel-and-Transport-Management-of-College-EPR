from erp.db import Database

TARGET = "Hello! this is admin"

def main():
    db = Database()
    try:
        rows = db.query("SELECT id, title, message FROM announcements WHERE title=? OR message=?", (TARGET, TARGET))
        if not rows:
            print(f"No announcements found matching: {TARGET}")
            return
        print(f"Found {len(rows)} matching announcement(s):")
        for r in rows:
            print(f" - id={r['id']} title={r['title']} message={r['message'][:80]}")
        # Delete them
        ids = [str(r['id']) for r in rows]
        for i in ids:
            db.execute("DELETE FROM dismissed_announcements WHERE announcement_id=?", (i,))
            db.execute("DELETE FROM announcements WHERE id=?", (i,))
        print(f"Deleted announcements with ids: {', '.join(ids)}")
    finally:
        db.close()

if __name__ == '__main__':
    main()
