# ============================================================
#  BachatKhana Backend v2 — Login (OTP) + Razorpay UPI
#  Khana Bachao, Paise Bachao 🍛
#
#  Chalane ke liye (Anaconda Prompt mein):
#     pip install flask flask-cors razorpay
#     python backend.py
#
#  Browser:  http://localhost:5000
#  (index.html isi folder mein honi chahiye)
# ============================================================

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import random
import secrets
import hmac
import hashlib
import time
import os

# ==================== CONFIG ====================
# DEV_MODE True = OTP screen aur console mein dikhega (SMS nahi jayega).
# Asli launch pe False karo aur send_sms_otp() mein SMS provider jodo.
DEV_MODE = True

# Razorpay keys — dashboard.razorpay.com -> Settings -> API Keys -> Generate Test Key
# Yahan paste karo. Khaali chhodo toh app "demo payment" mode mein chalegi.
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")        # Render pe: Environment tab mein daalna
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")  # (laptop pe chaho toh in dono lines ki jagah seedha "..." mein keys likh do)
# DHYAN: Secret key kisi ko mat bhejna, GitHub pe mat daalna!
# ================================================

try:
    import razorpay
except ImportError:
    razorpay = None

rzp_client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    if razorpay is None:
        print("[WARN] razorpay install nahi hai -> pip install razorpay | Abhi demo mode chalega.")
    else:
        rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bachatkhana.db")

app = Flask(__name__)
CORS(app)

BASE_IMPACT = {"meals": 12480, "rupees": 962000, "kg": 5230}

SEED = [
    ("Guru Kripa Sweets", "Sarafa", "Kaju katli + mix mithai box (400g)", "🍬", 1, 6, 320, 99, "9:00 – 11:30 PM", 4.6, "1.2 km"),
    ("Indori Poha House", "Bhawarkua", "Poha-jalebi combo (2 plate)", "🥘", 1, 8, 80, 30, "10:30 AM – 12 PM", 4.4, "400 m"),
    ("Sunrise Bakery", "Vijay Nagar", "Assorted pastries (4 pc)", "🍰", 1, 5, 240, 89, "8:30 – 10:00 PM", 4.5, "900 m"),
    ("Sharma Tiffin Service", "Palasia", "Ghar jaisi thali — dal, chawal, roti, sabzi", "🍛", 1, 10, 120, 49, "9:00 – 10:30 PM", 4.7, "1.8 km"),
    ("Chappan Hot Dog Corner", "Chappan Dukan", "Veg hot dog + benjo (2 pc)", "🌭", 1, 7, 140, 59, "9:30 – 11:00 PM", 4.8, "2.1 km"),
    ("Al-Karam Kitchen", "Palasia", "Chicken biryani (full plate)", "🍗", 0, 4, 220, 89, "9:30 – 11:00 PM", 4.3, "1.5 km"),
    ("Madhuram Namkeen", "Vijay Nagar", "Fresh namkeen mix (500g)", "🥨", 1, 9, 180, 69, "7:00 – 9:30 PM", 4.5, "650 m"),
    ("Cake Walk", "Vijay Nagar", "Day-end bread + buns bundle", "🍞", 1, 3, 150, 45, "8:30 – 10:00 PM", 4.2, "1.1 km"),
]


# ---------- Database ----------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop TEXT NOT NULL, area TEXT NOT NULL, item TEXT NOT NULL,
            emoji TEXT DEFAULT '🍛', veg INTEGER DEFAULT 1,
            qty INTEGER NOT NULL, mrp INTEGER NOT NULL, price INTEGER NOT NULL,
            pickup_window TEXT, rating REAL DEFAULT 5.0,
            dist TEXT DEFAULT '0 m', mine INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL, listing_id INTEGER,
            shop TEXT, item TEXT, emoji TEXT,
            qty INTEGER, total INTEGER, saved INTEGER,
            pickup_window TEXT, area TEXT,
            status TEXT DEFAULT 'READY', created_at INTEGER,
            user_id INTEGER, payment_id TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE NOT NULL,
            name TEXT DEFAULT '',
            created_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS otps (
            phone TEXT PRIMARY KEY,
            otp TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at INTEGER
        );
    """)
    # Purane v1 database ke liye migration (columns add karo agar nahi hain)
    for col in ("user_id INTEGER", "payment_id TEXT"):
        try:
            conn.execute(f"ALTER TABLE orders ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # column pehle se hai
    count = conn.execute("SELECT COUNT(*) AS c FROM listings").fetchone()["c"]
    if count == 0:
        conn.executemany(
            """INSERT INTO listings
               (shop, area, item, emoji, veg, qty, mrp, price, pickup_window, rating, dist)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            SEED,
        )
    conn.commit()
    conn.close()


def listing_json(r):
    return {
        "id": r["id"], "shop": r["shop"], "area": r["area"], "item": r["item"],
        "emoji": r["emoji"], "veg": bool(r["veg"]), "qty": r["qty"],
        "mrp": r["mrp"], "price": r["price"], "window": r["pickup_window"],
        "rating": r["rating"], "dist": r["dist"], "mine": bool(r["mine"]),
    }


def order_json(r):
    return {
        "id": r["id"], "code": r["code"], "shop": r["shop"], "item": r["item"],
        "emoji": r["emoji"], "qty": r["qty"], "total": r["total"], "saved": r["saved"],
        "window": r["pickup_window"], "area": r["area"], "status": r["status"],
    }


def make_code(conn):
    while True:
        code = "IND-" + str(random.randint(1000, 9999))
        if not conn.execute("SELECT 1 FROM orders WHERE code = ?", (code,)).fetchone():
            return code


# ---------- Auth helpers ----------

def send_sms_otp(phone, otp):
    """DEV_MODE: console mein print. Production: yahan MSG91 / 2Factor / Twilio
    ka API call aayega — bas is function ke andar, aur kuch nahi badalna."""
    print(f"  [OTP] +91 {phone} ke liye OTP hai: {otp}   (5 minute valid)")


def current_user():
    """Authorization: Bearer <token> header se logged-in user nikalo."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    conn = db()
    row = conn.execute(
        """SELECT u.id, u.phone, u.name FROM sessions s
           JOIN users u ON u.id = s.user_id WHERE s.token = ?""",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def need_login():
    return jsonify({"error": "Login karo pehle"}), 401


init_db()  # server start hote hi tables ready — Render/gunicorn ke liye zaroori


# ---------- Frontend ----------

@app.route("/")
def home():
    p = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(p):
        return send_from_directory(BASE_DIR, "index.html")
    return ("<h2>BachatKhana backend chal raha hai ✅</h2>"
            "<p><b>index.html</b> ko isi folder mein daalo, phir refresh karo.</p>")


# ---------- API: Auth ----------

@app.post("/api/auth/send-otp")
def send_otp():
    d = request.get_json(force=True, silent=True) or {}
    phone = "".join(ch for ch in str(d.get("phone") or "") if ch.isdigit())[-10:]
    if len(phone) != 10:
        return jsonify({"error": "10 digit ka mobile number daalo"}), 400

    otp = str(random.randint(100000, 999999))
    conn = db()
    conn.execute(
        "REPLACE INTO otps (phone, otp, expires_at) VALUES (?, ?, ?)",
        (phone, otp, int(time.time()) + 300),
    )
    is_new = conn.execute("SELECT 1 FROM users WHERE phone = ?", (phone,)).fetchone() is None
    conn.commit()
    conn.close()

    send_sms_otp(phone, otp)
    resp = {"ok": True, "is_new": is_new}
    if DEV_MODE:
        resp["demo_otp"] = otp  # sirf dev mode — production mein yeh line kabhi nahi jaati
    return jsonify(resp)


@app.post("/api/auth/verify-otp")
def verify_otp():
    d = request.get_json(force=True, silent=True) or {}
    phone = "".join(ch for ch in str(d.get("phone") or "") if ch.isdigit())[-10:]
    otp = str(d.get("otp") or "").strip()
    name = str(d.get("name") or "").strip()

    conn = db()
    row = conn.execute("SELECT * FROM otps WHERE phone = ?", (phone,)).fetchone()
    if not row or row["otp"] != otp or row["expires_at"] < int(time.time()):
        conn.close()
        return jsonify({"error": "Galat ya expire ho chuka OTP"}), 400

    conn.execute("DELETE FROM otps WHERE phone = ?", (phone,))
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if user is None:
        cur = conn.execute(
            "INSERT INTO users (phone, name, created_at) VALUES (?, ?, ?)",
            (phone, name, int(time.time())),
        )
        user_id, user_name = cur.lastrowid, name
    else:
        user_id, user_name = user["id"], user["name"]
        if name and not user_name:
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
            user_name = name

    token = secrets.token_hex(24)
    conn.execute(
        "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user_id, int(time.time())),
    )
    conn.commit()
    conn.close()
    return jsonify({"token": token, "user": {"phone": phone, "name": user_name}})


@app.get("/api/me")
def me():
    u = current_user()
    if not u:
        return need_login()
    return jsonify({"phone": u["phone"], "name": u["name"]})


# ---------- API: Listings ----------

@app.get("/api/listings")
def get_listings():
    conn = db()
    rows = conn.execute("SELECT * FROM listings ORDER BY mine DESC, id ASC").fetchall()
    conn.close()
    return jsonify([listing_json(r) for r in rows])


@app.post("/api/listings")
def create_listing():
    u = current_user()
    if not u:
        return need_login()
    d = request.get_json(force=True, silent=True) or {}
    item = (d.get("item") or "").strip()
    try:
        mrp = int(d.get("mrp") or 0)
        price = int(d.get("price") or 0)
        qty = max(1, int(d.get("qty") or 1))
    except (TypeError, ValueError):
        return jsonify({"error": "MRP, price aur qty numbers hone chahiye"}), 400
    if not item or mrp <= 0 or price <= 0:
        return jsonify({"error": "Item, MRP aur bachat price — teeno bharo"}), 400
    if price >= mrp:
        return jsonify({"error": "Bachat price MRP se kam hona chahiye"}), 400

    conn = db()
    cur = conn.execute(
        """INSERT INTO listings (shop, area, item, emoji, veg, qty, mrp, price, pickup_window, rating, dist, mine)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        ("Meri Dukaan (demo)", "Vijay Nagar", item, d.get("emoji") or "🍛",
         1 if d.get("veg", True) else 0, qty, mrp, price,
         d.get("window") or "8:30 – 10:00 PM", 5.0, "0 m"),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(listing_json(row)), 201


# ---------- Order banane ka common helper ----------

def book_order(conn, listing_id, qty, user_id, payment_id):
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not row:
        return None, ("Listing nahi mili", 404)
    if qty > row["qty"]:
        return None, ("Itni quantity available nahi hai", 400)

    code = make_code(conn)
    conn.execute("UPDATE listings SET qty = qty - ? WHERE id = ?", (qty, listing_id))
    cur = conn.execute(
        """INSERT INTO orders (code, listing_id, shop, item, emoji, qty, total, saved,
                               pickup_window, area, status, created_at, user_id, payment_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'READY', ?, ?, ?)""",
        (code, listing_id, row["shop"], row["item"], row["emoji"], qty,
         row["price"] * qty, (row["mrp"] - row["price"]) * qty,
         row["pickup_window"], row["area"], int(time.time()), user_id, payment_id),
    )
    conn.commit()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (cur.lastrowid,)).fetchone()
    return order, None


# ---------- API: Payment (Razorpay ya demo) ----------

@app.post("/api/pay/create")
def pay_create():
    """Step 1: payment shuru karo. Razorpay keys hain toh Razorpay order banta hai,
    warna demo mode. Frontend isi hisaab se aage badhta hai."""
    u = current_user()
    if not u:
        return need_login()
    d = request.get_json(force=True, silent=True) or {}
    listing_id = d.get("listing_id")
    try:
        qty = max(1, int(d.get("qty") or 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Qty number hona chahiye"}), 400

    conn = db()
    row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Listing nahi mili"}), 404
    if qty > row["qty"]:
        return jsonify({"error": "Itni quantity available nahi hai"}), 400

    if rzp_client is None:
        return jsonify({"mode": "demo"})

    amount_paise = row["price"] * qty * 100  # Razorpay paise mein leta hai
    rzp_order = rzp_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"bk_{listing_id}_{int(time.time())}",
    })
    return jsonify({
        "mode": "razorpay",
        "key_id": RAZORPAY_KEY_ID,
        "rzp_order_id": rzp_order["id"],
        "amount": amount_paise,
    })


@app.post("/api/pay/confirm")
def pay_confirm():
    """Step 2 (sirf Razorpay mode): payment hone ke baad signature verify karo.
    Signature sahi = paisa sach mein aaya hai, tabhi parchi banti hai."""
    u = current_user()
    if not u:
        return need_login()
    d = request.get_json(force=True, silent=True) or {}
    rzp_order_id = str(d.get("razorpay_order_id") or "")
    rzp_payment_id = str(d.get("razorpay_payment_id") or "")
    signature = str(d.get("razorpay_signature") or "")

    if not (rzp_order_id and rzp_payment_id and signature and RAZORPAY_KEY_SECRET):
        return jsonify({"error": "Payment details adhoore hain"}), 400

    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{rzp_order_id}|{rzp_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return jsonify({"error": "Payment verify nahi hua — signature galat"}), 400

    conn = db()
    # Idempotent: same payment dobara aaye toh wahi parchi wapas do
    existing = conn.execute("SELECT * FROM orders WHERE payment_id = ?", (rzp_payment_id,)).fetchone()
    if existing:
        conn.close()
        return jsonify(order_json(existing))

    try:
        qty = max(1, int(d.get("qty") or 1))
    except (TypeError, ValueError):
        conn.close()
        return jsonify({"error": "Qty number hona chahiye"}), 400
    order, err = book_order(conn, d.get("listing_id"), qty, u["id"], rzp_payment_id)
    conn.close()
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(order_json(order)), 201


@app.post("/api/orders")
def create_order_demo():
    """Demo-mode booking (jab Razorpay keys nahi hain). Asli paisa nahi lagta."""
    u = current_user()
    if not u:
        return need_login()
    d = request.get_json(force=True, silent=True) or {}
    try:
        qty = max(1, int(d.get("qty") or 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Qty number hona chahiye"}), 400
    conn = db()
    order, err = book_order(conn, d.get("listing_id"), qty, u["id"], "DEMO")
    conn.close()
    if err:
        return jsonify({"error": err[0]}), err[1]
    return jsonify(order_json(order)), 201


@app.get("/api/orders")
def get_orders():
    """Sirf logged-in user ke apne orders."""
    u = current_user()
    if not u:
        return need_login()
    conn = db()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC", (u["id"],)
    ).fetchall()
    conn.close()
    return jsonify([order_json(r) for r in rows])


@app.post("/api/verify")
def verify_parchi():
    u = current_user()
    if not u:
        return need_login()
    d = request.get_json(force=True, silent=True) or {}
    code = (d.get("code") or "").strip().upper()
    if not code:
        return jsonify({"ok": False})
    conn = db()
    row = conn.execute(
        "SELECT * FROM orders WHERE code = ? AND status = 'READY'", (code,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False})
    conn.execute("UPDATE orders SET status = 'COLLECTED' WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "code": code})


@app.get("/api/impact")
def impact():
    conn = db()
    row = conn.execute(
        """SELECT COALESCE(SUM(qty), 0) AS meals, COALESCE(SUM(saved), 0) AS rupees
           FROM orders WHERE status = 'COLLECTED'"""
    ).fetchone()
    conn.close()
    return jsonify({
        "meals": BASE_IMPACT["meals"] + row["meals"],
        "rupees": BASE_IMPACT["rupees"] + row["rupees"],
        "kg": BASE_IMPACT["kg"] + round(row["meals"] * 0.4),
    })


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True, "naam": "BachatKhana",
        "payment_mode": "razorpay" if rzp_client else "demo",
        "dev_mode": DEV_MODE,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("=" * 56)
    print("  BachatKhana backend v3 chalu ho gaya! \U0001F35B")
    print(f"  Browser mein kholo:  http://localhost:{port}")
    print(f"  Payment mode: {'RAZORPAY \u2705' if rzp_client else 'DEMO (keys daalo toh Razorpay chalega)'}")
    if DEV_MODE:
        print("  Dev mode ON \u2014 login OTP yahin console mein dikhega")
    print("  Band karne ke liye:  Ctrl + C")
    print("=" * 56)
    app.run(host="0.0.0.0", port=port, debug=True)
