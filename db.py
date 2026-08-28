import sqlite3
import json
from datetime import datetime
import os
import csv

DB_PATH = "attendance.db"

_students_cache = None

def invalidate_students_cache():
    global _students_cache
    _students_cache = None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
    except Exception:
        pass
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        reg_no TEXT PRIMARY KEY,
        name TEXT,
        department TEXT,
        phone TEXT,
        email TEXT,
        face_embedding TEXT,  -- JSON string of list of 128 floats (nullable if pre-registered)
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create attendance table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        reg_no TEXT,
        date TEXT,           -- YYYY-MM-DD
        s1_in TEXT,          -- HH:MM:SS
        s1_out TEXT,         -- HH:MM:SS
        s2_in TEXT,          -- HH:MM:SS
        s2_out TEXT,         -- HH:MM:SS
        status TEXT,         -- PRESENT, ABSENT
        PRIMARY KEY (reg_no, date),
        FOREIGN KEY (reg_no) REFERENCES students(reg_no) ON DELETE CASCADE
    )
    """)
    
    # Create session_state table for intra-day session tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS session_state (
        date TEXT PRIMARY KEY,
        s1_ended INTEGER DEFAULT 0
    )
    """)
    
    # Create append-only scan_events table for auditing, device tracing, and idempotency
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scan_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scan_id TEXT UNIQUE,
        device_id TEXT NOT NULL,
        reg_no TEXT NOT NULL,
        action_taken TEXT,
        status TEXT NOT NULL,
        mode TEXT,
        confidence REAL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        details TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_events_scan_id ON scan_events(scan_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_events_reg_no ON scan_events(reg_no, timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scan_events_device_id ON scan_events(device_id)")

    # Create durable cooldowns table for cross-device & cross-process concurrency safety
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cooldowns (
        reg_no TEXT PRIMARY KEY,
        last_scan_time REAL NOT NULL,
        last_device_id TEXT,
        last_scan_id TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

MASTER_CSV_FILES = ["Mock_Form_Responses.csv", "uploaded_students.csv", "Students_Details.csv", "Students_Details_Final.csv.xls"]

def get_all_target_csvs():
    import glob
    candidates = set(MASTER_CSV_FILES)
    for ext in ["*.csv", "*.csv.xls", "*.xls"]:
        for f in glob.glob(ext):
            if not f.startswith("temp_"):
                candidates.add(f)
    existing = [f for f in candidates if os.path.exists(f)]
    return existing if existing else ["Mock_Form_Responses.csv"]

def sync_student_to_csv(reg_no, name="", department="", phone="", email=""):
    """
    Syncs new or updated student data into ALL local CSV files so data persists across restarts.
    """
    reg_no = reg_no.strip().upper()
    if not reg_no:
        return

    target_csvs = get_all_target_csvs()

    for csv_path in target_csvs:
        rows = []
        updated = False
        header = ["Name", "Reg No", "Department", "Phone Number", "Shift"]

        if os.path.exists(csv_path):
            try:
                with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    all_lines = list(reader)
                    if all_lines:
                        header = all_lines[0]
                        shift_idx = 4
                        reg_idx = 1
                        name_idx = 0
                        dept_idx = 2
                        phone_idx = 3

                        for i, h in enumerate(header):
                            hl = h.strip().lower()
                            if "shift" in hl or "email" in hl:
                                shift_idx = i
                            elif "reg" in hl or "roll" in hl:
                                reg_idx = i
                            elif "name" in hl:
                                name_idx = i
                            elif "dept" in hl or "year" in hl:
                                dept_idx = i
                            elif "phone" in hl or "mobile" in hl:
                                phone_idx = i

                        for line in all_lines[1:]:
                            if not line:
                                continue
                            if any(col.strip().upper() == reg_no for col in line):
                                updated_row = list(line)
                                max_needed = max(shift_idx, reg_idx, name_idx, dept_idx, phone_idx) + 1
                                while len(updated_row) < max_needed:
                                    updated_row.append("")

                                if name: updated_row[name_idx] = name
                                updated_row[reg_idx] = reg_no
                                if department: updated_row[dept_idx] = department
                                if phone: updated_row[phone_idx] = phone
                                if email: updated_row[shift_idx] = email

                                rows.append(updated_row)
                                updated = True
                            else:
                                rows.append(line)
            except Exception as e:
                print(f"[CSV Sync Error] Reading {csv_path}: {e}")

        if not updated:
            rows.append([name, reg_no, department, phone, email])

        try:
            with open(csv_path, mode='w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
            print(f"[CSV Sync] Successfully saved {reg_no} in {csv_path}")
        except Exception as e:
            print(f"[CSV Sync Error] Writing to {csv_path}: {e}")

def sync_all_db_students_to_csv():
    """
    Syncs all existing students in SQLite database to all local CSV files.
    """
    students = get_all_students()
    for s in students:
        sync_student_to_csv(
            reg_no=s["reg_no"],
            name=s.get("name", ""),
            department=s.get("department", ""),
            phone=s.get("phone", ""),
            email=s.get("email", "")
        )

def add_student(reg_no, embedding, name="", department="", phone="", email=""):
    """
    Saves or updates a student in the database and syncs with the local CSV file.
    embedding: list of 128 floats
    """
    reg_no = reg_no.strip().upper()
    conn = get_db_connection()
    cursor = conn.cursor()
    embedding_json = json.dumps(list(embedding)) if embedding else None
    
    cursor.execute(
        """INSERT INTO students (reg_no, name, department, phone, email, face_embedding) 
           VALUES (?, ?, ?, ?, ?, ?) 
           ON CONFLICT(reg_no) DO UPDATE SET 
           face_embedding=CASE WHEN excluded.face_embedding IS NOT NULL THEN excluded.face_embedding ELSE students.face_embedding END,
           name=CASE WHEN excluded.name != '' THEN excluded.name ELSE name END,
           department=CASE WHEN excluded.department != '' THEN excluded.department ELSE department END,
           phone=CASE WHEN excluded.phone != '' THEN excluded.phone ELSE phone END,
           email=CASE WHEN excluded.email != '' THEN excluded.email ELSE email END""",
        (reg_no, name, department, phone, email, embedding_json)
    )
    conn.commit()
    conn.close()
    invalidate_students_cache()

    # Sync with master CSV files
    sync_student_to_csv(reg_no, name, department, phone, email)

def get_student(reg_no):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE reg_no = ?", (reg_no,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "reg_no": row["reg_no"],
            "name": row["name"],
            "department": row["department"],
            "phone": row["phone"],
            "email": row["email"],
            "face_embedding": json.loads(row["face_embedding"]) if row["face_embedding"] else None,
            "created_at": row["created_at"]
        }
    return None

def delete_student(reg_no):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM students WHERE reg_no = ?", (reg_no,))
    conn.commit()
    conn.close()
    invalidate_students_cache()

def get_all_students(use_cache=True):
    global _students_cache
    if use_cache and _students_cache is not None:
        return _students_cache

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students")
    rows = cursor.fetchall()
    conn.close()
    
    students = []
    for row in rows:
        students.append({
            "reg_no": row["reg_no"],
            "name": row["name"],
            "department": row["department"],
            "phone": row["phone"],
            "email": row["email"],
            "face_embedding": json.loads(row["face_embedding"]) if row["face_embedding"] else None,
            "created_at": row["created_at"]
        })
    if use_cache:
        _students_cache = students
    return students

def is_s1_ended(date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT s1_ended FROM session_state WHERE date = ?", (date,))
    row = cursor.fetchone()
    conn.close()
    return bool(row["s1_ended"]) if row else False

def end_s1_session(date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO session_state (date, s1_ended)
        VALUES (?, 1)
        ON CONFLICT(date) DO UPDATE SET s1_ended = 1
    """, (date,))
    
    # Mark students who checked into S1 but did NOT check out as 'SKIPPED'
    cursor.execute("""
        UPDATE attendance
        SET s1_out = 'SKIPPED'
        WHERE date = ? AND s1_in IS NOT NULL AND (s1_out IS NULL OR s1_out = '')
    """, (date,))
    
    conn.commit()
    conn.close()

def clear_cooldown(reg_no=None):
    """
    Clears cooldown for a specific student or all students.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if reg_no:
        cursor.execute("DELETE FROM cooldowns WHERE reg_no = ?", (reg_no.strip().upper(),))
    else:
        cursor.execute("DELETE FROM cooldowns")
    conn.commit()
    conn.close()

def get_active_cooldowns(cooldown_seconds=90):
    """
    Returns list of students currently in active cooldown with remaining seconds.
    """
    import time
    now_ts = time.time()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.reg_no, c.last_scan_time, c.last_device_id, c.updated_at,
               s.name, s.department
        FROM cooldowns c
        LEFT JOIN students s ON TRIM(UPPER(c.reg_no)) = TRIM(UPPER(s.reg_no))
    """)
    rows = cursor.fetchall()
    conn.close()

    active = []
    for r in rows:
        elapsed = now_ts - r["last_scan_time"]
        if elapsed < cooldown_seconds:
            rem = int(cooldown_seconds - elapsed)
            active.append({
                "reg_no": r["reg_no"],
                "name": r["name"] or r["reg_no"],
                "department": r["department"] or "-",
                "last_scan_time": r["last_scan_time"],
                "cooldown_remaining": rem,
                "device_id": r["last_device_id"],
                "updated_at": r["updated_at"]
            })
    active.sort(key=lambda x: x["cooldown_remaining"], reverse=True)
    return active

def log_attendance(reg_no, mode=None, confirm=False, device_id="unknown_device", scan_id=None, confidence=None, cooldown_seconds=90):
    """
    Logs attendance for the student atomically with idempotency, durable cooldowns, and append-only event tracing.
    """
    import uuid
    import time
    scan_id = scan_id or f"scan_{uuid.uuid4().hex}"
    device_id = device_id or "unknown_device"

    now = datetime.now()
    today_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    now_ts = time.time()

    conn = get_db_connection()
    # Execute IMMEDIATE transaction to serialize concurrent updates
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()

    try:
        # 1. Idempotency Check: return previously committed result if scan_id exists
        cursor.execute("SELECT details FROM scan_events WHERE scan_id = ?", (scan_id,))
        existing_event = cursor.fetchone()
        if existing_event:
            conn.commit()
            conn.close()
            return json.loads(existing_event["details"])

        # 2. Check if student exists
        cursor.execute("SELECT reg_no, name, email, department FROM students WHERE reg_no = ?", (reg_no,))
        student_row = cursor.fetchone()
        if not student_row:
            conn.commit()
            conn.close()
            raise ValueError(f"Student with registration number {reg_no} is not registered.")

        student_email = student_row["email"]
        student_name = student_row["name"] or reg_no
        student_dept = student_row["department"] or "-"

        # 3. Durable Cooldown Check across all devices
        cursor.execute("SELECT last_scan_time FROM cooldowns WHERE reg_no = ?", (reg_no,))
        cooldown_row = cursor.fetchone()
        if cooldown_row and not confirm:
            elapsed = now_ts - cooldown_row["last_scan_time"]
            if elapsed < cooldown_seconds:
                cooldown_remaining = int(cooldown_seconds - elapsed)
                cooldown_payload = {
                    "reg_no": reg_no,
                    "name": student_name,
                    "email": student_email,
                    "shift": student_email or "Shift 1",
                    "department": student_dept,
                    "date": today_date,
                    "status": "cooldown_active",
                    "action_taken": None,
                    "device_id": device_id,
                    "scan_id": scan_id,
                    "cooldown_remaining": cooldown_remaining,
                    "message": f"Cooldown active: Please wait {cooldown_remaining // 60}m {cooldown_remaining % 60}s.",
                    "committed_at": datetime.now().isoformat()
                }
                cursor.execute(
                    """INSERT INTO scan_events (scan_id, device_id, reg_no, action_taken, status, mode, confidence, details)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (scan_id, device_id, reg_no, None, "cooldown_active", mode, confidence, json.dumps(cooldown_payload))
                )
                conn.commit()
                conn.close()
                return cooldown_payload

        # 4. Fetch attendance record for today
        cursor.execute("SELECT * FROM attendance WHERE reg_no = ? AND date = ?", (reg_no, today_date))
        record = cursor.fetchone()

        status = ""
        action_taken = ""

        if record and record["status"] in ["ABSENT", "ABSENT | BUNKED"]:
            payload = {
                "reg_no": reg_no,
                "name": student_name,
                "email": student_email,
                "shift": student_email or "Shift 1",
                "department": student_dept,
                "date": today_date,
                "status": "session_ended",
                "action_taken": None,
                "device_id": device_id,
                "scan_id": scan_id,
                "s1_in": record["s1_in"],
                "s1_out": record["s1_out"],
                "s2_in": record["s2_in"],
                "s2_out": record["s2_out"],
                "missed_previous": False,
                "committed_at": datetime.now().isoformat()
            }
            cursor.execute(
                """INSERT INTO scan_events (scan_id, device_id, reg_no, action_taken, status, mode, confidence, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (scan_id, device_id, reg_no, None, "session_ended", mode, confidence, json.dumps(payload))
            )
            conn.commit()
            conn.close()
            return payload

        s1_ended = is_s1_ended(today_date)
        skipped_s1_out = bool(record and record["s1_out"] == "SKIPPED")

        if skipped_s1_out and not confirm:
            payload = {
                "reg_no": reg_no,
                "name": student_name,
                "status": "needs_confirmation",
                "message": "Previous session check-out was skipped. Force check-in?",
                "action_taken": None,
                "device_id": device_id,
                "scan_id": scan_id,
                "committed_at": datetime.now().isoformat()
            }
            cursor.execute(
                """INSERT INTO scan_events (scan_id, device_id, reg_no, action_taken, status, mode, confidence, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (scan_id, device_id, reg_no, None, "needs_confirmation", mode, confidence, json.dumps(payload))
            )
            conn.commit()
            conn.close()
            return payload

        if not record:
            if not s1_ended:
                if mode == "check_out":
                    cursor.execute("INSERT INTO attendance (reg_no, date, s1_out) VALUES (?, ?, ?)", (reg_no, today_date, current_time))
                    action_taken = "s1_out"
                    status = "check_out"
                else:
                    cursor.execute("INSERT INTO attendance (reg_no, date, s1_in) VALUES (?, ?, ?)", (reg_no, today_date, current_time))
                    action_taken = "s1_in"
                    status = "check_in"
            else:
                if mode == "check_out":
                    cursor.execute("INSERT INTO attendance (reg_no, date, s2_out) VALUES (?, ?, ?)", (reg_no, today_date, current_time))
                    action_taken = "s2_out"
                    status = "check_out"
                else:
                    cursor.execute("INSERT INTO attendance (reg_no, date, s2_in) VALUES (?, ?, ?)", (reg_no, today_date, current_time))
                    action_taken = "s2_in"
                    status = "check_in"
        else:
            s1_in = record["s1_in"]
            s1_out = record["s1_out"]
            s2_in = record["s2_in"]
            s2_out = record["s2_out"]

            if s1_out == "SKIPPED" and confirm:
                cursor.execute(
                    "UPDATE attendance SET s1_out = ?, s2_in = ? WHERE reg_no = ? AND date = ?",
                    (current_time, current_time, reg_no, today_date)
                )
                action_taken = "s2_in"
                status = "check_in"
            elif not s1_ended:
                if mode == "check_in":
                    if not s1_in:
                        cursor.execute("UPDATE attendance SET s1_in = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s1_in"
                        status = "check_in"
                    else:
                        status = "already_checked_in"
                elif mode == "check_out":
                    if not s1_out or s1_out == 'SKIPPED':
                        cursor.execute("UPDATE attendance SET s1_out = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s1_out"
                        status = "check_out"
                    else:
                        status = "already_checked_out"
                else:
                    if not s1_in:
                        cursor.execute("UPDATE attendance SET s1_in = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s1_in"
                        status = "check_in"
                    elif not s1_out or s1_out == 'SKIPPED':
                        cursor.execute("UPDATE attendance SET s1_out = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s1_out"
                        status = "check_out"
                    else:
                        status = "already_checked_out"
            else:
                if mode == "check_in":
                    if not s2_in:
                        cursor.execute("UPDATE attendance SET s2_in = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s2_in"
                        status = "check_in"
                    else:
                        status = "already_checked_in"
                elif mode == "check_out":
                    if not s2_out:
                        cursor.execute("UPDATE attendance SET s2_out = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s2_out"
                        status = "check_out"
                    else:
                        status = "already_checked_out"
                else:
                    if not s2_in:
                        cursor.execute("UPDATE attendance SET s2_in = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s2_in"
                        status = "check_in"
                    elif not s2_out:
                        cursor.execute("UPDATE attendance SET s2_out = ? WHERE reg_no = ? AND date = ?", (current_time, reg_no, today_date))
                        action_taken = "s2_out"
                        status = "check_out"
                    else:
                        status = "already_completed"

        # Re-evaluate final status
        cursor.execute("SELECT * FROM attendance WHERE reg_no = ? AND date = ?", (reg_no, today_date))
        updated_record = cursor.fetchone()

        if updated_record:
            if (updated_record["s1_in"] and updated_record["s1_out"] and updated_record["s1_out"] != 'SKIPPED' and 
                updated_record["s2_in"] and updated_record["s2_out"]):
                cursor.execute("UPDATE attendance SET status = 'PRESENT' WHERE reg_no = ? AND date = ?", (reg_no, today_date))
            else:
                cursor.execute("UPDATE attendance SET status = 'INCOMPLETE' WHERE reg_no = ? AND date = ?", (reg_no, today_date))

        # Update durable cooldown table only if an action was actually taken
        if action_taken:
            cursor.execute("""
                INSERT INTO cooldowns (reg_no, last_scan_time, last_device_id, last_scan_id, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(reg_no) DO UPDATE SET
                last_scan_time = excluded.last_scan_time,
                last_device_id = excluded.last_device_id,
                last_scan_id = excluded.last_scan_id,
                updated_at = CURRENT_TIMESTAMP
            """, (reg_no, now_ts, device_id, scan_id))

        result_payload = {
            "reg_no": reg_no,
            "name": student_name,
            "email": student_email,
            "shift": student_email or "Shift 1",
            "department": student_dept,
            "date": today_date,
            "status": status,
            "action_taken": action_taken,
            "device_id": device_id,
            "scan_id": scan_id,
            "committed_at": datetime.now().isoformat(),
            "s1_in": updated_record["s1_in"] if updated_record else None,
            "s1_out": updated_record["s1_out"] if updated_record else None,
            "s2_in": updated_record["s2_in"] if updated_record else None,
            "s2_out": updated_record["s2_out"] if updated_record else None,
            "missed_previous": False
        }

        # Append to scan_events table
        cursor.execute(
            """INSERT INTO scan_events (scan_id, device_id, reg_no, action_taken, status, mode, confidence, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, device_id, reg_no, action_taken, status, mode, confidence, json.dumps(result_payload))
        )

        conn.commit()
        conn.close()
        return result_payload
    except Exception as e:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        raise e

def get_attendance_logs(date=None):
    """
    Fetches all attendance logs for a specific date (defaults to today).
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT a.reg_no, a.date, a.s1_in, a.s1_out, a.s2_in, a.s2_out, a.status, 
               s.name, s.department, s.phone, s.email
        FROM attendance a
        LEFT JOIN students s ON TRIM(UPPER(a.reg_no)) = TRIM(UPPER(s.reg_no))
        WHERE a.date = ?
        ORDER BY a.reg_no ASC
    """, (date,))
    
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        logs.append({
            "reg_no": row["reg_no"],
            "name": row["name"],
            "department": row["department"],
            "phone": row["phone"],
            "email": row["email"],
            "date": row["date"],
            "s1_in": row["s1_in"],
            "s1_out": row["s1_out"],
            "s2_in": row["s2_in"],
            "s2_out": row["s2_out"],
            "status": row["status"]
        })
    return logs

def edit_attendance(reg_no, date, s1_in=None, s1_out=None, s2_in=None, s2_out=None):
    """
    Manually edits or inserts an attendance log.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if student exists
    cursor.execute("SELECT reg_no FROM students WHERE reg_no = ?", (reg_no,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError(f"Student with registration number {reg_no} is not registered.")
        
    cursor.execute("SELECT * FROM attendance WHERE reg_no = ? AND date = ?", (reg_no, date))
    record = cursor.fetchone()
    
    if not record:
        cursor.execute(
            "INSERT INTO attendance (reg_no, date, s1_in, s1_out, s2_in, s2_out) VALUES (?, ?, ?, ?, ?, ?)",
            (reg_no, date, s1_in, s1_out, s2_in, s2_out)
        )
    else:
        cursor.execute(
            """UPDATE attendance SET 
               s1_in = COALESCE(?, s1_in), 
               s1_out = COALESCE(?, s1_out), 
               s2_in = COALESCE(?, s2_in), 
               s2_out = COALESCE(?, s2_out) 
               WHERE reg_no = ? AND date = ?""",
            (s1_in, s1_out, s2_in, s2_out, reg_no, date)
        )
        
    # Re-evaluate status
    cursor.execute("SELECT * FROM attendance WHERE reg_no = ? AND date = ?", (reg_no, date))
    rec = cursor.fetchone()
    if rec:
        if rec["s1_in"] and rec["s1_out"] and rec["s2_in"] and rec["s2_out"]:
            cursor.execute("UPDATE attendance SET status = 'PRESENT' WHERE reg_no = ? AND date = ?", (reg_no, date))
        else:
            cursor.execute("UPDATE attendance SET status = 'INCOMPLETE' WHERE reg_no = ? AND date = ?", (reg_no, date))

    conn.commit()
    conn.close()

def end_session(date):
    """
    Marks any user without all 4 scans as 'ABSENT' for the given date.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Mark users who have some scans but are incomplete or skipped
    cursor.execute(
        """UPDATE attendance 
           SET status = 'ABSENT | BUNKED' 
           WHERE date = ? AND (s1_in IS NULL OR s1_out IS NULL OR s1_out = 'SKIPPED' OR s2_in IS NULL OR s2_out IS NULL)""",
        (date,)
    )
    
    # Mark users with 0 scans as ABSENT by inserting them
    cursor.execute("SELECT reg_no FROM students")
    students = cursor.fetchall()
    for student in students:
        reg_no = student["reg_no"]
        cursor.execute("SELECT 1 FROM attendance WHERE reg_no = ? AND date = ?", (reg_no, date))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO attendance (reg_no, date, status) VALUES (?, ?, 'ABSENT')",
                (reg_no, date)
            )
            
    conn.commit()
    conn.close()

def reset_today_session(date):
    """
    Deletes all attendance records and session state for the given date, resetting everything.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE date = ?", (date,))
    cursor.execute("DELETE FROM session_state WHERE date = ?", (date,))
    conn.commit()
    conn.close()

def import_students_csv(csv_path):
    """
    Reads a CSV file and inserts/updates the students table.
    Expected columns: Reg No, Name, Department, Phone Number, Email
    """
    if not os.path.exists(csv_path):
        return {"error": "File not found"}
        
    count = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    
    with open(csv_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Normalize column names for safe access
        headers = [h.strip().lower() for h in reader.fieldnames]
        
        for row in reader:
            row_dict = {h.strip().lower(): v.strip() for h, v in row.items()}
            
            # Find the required fields, be flexible with exact names
            reg_no = (row_dict.get('reg no') or 
                      row_dict.get('reg_no') or 
                      row_dict.get('regno') or 
                      row_dict.get('register number') or 
                      row_dict.get('register_number') or 
                      row_dict.get('registration number') or 
                      row_dict.get('registration_number') or '')
            if not reg_no:
                continue
                
            name = row_dict.get('name', '')
            dept = (row_dict.get('department') or 
                    row_dict.get('dept') or 
                    row_dict.get('year and department') or 
                    row_dict.get('year & department') or 
                    row_dict.get('year_and_department') or 
                    row_dict.get('branch') or 
                    row_dict.get('course') or '')
            phone = row_dict.get('phone number', row_dict.get('phone', row_dict.get('contact', '')))
            email = (row_dict.get('shift') or
                     row_dict.get('email') or 
                     row_dict.get('mail') or 
                     row_dict.get('mail id') or 
                     row_dict.get('mail_id') or 
                     row_dict.get('email address') or 
                     row_dict.get('email_address') or '')
            
            cursor.execute(
                """INSERT INTO students (reg_no, name, department, phone, email) 
                   VALUES (?, ?, ?, ?, ?) 
                   ON CONFLICT(reg_no) DO UPDATE SET 
                   name=CASE WHEN excluded.name != '' THEN excluded.name ELSE students.name END,
                   department=CASE WHEN excluded.department != '' THEN excluded.department ELSE students.department END,
                   phone=CASE WHEN excluded.phone != '' THEN excluded.phone ELSE students.phone END,
                   email=CASE WHEN excluded.email != '' THEN excluded.email ELSE students.email END""",
                (reg_no.upper(), name, dept, phone, email)
            )
            sync_student_to_csv(reg_no, name, dept, phone, email)
            count += 1
            
    conn.commit()
    conn.close()
    invalidate_students_cache()
    return {"imported": count}
