import sqlite3
from datetime import datetime
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
DB_NAME = "database.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with open("schema.sql", "r") as f:
        schema = f.read()
    conn = get_db()
    conn.executescript(schema)
    conn.close()


def calculate_fee(duration_minutes):
    """Calculates fee strictly based on client tier structure."""
    if duration_minutes <= 30:
        return 0.0
    elif duration_minutes <= 120:
        return 50.0
    elif duration_minutes <= 240:
        return 100.0
    elif duration_minutes <= 360:
        return 300.0
    else:
        return 500.0


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/slots", methods=["GET"])
def get_slots():
    conn = get_db()
    slots = conn.execute(
        "SELECT * FROM slots ORDER BY slot_id ASC"
    ).fetchall()
    conn.close()
    return jsonify([dict(slot) for slot in slots])


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    conn = get_db()
    total_slots = conn.execute("SELECT COUNT(*) FROM slots").fetchone()[0]
    occupied_slots = conn.execute(
        "SELECT COUNT(*) FROM slots WHERE status = 'OCCUPIED'"
    ).fetchone()[0]
    available_slots = total_slots - occupied_slots

    today_revenue = (
        conn.execute(
            """
        SELECT SUM(amount_payable) FROM parking_sessions 
        WHERE payment_status = 'COMPLETED' AND date(exit_time) = date('now')
    """
        ).fetchone()[0]
        or 0.0
    )

    conn.close()
    return jsonify(
        {
            "total_slots": total_slots,
            "occupied_slots": occupied_slots,
            "available_slots": available_slots,
            "today_revenue": today_revenue,
        }
    )


@app.route("/api/sessions/active", methods=["GET"])
def get_active_sessions():
    conn = get_db()
    sessions = conn.execute(
        """
        SELECT session_id, license_plate, slot_id, arrival_time 
        FROM parking_sessions 
        WHERE exit_time IS NULL 
        ORDER BY session_id DESC
    """
    ).fetchall()
    conn.close()
    return jsonify([dict(s) for s in sessions])


@app.route("/api/entry", methods=["POST"])
def vehicle_entry():
    data = request.json or {}
    license_plate = data.get("license_plate", "").strip().upper()

    if not license_plate:
        return jsonify({"error": "License plate number is required"}), 400

    conn = get_db()
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT session_id FROM parking_sessions WHERE license_plate = ? AND exit_time IS NULL",
        (license_plate,),
    ).fetchone()
    if existing:
        conn.close()
        return (
            jsonify(
                {
                    "error": f"Vehicle {license_plate} is already inside the facility."
                }
            ),
            400,
        )

    slot = cursor.execute(
        "SELECT slot_id FROM slots WHERE status = 'AVAILABLE' ORDER BY slot_id ASC LIMIT 1"
    ).fetchone()

    if not slot:
        conn.close()
        return (
            jsonify({"error": "Parking facility is currently at full capacity!"}),
            400,
        )

    slot_id = slot["slot_id"]
    arrival_time = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO parking_sessions (license_plate, slot_id, arrival_time, payment_status)
        VALUES (?, ?, ?, 'PENDING')
    """,
        (license_plate, slot_id, arrival_time),
    )

    cursor.execute(
        "UPDATE slots SET status = 'OCCUPIED' WHERE slot_id = ?", (slot_id,)
    )
    conn.commit()
    conn.close()

    return jsonify(
        {
            "message": f"Entry granted. Slot {slot_id} assigned.",
            "slot_id": slot_id,
            "license_plate": license_plate,
        }
    )


@app.route("/api/exit-preview", methods=["POST"])
def exit_preview():
    data = request.json or {}
    license_plate = data.get("license_plate", "").strip().upper()

    conn = get_db()
    session = conn.execute(
        """
        SELECT * FROM parking_sessions 
        WHERE license_plate = ? AND exit_time IS NULL 
        ORDER BY session_id DESC LIMIT 1
    """,
        (license_plate,),
    ).fetchone()
    conn.close()

    if not session:
        return (
            jsonify(
                {
                    "error": f"No active parking session found for plate: {license_plate}"
                }
            ),
            404,
        )

    arrival = datetime.fromisoformat(session["arrival_time"])
    now = datetime.now()
    duration = max(1, int((now - arrival).total_seconds() / 60))
    fee = calculate_fee(duration)

    return jsonify(
        {
            "session_id": session["session_id"],
            "license_plate": license_plate,
            "slot_id": session["slot_id"],
            "arrival_time": arrival.strftime("%H:%M:%S (%d %b)"),
            "duration_minutes": duration,
            "amount_payable": fee,
        }
    )


@app.route("/api/pay-and-exit", methods=["POST"])
def pay_and_exit():
    data = request.json or {}
    session_id = data.get("session_id")

    conn = get_db()
    cursor = conn.cursor()

    session = cursor.execute(
        "SELECT * FROM parking_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not session or session["exit_time"] is not None:
        conn.close()
        return jsonify({"error": "Invalid or already completed session."}), 400

    arrival = datetime.fromisoformat(session["arrival_time"])
    now = datetime.now()
    duration = max(1, int((now - arrival).total_seconds() / 60))
    fee = calculate_fee(duration)

    cursor.execute(
        """
        UPDATE parking_sessions 
        SET exit_time = ?, duration_minutes = ?, amount_payable = ?, payment_status = 'COMPLETED'
        WHERE session_id = ?
    """,
        (now.isoformat(), duration, fee, session_id),
    )

    cursor.execute(
        "UPDATE slots SET status = 'AVAILABLE' WHERE slot_id = ?",
        (session["slot_id"],),
    )
    conn.commit()
    conn.close()

    return jsonify(
        {
            "message": f"Payment of Kshs. {fee:,.2f} confirmed. Exit barrier opened.",
            "fee": fee,
            "slot_id": session["slot_id"],
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
