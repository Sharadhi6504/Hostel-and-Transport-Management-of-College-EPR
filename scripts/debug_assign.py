import os
import sys
_HERE = os.path.abspath(os.path.dirname(__file__))
# ensure project root is on sys.path so `import web` works when script is run directly
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, '..')))

from web import app as flask_app
import importlib
webapp_module = importlib.import_module('web.app')
from erp.manager import ERPManager

m = ERPManager(db_path=':memory:')
webapp_module.manager = m
print('WEB module manager before wrapping:', webapp_module.assign_route.__globals__.get('manager'))
flask_app.config['TESTING'] = True
client = flask_app.test_client()

# create student and route
sid = m.add_student(name='AR Student', username=None, password=None)
rid = m.register_route('R1','Gate', None, 50.0)
print('sid, rid', sid, rid)

try:
    print('Direct assign attempt:')
    aid = m.assign_student_to_route(sid, rid)
    print('Assigned id', aid)
except Exception as e:
    print('Direct assign exception:', e)

with client as c:
    # debug: show any existing transport allocations before POST
    before = m.db.query('SELECT * FROM transport_allocations')
    print('before allocs', [dict(r) for r in before])
    with c.session_transaction() as sess:
        sess['user'] = {'username':'admin','role':'admin'}
    # wrap assign_student_to_route to log debug info when called by route
    orig_assign = m.assign_student_to_route
    def dbg_assign(student_id, route_id):
        print('DBG: in assign_student_to_route, db path=', m.db.path)
        rows = m.db.query('SELECT * FROM transport_allocations WHERE student_id=? AND route_id=?', (student_id, route_id))
        print('DBG: existing alloc rows before insert', [dict(r) for r in rows])
        return orig_assign(student_id, route_id)
    m.assign_student_to_route = dbg_assign
    resp = c.post(f'/students/{sid}/assign_route', data={'route_id':str(rid)}, follow_redirects=True)
    print('status', resp.status_code)
    full = resp.data.decode()
    print(full)

rows = m.db.query('SELECT * FROM transport_allocations WHERE student_id=? AND route_id=?', (sid, rid))
print('alloc rows', [dict(r) for r in rows])
