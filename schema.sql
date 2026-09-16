CREATE TABLE IF NOT EXISTS slots (
    slot_id TEXT PRIMARY KEY,
    zone TEXT NOT NULL,
    status TEXT DEFAULT 'AVAILABLE'
);

CREATE TABLE IF NOT EXISTS parking_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_plate TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    arrival_time TEXT NOT NULL,
    exit_time TEXT,
    duration_minutes INTEGER,
    amount_payable REAL,
    payment_status TEXT DEFAULT 'PENDING',
    FOREIGN KEY(slot_id) REFERENCES slots(slot_id)
);

-- Seed Initial Slots (Zones A & B)
INSERT OR IGNORE INTO slots (slot_id, zone, status) VALUES
('A1', 'Zone A', 'AVAILABLE'), ('A2', 'Zone A', 'AVAILABLE'), ('A3', 'Zone A', 'AVAILABLE'),
('A4', 'Zone A', 'AVAILABLE'), ('A5', 'Zone A', 'AVAILABLE'), ('B1', 'Zone B', 'AVAILABLE'),
('B2', 'Zone B', 'AVAILABLE'), ('B3', 'Zone B', 'AVAILABLE'), ('B4', 'Zone B', 'AVAILABLE'),
('B5', 'Zone B', 'AVAILABLE');
