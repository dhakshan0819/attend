import db
import sqlite3
from datetime import datetime, timedelta

def add_absence():
    conn = db.get_db_connection()
    cursor = conn.cursor()
    
    # Get yesterday's date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    cursor.execute("SELECT reg_no FROM students")
    students = cursor.fetchall()
    
    for student in students:
        reg_no = student["reg_no"]
        # Delete if already exists for yesterday
        cursor.execute("DELETE FROM attendance WHERE reg_no = ? AND date = ?", (reg_no, yesterday))
        # Insert absent record
        cursor.execute(
            "INSERT INTO attendance (reg_no, date, status) VALUES (?, ?, 'ABSENT')",
            (reg_no, yesterday)
        )
        
    conn.commit()
    conn.close()
    print(f"Successfully added 'ABSENT' records for {len(students)} students for yesterday ({yesterday}).")

if __name__ == "__main__":
    add_absence()
