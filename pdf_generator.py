import io
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import db

def generate_attendance_pdf(date_str=None, view="log", filter_val="all"):
    """
    Generates a PDF report of attendance for the given date.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        display_date = dt.strftime("%B %d, %Y")
    except ValueError:
        display_date = date_str

    students = db.get_all_students()
    attendance_logs = db.get_attendance_logs(date_str)
    
    attendance_map = {log["reg_no"]: log for log in attendance_logs}
    
    # Filter students
    if filter_val == "present":
        students = [s for s in students if attendance_map.get(s["reg_no"]) and attendance_map[s["reg_no"]].get("status") == "PRESENT"]
    elif filter_val == "absent":
        students = [s for s in students if not (attendance_map.get(s["reg_no"]) and attendance_map[s["reg_no"]].get("status") == "PRESENT")]
    
    total_students = len(students)
    present_count = sum(1 for log in attendance_logs if log.get("status") == "PRESENT")
    absent_count = len(db.get_all_students()) - present_count
    
    buffer = io.BytesIO()
    
    # Adjust orientation based on view
    if view == "log":
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
    else:
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
    
    story = []
    styles = getSampleStyleSheet()
    
    title_text = "Local Attendance System - Full Daily Report" if view == "log" else "Local Attendance System - Student Report"
    
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=24,
        leading=28, textColor=colors.HexColor('#1E293B'), spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12,
        leading=16, textColor=colors.HexColor('#64748B'), spaceAfter=15
    )
    
    th_style = ParagraphStyle(
        'TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10,
        leading=12, textColor=colors.white, alignment=1
    )
    
    td_style = ParagraphStyle(
        'TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=9,
        leading=11, textColor=colors.HexColor('#334155'), alignment=1
    )
    
    td_bold_style = ParagraphStyle(
        'TableCellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9,
        leading=11, textColor=colors.HexColor('#0F172A'), alignment=1
    )
    
    status_present_style = ParagraphStyle(
        'StatusPresent', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9,
        leading=11, textColor=colors.HexColor('#16A34A'), alignment=1
    )
    
    status_absent_style = ParagraphStyle(
        'StatusAbsent', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9,
        leading=11, textColor=colors.HexColor('#DC2626'), alignment=1
    )
    
    status_not_attended_style = ParagraphStyle(
        'StatusNotAttended', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9,
        leading=11, textColor=colors.HexColor('#64748B'), alignment=1
    )

    story.append(Paragraph(title_text, title_style))
    story.append(Paragraph(f"Date: {display_date}", subtitle_style))
    
    orig_total = len(db.get_all_students())
    stats_data = [
        [
            Paragraph("<b>Total Registered</b>", td_style),
            Paragraph("<b>Present</b>", td_style),
            Paragraph("<b>Absent</b>", td_style),
            Paragraph("<b>Attendance Rate</b>", td_style)
        ],
        [
            Paragraph(f"<font size=14><b>{orig_total}</b></font>", td_bold_style),
            Paragraph(f"<font size=14 color='#16A34A'><b>{present_count}</b></font>", td_bold_style),
            Paragraph(f"<font size=14 color='#DC2626'><b>{absent_count}</b></font>", td_bold_style),
            Paragraph(f"<font size=14 color='#2563EB'><b>{((present_count / orig_total * 100) if orig_total > 0 else 0.0):.1f}%</b></font>", td_bold_style)
        ]
    ]
    
    stats_table = Table(stats_data, colWidths=[2*inch]*4)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    if view == "log":
        table_headers = [
            Paragraph("S.No", th_style),
            Paragraph("Name", th_style),
            Paragraph("Reg No", th_style),
            Paragraph("Department", th_style),
            Paragraph("Phone", th_style),
            Paragraph("Shift", th_style),
            Paragraph("S1 In", th_style),
            Paragraph("S1 Out", th_style),
            Paragraph("S2 In", th_style),
            Paragraph("S2 Out", th_style),
            Paragraph("Sessions", th_style),
            Paragraph("Status", th_style)
        ]
        col_widths = [25, 80, 60, 70, 65, 55, 45, 45, 45, 45, 45, 60]
    else:
        table_headers = [
            Paragraph("S.No", th_style),
            Paragraph("Name", th_style),
            Paragraph("Reg No", th_style),
            Paragraph("Department", th_style),
            Paragraph("Phone Number", th_style),
            Paragraph("Shift", th_style),
            Paragraph("Sessions", th_style),
            Paragraph("Status", th_style)
        ]
        col_widths = [25, 80, 60, 70, 75, 95, 50, 60]
        
    table_data = [table_headers]
    sorted_students = sorted(students, key=lambda s: s["reg_no"])
    
    for idx, student in enumerate(sorted_students, 1):
        reg_no = student["reg_no"]
        
        if view == "log":
            att = attendance_map.get(reg_no)
            status_text = Paragraph("Not Attended", status_not_attended_style)
            s1_in = s1_out = s2_in = s2_out = "-"
            
            if att:
                s1_in = att.get("s1_in") or "-"
                s1_out = att.get("s1_out") or "-"
                s2_in = att.get("s2_in") or "-"
                s2_out = att.get("s2_out") or "-"
                
                s1_ok = bool(att.get("s1_in") and att.get("s1_out"))
                s2_ok = bool(att.get("s2_in") and att.get("s2_out"))
                
                status_val = att.get("status", "")
                if status_val == "PRESENT":
                    status_text = Paragraph("PRESENT", status_present_style)
                elif status_val == "INCOMPLETE":
                    status_text = Paragraph("INCOMPLETE", status_absent_style)
                elif "ABSENT" in status_val:
                    status_text = Paragraph(status_val, status_absent_style)
                else:
                    status_text = Paragraph(status_val, status_not_attended_style)
            else:
                s1_ok = False
                s2_ok = False
                
            s1_color = "#16A34A" if s1_ok else "#DC2626"
            s2_color = "#16A34A" if s2_ok else "#DC2626"
            sessions_html = f"<font color='{s1_color}'>●</font>  <font color='{s2_color}'>●</font>"
            sessions_text = Paragraph(sessions_html, td_style)
                
            shift_val = student.get("email") or student.get("shift") or "Shift 1"
            row = [
                Paragraph(str(idx), td_style),
                Paragraph(student.get("name") or "-", td_bold_style),
                Paragraph(reg_no, td_bold_style),
                Paragraph(student.get("department") or "-", td_style),
                Paragraph(student.get("phone") or "-", td_style),
                Paragraph(shift_val, td_style),
                Paragraph(s1_in, td_style),
                Paragraph(s1_out, td_style),
                Paragraph(s2_in, td_style),
                Paragraph(s2_out, td_style),
                sessions_text,
                status_text
            ]
        else:
            att = attendance_map.get(reg_no)
            status_text = Paragraph("Not Attended", status_not_attended_style)
            
            if att:
                s1_ok = bool(att.get("s1_in") and att.get("s1_out"))
                s2_ok = bool(att.get("s2_in") and att.get("s2_out"))
                status_val = att.get("status", "")
                if status_val == "PRESENT":
                    status_text = Paragraph("PRESENT", status_present_style)
                elif status_val == "INCOMPLETE":
                    status_text = Paragraph("INCOMPLETE", status_absent_style)
                elif "ABSENT" in status_val:
                    status_text = Paragraph(status_val, status_absent_style)
                else:
                    status_text = Paragraph(status_val, status_not_attended_style)
            else:
                s1_ok = False
                s2_ok = False
                
            s1_color = "#16A34A" if s1_ok else "#DC2626"
            s2_color = "#16A34A" if s2_ok else "#DC2626"
            sessions_html = f"<font color='{s1_color}'>●</font>  <font color='{s2_color}'>●</font>"
            sessions_text = Paragraph(sessions_html, td_style)

            row = [
                Paragraph(str(idx), td_style),
                Paragraph(student.get("name") or "-", td_bold_style),
                Paragraph(reg_no, td_bold_style),
                Paragraph(student.get("department") or "-", td_style),
                Paragraph(student.get("phone") or "-", td_style),
                Paragraph(student.get("email") or student.get("shift") or "Shift 1", td_style),
                sessions_text,
                status_text
            ]
        table_data.append(row)
        
    attendance_table = Table(table_data, colWidths=col_widths)
    
    table_styles = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E293B')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
    ]
    
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            table_styles.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F8FAFC')))
            
    attendance_table.setStyle(TableStyle(table_styles))
    story.append(attendance_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer
