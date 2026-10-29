"""Haven: Dormitory and Housing Management System (Flask + SQLite).
Run:  pip install -r requirements.txt   then   python app.py   then open http://127.0.0.1:5001
Keep index.html in the same folder as this file.
"""
import datetime
import os
import random
import sqlite3
from functools import wraps

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "dormhub.db"))
app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK (role IN ('Admin','Staff')));
CREATE TABLE IF NOT EXISTS rooms (
    room_id INTEGER PRIMARY KEY AUTOINCREMENT, room_no TEXT NOT NULL UNIQUE, building TEXT NOT NULL,
    floor INTEGER NOT NULL, room_type TEXT NOT NULL, capacity INTEGER NOT NULL CHECK (capacity > 0),
    monthly_rate REAL NOT NULL);
CREATE TABLE IF NOT EXISTS residents (
    resident_id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL, contact_no TEXT, email TEXT,
    occupation TEXT, emergency_contact TEXT, date_registered TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS leases (
    lease_id INTEGER PRIMARY KEY AUTOINCREMENT, resident_id INTEGER NOT NULL REFERENCES residents(resident_id),
    room_id INTEGER NOT NULL REFERENCES rooms(room_id), start_date TEXT NOT NULL, end_date TEXT,
    status TEXT NOT NULL CHECK (status IN ('Active','Ended')));
CREATE TABLE IF NOT EXISTS payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT, lease_id INTEGER NOT NULL REFERENCES leases(lease_id),
    amount REAL NOT NULL CHECK (amount > 0), method TEXT, period TEXT NOT NULL, date_paid TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS maintenance (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER NOT NULL REFERENCES rooms(room_id),
    issue TEXT NOT NULL, priority TEXT NOT NULL CHECK (priority IN ('Low','Medium','High')),
    status TEXT NOT NULL CHECK (status IN ('Open','In Progress','Resolved')), date_reported TEXT NOT NULL);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def iso(days=0):
    return (datetime.date.today() + datetime.timedelta(days=days)).isoformat()


def add_months(d, n):
    m = d.month - 1 + n
    return d.replace(year=d.year + m // 12, month=m % 12 + 1, day=1)


# ---------------------------------------------------------------- fictional data
FIRST = ["Miguel", "Andrea", "Joshua", "Camille", "Paolo", "Isabel", "Gabriel", "Trisha", "Anton", "Bea",
         "Kenneth", "Lyka", "Darwin", "Maribel", "Oscar", "Hazel", "Raymond", "Selena", "Tomas", "Yvonne",
         "Harold", "Nina", "Basil", "Pia", "Rico", "Wendy", "Efren", "Joy", "Lance", "Dolores",
         "Ulysses", "Mara", "Cyrus", "Elaine", "Nestor", "Gina", "Felix", "Honey", "Ivan", "Liza"]
LAST = ["Abad", "Bonifacio", "Capistrano", "Dumlao", "Evangelista", "Fajardo", "Gatchalian", "Hizon", "Imperial",
        "Jacinto", "Katigbak", "Labrador", "Montes", "Nepomuceno", "Ortega", "Pangilinan", "Quiambao", "Rivera",
        "Sandoval", "Tuazon", "Umali", "Vergara", "Wenceslao", "Yambao", "Zaragoza", "Angeles", "Borromeo",
        "Cordero", "Delos Reyes", "Enriquez"]
JOBS = ["Nurse", "Call center agent", "Line cook", "Graphic designer", "Electrician", "Bank teller", "Delivery rider",
        "Warehouse clerk", "Barista", "Accountant", "Hotel receptionist", "Seamstress", "Mechanic",
        "Sales associate", "Security officer", "Software tester", "Pharmacy assistant", "Welder"]
ISSUES = ["Leaking faucet", "Broken door lock", "Flickering ceiling light", "Air conditioner not cooling",
          "Clogged sink drain", "Loose window latch", "No hot water", "Wi-Fi router not working",
          "Bed frame squeaking", "Wall socket not working"]
BUILDINGS = ["Aster Hall", "Birch House", "Cedar Court"]


def phone(r):
    return f"09{r.choice(['17', '18', '28', '05', '20'])}-555-{r.randint(0, 9999):04d}"


def seed_demo(db):
    """60 rooms, 150 residents (110 living in, 40 moved out), rent payments, 40 repair requests."""
    r = random.Random(11)
    today = datetime.date.today()
    shapes = [("Single", 1, 4500)] * 20 + [("Double", 2, 3200)] * 25 + [("Quad", 4, 2200)] * 15
    r.shuffle(shapes)
    i = 0
    for b in BUILDINGS:
        for fl in range(1, 5):
            for n in range(1, 6):
                t, cap, rate = shapes[i]
                i += 1
                db.execute("INSERT INTO rooms (room_no, building, floor, room_type, capacity, monthly_rate) VALUES (?,?,?,?,?,?)",
                           (f"{b[0]}{fl}0{n}", b, fl, t, cap, rate + (fl - 1) * 100))
    used = set()
    for _ in range(150):
        while True:
            name = f"{r.choice(FIRST)} {r.choice(LAST)}"
            if name not in used:
                used.add(name)
                break
        db.execute("INSERT INTO residents (full_name, contact_no, email, occupation, emergency_contact, date_registered) VALUES (?,?,?,?,?,?)",
                   (name, phone(r), name.lower().replace(" ", ".") + str(r.randint(1, 99)) + "@example.com",
                    r.choice(JOBS), f"{r.choice(FIRST)} {r.choice(LAST)} - {phone(r)}", iso(-r.randint(20, 600))))
    rooms = [dict(x) for x in db.execute("SELECT * FROM rooms")]
    free = {x["room_id"]: x["capacity"] for x in rooms}
    for n, (rid,) in enumerate(db.execute("SELECT resident_id FROM residents ORDER BY resident_id").fetchall()):
        if n < 110:
            room = r.choice([x for x in rooms if free[x["room_id"]] > 0])
            free[room["room_id"]] -= 1
            start, end, st = today - datetime.timedelta(days=r.randint(20, 420)), None, "Active"
        else:
            room = r.choice(rooms)
            start = today - datetime.timedelta(days=r.randint(200, 600))
            end, st = today - datetime.timedelta(days=r.randint(15, 150)), "Ended"
        lid = db.execute("INSERT INTO leases (resident_id, room_id, start_date, end_date, status) VALUES (?,?,?,?,?)",
                         (rid, room["room_id"], start.isoformat(), end.isoformat() if end else None, st)).lastrowid

        def pay(d):
            period = d.strftime("%Y-%m")
            db.execute("INSERT INTO payments (lease_id, amount, method, period, date_paid) VALUES (?,?,?,?,?)",
                       (lid, room["monthly_rate"], r.choice(["Cash", "GCash", "Bank transfer"]), period, f"{period}-{r.randint(1, 5):02d}"))
        if st == "Active":
            for k in range(min(6, (today - start).days // 30 + 1)):
                if (k == 0 and r.random() < .3) or (k > 0 and r.random() < .05):
                    continue
                pay(add_months(today, -k))
        else:
            for k in range(r.randint(2, 4)):
                pay(add_months(start, k))
    for _ in range(40):
        db.execute("INSERT INTO maintenance (room_id, issue, priority, status, date_reported) VALUES (?,?,?,?,?)",
                   (r.choice(rooms)["room_id"], r.choice(ISSUES), r.choice(["Low", "Medium", "High"]),
                    r.choices(["Open", "In Progress", "Resolved"], [3, 2, 5])[0], iso(-r.randint(1, 60))))


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        db.executemany("INSERT INTO users (full_name, username, password_hash, role) VALUES (?,?,?,?)", [
            ("Housing Administrator", "admin", generate_password_hash("admin123"), "Admin"),
            ("Front Desk Staff", "staff", generate_password_hash("staff123"), "Staff")])
        seed_demo(db)
    db.commit()
    db.close()


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        if "user" not in session:
            return jsonify(error="Please log in."), 401
        return fn(*a, **k)
    return wrapper


def fail(msg, code=400):
    return jsonify(error=msg), code


@app.get("/")
def home():
    return send_from_directory(BASE, "index.html")


# ---------------------------------------------------------------- auth
@app.post("/api/login")
def login():
    d = request.get_json(force=True, silent=True) or {}
    row = get_db().execute("SELECT * FROM users WHERE username = ?", (str(d.get("u", "")).strip().lower(),)).fetchone()
    if row and check_password_hash(row["password_hash"], str(d.get("p", "")).strip()):
        session["user"] = row["username"]
        return jsonify(user=row["username"])
    return jsonify(error="Wrong username or password."), 401


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    return jsonify(user=session["user"]) if "user" in session else (jsonify(error="no"), 401)


# ---------------------------------------------------------------- data
@app.get("/api/data")
@login_required
def data():
    q = lambda sql: get_db().execute(sql).fetchall()
    return jsonify(
        r=[{"id": x["room_id"], "no": x["room_no"], "bld": x["building"], "floor": x["floor"], "type": x["room_type"],
            "cap": x["capacity"], "rate": x["monthly_rate"], "occ": x["occ"]} for x in q(
            "SELECT rooms.*, (SELECT COUNT(*) FROM leases WHERE room_id = rooms.room_id AND status = 'Active') AS occ "
            "FROM rooms ORDER BY building, floor, room_no")],
        c=[{"id": x["resident_id"], "name": x["full_name"], "contact": x["contact_no"], "email": x["email"],
            "job": x["occupation"], "emerg": x["emergency_contact"], "date": x["date_registered"]}
           for x in q("SELECT * FROM residents ORDER BY resident_id")],
        l=[{"id": x["lease_id"], "rid": x["resident_id"], "room": x["room_id"], "start": x["start_date"],
            "end": x["end_date"], "status": x["status"]} for x in q("SELECT * FROM leases ORDER BY lease_id")],
        pay=[{"id": x["payment_id"], "lid": x["lease_id"], "amt": x["amount"], "method": x["method"],
              "period": x["period"], "date": x["date_paid"]} for x in q("SELECT * FROM payments ORDER BY date_paid, payment_id")],
        m=[{"id": x["request_id"], "room": x["room_id"], "issue": x["issue"], "pri": x["priority"],
            "status": x["status"], "date": x["date_reported"]} for x in q("SELECT * FROM maintenance ORDER BY request_id")])


@app.post("/api/<action>")
@login_required
def act(action):
    d = request.get_json(force=True, silent=True) or {}
    db = get_db()
    try:
        if action == "addR":
            db.execute("INSERT INTO residents (full_name, contact_no, email, occupation, emergency_contact, date_registered) VALUES (?,?,?,?,?,?)",
                       (d["name"].strip(), d.get("contact"), d.get("email"), d.get("job"), d.get("emerg"), iso()))
        elif action == "addRoom":
            db.execute("INSERT INTO rooms (room_no, building, floor, room_type, capacity, monthly_rate) VALUES (?,?,?,?,?,?)",
                       (d["no"].strip(), d["bld"].strip(), int(d["floor"]), d["type"], int(d["cap"]), float(d["rate"])))
        elif action == "delRoom":
            room_id = int(d["id"])
            db.execute("DELETE FROM payments WHERE lease_id IN (SELECT lease_id FROM leases WHERE room_id = ?)", (room_id,))
            db.execute("DELETE FROM leases WHERE room_id = ?", (room_id,))
            db.execute("DELETE FROM maintenance WHERE room_id = ?", (room_id,))
            db.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
        elif action == "assign":
            rid, room_id = int(d["rid"]), int(d["room_id"])
            if db.execute("SELECT 1 FROM leases WHERE resident_id = ? AND status = 'Active'", (rid,)).fetchone():
                return fail("This resident already has an active stay. End it before assigning a new room.")
            room = db.execute("SELECT capacity, (SELECT COUNT(*) FROM leases WHERE room_id = rooms.room_id AND status = 'Active') AS occ "
                              "FROM rooms WHERE room_id = ?", (room_id,)).fetchone()
            if room["occ"] >= room["capacity"]:
                return fail("This room is full. Choose a room with an open bed.")
            db.execute("INSERT INTO leases (resident_id, room_id, start_date, end_date, status) VALUES (?,?,?,NULL,'Active')",
                       (rid, room_id, d["start"]))
        elif action == "endLease":
            db.execute("UPDATE leases SET status = 'Ended', end_date = ? WHERE lease_id = ?", (iso(), int(d["lid"])))
        elif action == "delLease":
            lid = int(d["id"])
            db.execute("DELETE FROM payments WHERE lease_id = ?", (lid,))
            db.execute("DELETE FROM leases WHERE lease_id = ?", (lid,))
        elif action == "addPay":
            db.execute("INSERT INTO payments (lease_id, amount, method, period, date_paid) VALUES (?,?,?,?,?)",
                       (int(d["lid"]), float(d["amt"]), d["method"], d["period"], iso()))
        elif action == "addM":
            db.execute("INSERT INTO maintenance (room_id, issue, priority, status, date_reported) VALUES (?,?,?,'Open',?)",
                       (int(d["room_id"]), d["issue"].strip(), d["pri"], iso()))
        elif action == "setM":
            db.execute("UPDATE maintenance SET status = ? WHERE request_id = ?", (d["status"], int(d["id"])))
        elif action == "reset":
            for t in ["payments", "maintenance", "leases", "residents", "rooms"]:
                db.execute(f"DELETE FROM {t}")
            db.execute("DELETE FROM sqlite_sequence")
            if d.get("demo"):
                seed_demo(db)
        else:
            return fail("Unknown action.", 404)
        db.commit()
    except (KeyError, ValueError, TypeError, AttributeError, sqlite3.Error) as e:
        db.rollback()
        return fail(f"Could not save: {e}")
    return jsonify(ok=True)


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
