import io
import pandas as pd
from datetime import datetime
import db

def generate_attendance_excel(date_str=None, view="log", filter_val="all"):
    """
    Generates an Excel report (.xlsx) of attendance for the given date.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    students = db.get_all_students()
    attendance_logs = db.get_attendance_logs(date_str)
    
    attendance_map = {log["reg_no"]: log for log in attendance_logs}
    
    # Filter students
    if filter_val == "present":
        students = [s for s in students if attendance_map.get(s["reg_no"]) and attendance_map[s["reg_no"]].get("status") == "PRESENT"]
    elif filter_val == "absent":
        students = [s for s in students if not (attendance_map.get(s["reg_no"]) and attendance_map[s["reg_no"]].get("status") == "PRESENT")]
    
    sorted_students = sorted(students, key=lambda s: s["reg_no"])
    
    rows = []
    for idx, student in enumerate(sorted_students, 1):
        reg_no = student["reg_no"]
        att = attendance_map.get(reg_no)
        
        status = att.get("status") if att else "NOT ATTENDED"
        s1_in = (att.get("s1_in") or "-") if att else "-"
        s1_out = (att.get("s1_out") or "-") if att else "-"
        s2_in = (att.get("s2_in") or "-") if att else "-"
        s2_out = (att.get("s2_out") or "-") if att else "-"
        if view == "log":
            rows.append({
                "S.No": idx,
                "Reg No": reg_no,
                "Name": student.get("name") or "-",
                "Department": student.get("department") or "-",
                "Phone": student.get("phone") or "-",
                "Shift": student.get("email") or student.get("shift") or "Shift 1",
                "S1 In": s1_in,
                "S1 Out": s1_out,
                "S2 In": s2_in,
                "S2 Out": s2_out,
                "Status": status
            })
        else:
            rows.append({
                "S.No": idx,
                "Reg No": reg_no,
                "Name": student.get("name") or "-",
                "Department": student.get("department") or "-",
                "Phone": student.get("phone") or "-",
                "Shift": student.get("email") or student.get("shift") or "Shift 1",
                "Status": status
            })
            
    df = pd.DataFrame(rows)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        sheet_name = "Attendance Log" if view == "log" else "Attendance Summary"
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        # Auto-adjust column width for clean display
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 4, 12)
            
    output.seek(0)
    return output
