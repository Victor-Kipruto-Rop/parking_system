from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table: slots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slots (
            slot_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'AVAILABLE'
        )
    ''')
    
    # Table: parking_sessions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parking_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_plate TEXT NOT NULL,
            slot_id TEXT NOT NULL,
            arrival_time TEXT NOT NULL,
            exit_time TEXT,
            duration_minutes INTEGER,
            amount_payable REAL,
            payment_status TEXT DEFAULT 'PENDING'
        )
    ''')
    
    # Seed 10 slots if empty
    cursor.execute('SELECT COUNT(*) FROM slots')
    if cursor.fetchone()[0] == 0:
        for i in range(1, 11):
            cursor.execute('INSERT INTO slots (slot_id, status) VALUES (?, ?)', (f'SLOT-{i:02d}', 'AVAILABLE'))
            
    conn.commit()
    conn.close()

def calculate_fee(duration_minutes):
    """Calculates fee according to client specifications."""
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/slots', methods=['GET'])
def get_slots():
    conn = get_db_connection()
    slots = conn.execute('SELECT * FROM slots').fetchall()
    conn.close()
    return jsonify([dict(slot) for slot in slots])

@app.route('/api/entry', methods=['POST'])
def vehicle_entry():
    data = request.json
    license_plate = data.get('license_plate', '').strip().upper()
    
    if not license_plate:
        return jsonify({'error': 'License plate is required'}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find first available slot
    slot = cursor.execute("SELECT slot_id FROM slots WHERE status = 'AVAILABLE' LIMIT 1").fetchone()
    if not slot:
        conn.close()
        return jsonify({'error': 'Parking Lot Full!'}), 400
        
    slot_id = slot['slot_id']
    arrival_time = datetime.now().isoformat()
    
    # Create active session and set slot to OCCUPIED
    cursor.execute('''
        INSERT INTO parking_sessions (license_plate, slot_id, arrival_time, payment_status)
        VALUES (?, ?, ?, 'PENDING')
    ''', (license_plate, slot_id, arrival_time))
    
    cursor.execute("UPDATE slots SET status = 'OCCUPIED' WHERE slot_id = ?", (slot_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': f'Vehicle {license_plate} parked successfully at {slot_id}. Barrier Raised.',
        'slot_id': slot_id
    })

@app.route('/api/exit-preview', methods=['POST'])
def exit_preview():
    data = request.json
    license_plate = data.get('license_plate', '').strip().upper()
    
    conn = get_db_connection()
    session = conn.execute('''
        SELECT * FROM parking_sessions 
        WHERE license_plate = ? AND exit_time IS NULL 
        ORDER BY session_id DESC LIMIT 1
    ''', (license_plate,)).fetchone()
    conn.close()
    
    if not session:
        return jsonify({'error': 'Active session not found for this vehicle'}), 444
        
    arrival_time = datetime.fromisoformat(session['arrival_time'])
    now = datetime.now()
    duration_minutes = max(1, int((now - arrival_time).total_seconds() / 60))
    fee = calculate_fee(duration_minutes)
    
    return jsonify({
        'session_id': session['session_id'],
        'license_plate': license_plate,
        'slot_id': session['slot_id'],
        'duration_minutes': duration_minutes,
        'amount_payable': fee
    })

@app.route('/api/pay-and-exit', methods=['POST'])
def pay_and_exit():
    data = request.json
    session_id = data.get('session_id')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    session = cursor.execute('SELECT * FROM parking_sessions WHERE session_id = ?', (session_id,)).fetchone()
    if not session:
        conn.close()
        return jsonify({'error': 'Session not found'}), 404
        
    arrival_time = datetime.fromisoformat(session['arrival_time'])
    now = datetime.now()
    duration_minutes = max(1, int((now - arrival_time).total_seconds() / 60))
    fee = calculate_fee(duration_minutes)
    
    # Finalize session and free slot
    cursor.execute('''
        UPDATE parking_sessions 
        SET exit_time = ?, duration_minutes = ?, amount_payable = ?, payment_status = 'COMPLETED'
        WHERE session_id = ?
    ''', (now.isoformat(), duration_minutes, fee, session_id))
    
    cursor.execute("UPDATE slots SET status = 'AVAILABLE' WHERE slot_id = ?", (session['slot_id'],))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'message': f'Payment of Kshs. {fee} received. Barrier raised for vehicle exit.',
        'fee': fee
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
