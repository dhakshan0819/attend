import os
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Header, Depends, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import time
from datetime import datetime
import db
from face_handler import FaceHandler
from pdf_generator import generate_attendance_pdf
from excel_generator import generate_attendance_excel

from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage

load_dotenv()

# Dictionary to track last scan time per user to enforce cooldown
recent_scans = {}
COOLDOWN_SECONDS = 90 # 1.5 minutes

# Initialize database
db.init_db()

# Initialize Face Handler
try:
    face_handler = FaceHandler()
except Exception as e:
    print(f"CRITICAL: Failed to initialize face models: {e}")
    face_handler = None

app = FastAPI(title="Local Attendance System API", version="1.0.0")

# CORS middleware for phone camera scanning access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def send_email_notification(email_addr: str, student_name: str, action: str, time_str: str, date_str: str):
    if not email_addr:
        return
    try:
        sender_email = os.environ.get("SENDER_EMAIL")
        sender_pass = os.environ.get("SENDER_PASSWORD")
        smtp_server = os.environ.get("SMTP_SERVER")
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
        use_ssl = os.environ.get("SMTP_USE_SSL", "False").lower() == "true"
        use_tls = os.environ.get("SMTP_USE_TLS", "True").lower() == "true"
        sender_name = os.environ.get("SENDER_NAME", "Attendance System")

        if not sender_email or not sender_pass:
            return

        msg = EmailMessage()
        action_text = action.replace("_", " ").title()
        msg['Subject'] = f"Attendance {action_text} Notification"
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = email_addr
        
        msg.set_content(f"Hello {student_name},\n\nYou have successfully logged {action_text} on {date_str} at {time_str}.\n\nThank you.")

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                server.starttls()
        
        server.login(sender_email, sender_pass)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Failed to send email to {email_addr}: {e}")

# Pydantic models for request bodies
# Pydantic models for request bodies
class RegisterRequest(BaseModel):
    reg_no: str
    images: List[str]  # List of base64 image strings
    name: Optional[str] = ""
    department: Optional[str] = ""
    phone: Optional[str] = ""
    shift: Optional[str] = "Shift 1"
    email: Optional[str] = ""
    device_id: Optional[str] = "unknown_device"
    scan_id: Optional[str] = None

class FaceAttendanceRequest(BaseModel):
    image: str
    liveness_images: Optional[List[str]] = None
    mode: str = "auto"
    confirm: bool = False
    require_confidence_60: bool = False
    device_id: Optional[str] = "unknown_device"
    scan_id: Optional[str] = None

class AdminLoginRequest(BaseModel):
    password: str

class EndSessionPasswordRequest(BaseModel):
    password: str

class ManualLogRequest(BaseModel):
    reg_no: str
    mode: str
    date: Optional[str] = None
    time: Optional[str] = None
    device_id: Optional[str] = "unknown_device"
    scan_id: Optional[str] = None

class EditLogRequest(BaseModel):
    reg_no: str
    date: str
    s1_in: Optional[str] = None
    s1_out: Optional[str] = None
    s2_in: Optional[str] = None
    s2_out: Optional[str] = None

class CooldownReleaseRequest(BaseModel):
    reg_no: str

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.get("/face-registration")
def read_face_registration():
    return FileResponse("static/face_registration.html")

@app.get("/face-attendance")
def read_face_attendance():
    return FileResponse("static/face_attendance.html")

@app.get("/api/user_info/{reg_no}")
def get_user_info(reg_no: str):
    student = db.get_student(reg_no.upper())
    if student:
        return {"status": "success", "data": student}
    return {"status": "not_found"}

@app.post("/api/register")
def register_student(req: RegisterRequest):
    if not face_handler:
        raise HTTPException(status_code=500, detail="Face recognition model is not loaded.")
        
    device_id = req.device_id or "unknown_device"
    import uuid
    scan_id = req.scan_id or f"scan_{uuid.uuid4().hex}"

    print(f"[LOG] [device_id: {device_id}] [scan_id: {scan_id}] Registering student {req.reg_no}")

    reg_no = req.reg_no.strip().upper()
    if not reg_no:
        raise HTTPException(status_code=400, detail="Registration number is required.")
        
    decoded_images = []
    embeddings = []
    for idx, img_b64 in enumerate(req.images):
        img = face_handler.decode_base64_image(img_b64)
        if img is not None:
            decoded_images.append(img)
            emb = face_handler.get_embedding(img)
            if emb is not None:
                embeddings.append(emb)
                
    if not embeddings:
        raise HTTPException(
            status_code=400, 
            detail="Could not detect a clear face in any of the captured frames. Please look directly at the camera in a well-lit area."
        )


        
    # Average and normalize embeddings
    mean_emb = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(mean_emb)
    if norm > 0:
        mean_emb = mean_emb / norm
        
    # Save to database
    shift_val = req.shift or req.email or "Shift 1"
    db.add_student(reg_no, mean_emb.tolist(), req.name, req.department, req.phone, shift_val)
    
    # Auto append to Mock_Form_Responses.csv
    try:
        csv_path = "Mock_Form_Responses.csv"
        if os.path.exists(csv_path):
            with open(csv_path, "a", encoding="utf-8") as f:
                f.write(f"\n{req.name},{reg_no},{req.department},{req.phone},{shift_val}")
    except Exception as e:
        print(f"Failed to append to CSV: {e}")
    
    # Auto check-in the registered student
    auto_check_in_status = "failed"
    try:
        db.log_attendance(reg_no, mode="check_in", device_id=device_id, scan_id=scan_id)
        auto_check_in_status = "success"
    except Exception as e:
        print(f"Failed to auto-checkin registered student {reg_no}: {e}")
        
    return {
        "status": "success",
        "message": f"Successfully registered face and checked in student {reg_no}.",
        "frames_processed": len(req.images),
        "frames_successful": len(embeddings),
        "auto_check_in": auto_check_in_status,
        "device_id": device_id,
        "scan_id": scan_id
    }

@app.post("/api/attendance/face")
def attendance_face(req: FaceAttendanceRequest, background_tasks: BackgroundTasks):
    if not face_handler:
        raise HTTPException(status_code=500, detail="Face recognition model is not loaded.")
        
    device_id = req.device_id or "unknown_device"
    import uuid
    scan_id = req.scan_id or f"scan_{uuid.uuid4().hex}"

    print(f"[LOG] [device_id: {device_id}] [scan_id: {scan_id}] Processing face attendance request (mode={req.mode}, confirm={req.confirm})")

    img = face_handler.decode_base64_image(req.image)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image data received.")


        
    # Extract embedding and aligned face image
    input_emb, aligned_face = face_handler.get_embedding(img, min_confidence=0.85, return_aligned=True)
    if input_emb is None:
        raise HTTPException(status_code=400, detail="No face detected. Please ensure your face is fully visible.")
        
    # Fetch all students from DB
    students = [s for s in db.get_all_students() if s.get("face_embedding")]
    if not students:
        raise HTTPException(status_code=400, detail="No students with faces registered in the database yet.")
        
    match_threshold = 0.60 if req.require_confidence_60 else 0.40
    matched_reg_no, score = face_handler.match_face(input_emb, students, threshold=match_threshold)
    
    if not matched_reg_no:
        raise HTTPException(
            status_code=404, 
            detail=f"Face not recognized (highest similarity: {score:.3f}, required: {match_threshold:.3f})."
        )

    print(f"[LOG] [device_id: {device_id}] [scan_id: {scan_id}] Matched student {matched_reg_no} (score: {score:.3f})")

    # Atomic log_attendance with durable cooldown, append-only scan_events, and idempotency
    try:
        log = db.log_attendance(
            matched_reg_no,
            mode=req.mode,
            confirm=req.confirm,
            device_id=device_id,
            scan_id=scan_id,
            confidence=score,
            cooldown_seconds=COOLDOWN_SECONDS
        )

        if log.get("status") == "cooldown_active":
            raise HTTPException(
                status_code=429,
                detail=log.get("message", "Cooldown active.")
            )

        if log.get("email") and log.get("action_taken"):
            current_time_str = datetime.now().strftime("%I:%M:%S %p")
            background_tasks.add_task(send_email_notification, log["email"], log.get("name", log["reg_no"]), log["action_taken"], current_time_str, log["date"])

        # Encode aligned face image to base64
        import cv2
        import base64
        _, img_buffer = cv2.imencode('.jpg', aligned_face)
        face_image_b64 = base64.b64encode(img_buffer).decode('utf-8')
        
        status_msg = f"Recognized student {matched_reg_no}"
        if log.get("status") and "already" in log["status"]:
            status_msg = f"Student {matched_reg_no} is already logged"
            
        return {
            "status": "success",
            "message": f"{status_msg} (Confidence: {score:.3f})",
            "reg_no": matched_reg_no,
            "confidence": score,
            "device_id": device_id,
            "scan_id": scan_id,
            "server_time": datetime.now().isoformat(),
            "face_image": face_image_b64,
            "data": log
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error logging attendance: {e}")

@app.get("/api/system/today")
def get_system_today():
    from datetime import datetime
    return {"date": datetime.now().strftime("%Y-%m-%d")}

@app.get("/api/attendance")
def get_attendance(date: Optional[str] = None):
    try:
        logs = db.get_attendance_logs(date)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {e}")

@app.get("/api/attendance/export")
def export_attendance(date: Optional[str] = None, view: str = "log", filter: str = "all"):
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        
    try:
        pdf_buffer = generate_attendance_pdf(date, view=view, filter_val=filter)
        filename = "log_view.pdf" if view == "log" else "report_view.pdf"
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {e}")

@app.get("/api/attendance/export/excel")
def export_attendance_excel(date: Optional[str] = None, view: str = "log", filter: str = "all"):
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        
    try:
        excel_buffer = generate_attendance_excel(date, view=view, filter_val=filter)
        filename = f"attendance_{date}_{view}.xlsx"
        return Response(
            content=excel_buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel report: {e}")

@app.get("/api/students")
def list_students():
    try:
        students = db.get_all_students()
        # Return stripped metadata (exclude raw embedding arrays for response size)
        stripped = []
        for s in students:
            has_face = bool(s.get("face_embedding"))
            stripped.append({
                "reg_no": s["reg_no"],
                "name": s["name"],
                "department": s["department"],
                "phone": s.get("phone", ""),
                "shift": s.get("email") or s.get("shift") or "Shift 1",
                "has_face": has_face,
                "created_at": s["created_at"]
            })
        return stripped
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch students: {e}")

@app.delete("/api/students/{reg_no}")
def delete_student(reg_no: str):
    reg_no = reg_no.strip().upper()
    try:
        student = db.get_student(reg_no)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found.")
        db.delete_student(reg_no)
        return {"status": "success", "message": f"Deleted student {reg_no} and their attendance history."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete student: {e}")

@app.get("/api/system/health")
def get_system_health():
    active_cooldowns = db.get_active_cooldowns()
    return {
        "status": "Online",
        "cooldown_count": len(active_cooldowns),
        "timestamp": datetime.now().isoformat()
    }

# DEVELOPER NOTICE: The admin dashboard endpoint is configured below at "/admin"
# to serve static/admin.html. To preserve security by obscurity, do not mention
# this path or include admin.html in any public documentation, readme files,
# or user guides. It must remain hidden but accessible.
@app.get("/admin")
def read_admin():
    return FileResponse("static/admin.html")

def verify_admin_token(authorization: str = Header(None)):
    if authorization != "Bearer admin_token_2026":
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest):
    if req.password == "sudo@neko":
        return {"status": "success", "token": "admin_token_2026"}
    raise HTTPException(status_code=401, detail="Invalid password")

@app.post("/api/admin/manual_log")
def admin_manual_log(req: ManualLogRequest, _: None = Depends(verify_admin_token)):
    try:
        device_id = req.device_id or "admin_console"
        import uuid
        scan_id = req.scan_id or f"scan_{uuid.uuid4().hex}"
        if req.date and req.time:
            # Edit existing or insert
            if req.mode == "check_in":
                db.edit_attendance(req.reg_no, req.date, s1_in=req.time)
            else:
                db.edit_attendance(req.reg_no, req.date, s1_out=req.time)
            return {"status": "success", "device_id": device_id, "scan_id": scan_id}
        else:
            log = db.log_attendance(req.reg_no, mode=req.mode, device_id=device_id, scan_id=scan_id)
            return {"status": "success", "data": log, "device_id": device_id, "scan_id": scan_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/session/end")
def admin_end_session(_: None = Depends(verify_admin_token)):
    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        db.end_session(today)
        return {"status": "success", "message": "Session ended. Missing check-outs marked as absent."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/session/end_with_password")
def admin_end_session_password(req: EndSessionPasswordRequest):
    if req.password != "sudo@neko":
        raise HTTPException(status_code=401, detail="Invalid password")
    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        db.end_session(today)
        return {"status": "success", "message": "Session ended. Missing check-outs marked as absent."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/session/end_s1_with_password")
def admin_end_s1_password(req: EndSessionPasswordRequest):
    if req.password != "sudo@neko":
        raise HTTPException(status_code=401, detail="Invalid password")
    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        db.end_s1_session(today)
        
        # Clear cooldowns in memory and DB
        global recent_scans
        recent_scans.clear()
        db.clear_cooldown()
        
        return {"status": "success", "message": "Session 1 (S1) ended. Subsequent check-ins will be logged for Session 2 (S2)."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/session/new_with_password")
def admin_new_session_password(req: EndSessionPasswordRequest):
    if req.password != "sudo@neko":
        raise HTTPException(status_code=401, detail="Invalid password")
    try:
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        db.reset_today_session(today)
        
        # Clear cooldowns in memory and DB
        global recent_scans
        recent_scans.clear()
        db.clear_cooldown()
        
        return {"status": "success", "message": "Started a Reset Today Session. Today's logs have been reset."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/attendance/edit")
def admin_edit_log(req: EditLogRequest, _: None = Depends(verify_admin_token)):
    try:
        db.edit_attendance(req.reg_no, req.date, req.s1_in, req.s1_out, req.s2_in, req.s2_out)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/cooldown/release")
def admin_release_cooldown(req: CooldownReleaseRequest, _: None = Depends(verify_admin_token)):
    global recent_scans
    target = req.reg_no.upper()
    if target == "ALL":
        recent_scans.clear()
        db.clear_cooldown()
        return {"status": "success", "message": "Cleared cooldown for all users."}
    else:
        recent_scans.pop(target, None)
        db.clear_cooldown(target)
        return {"status": "success", "message": f"Cleared cooldown for {req.reg_no}."}

class ClearAllCooldownsRequest(BaseModel):
    password: str

@app.get("/api/admin/cooldowns")
def admin_get_cooldowns(_: None = Depends(verify_admin_token)):
    return db.get_active_cooldowns()

@app.delete("/api/admin/cooldown/{reg_no}")
def admin_delete_single_cooldown(reg_no: str, _: None = Depends(verify_admin_token)):
    db.clear_cooldown(reg_no.strip().upper())
    return {"status": "success", "message": f"Cleared cooldown for {reg_no}."}

@app.post("/api/admin/cooldowns/clear-all")
def admin_clear_all_cooldowns(req: ClearAllCooldownsRequest, _: None = Depends(verify_admin_token)):
    if req.password != "sudo@neko":
        raise HTTPException(status_code=401, detail="Invalid root password. Action unauthorized.")
    db.clear_cooldown()
    return {"status": "success", "message": "All active cooldowns have been cleared."}

@app.get("/api/scan_events")
def get_scan_events(limit: int = 50):
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scan_events ORDER BY event_id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch scan events: {e}")
        if req.reg_no.upper() in recent_scans:
            del recent_scans[req.reg_no.upper()]
        return {"status": "success", "message": f"Cleared cooldown for {req.reg_no}."}

@app.delete("/api/admin/students/{reg_no}")
def admin_delete_student(reg_no: str, _: None = Depends(verify_admin_token)):
    return delete_student(reg_no)

@app.post("/api/admin/upload_students_csv")
async def upload_students_csv(file: UploadFile = File(...), _: None = Depends(verify_admin_token)):
    try:
        file_path = f"temp_{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        result = db.import_students_csv(file_path)
        os.remove(file_path)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload_students_csv")
async def public_upload_students_csv(file: UploadFile = File(...)):
    try:
        file_path = f"temp_{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        result = db.import_students_csv(file_path)
        os.remove(file_path)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/image", StaticFiles(directory="image"), name="image")

if __name__ == "__main__":
    import uvicorn
    import subprocess
    import socket
    
    def get_lan_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(('8.8.8.8', 80))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    lan_ip = get_lan_ip()
    port = 8000
    
    # Generate self-signed certificate if not exist
    if not os.path.exists("key.pem") or not os.path.exists("cert.pem"):
        print("Generating self-signed SSL certificates for local HTTPS...")
        try:
            subprocess.run([
                "openssl", "req", "-newkey", "rsa:2048", "-new", "-nodes", "-x509",
                "-days", "365", "-keyout", "key.pem", "-out", "cert.pem",
                "-subj", "/C=US/ST=State/L=City/O=Gatekeeper/CN=localhost"
            ], check=True)
            print("SSL Certificate generated successfully.")
        except Exception as e:
            print(f"WARNING: Could not generate SSL certificates using openssl: {e}")
            
    # Launch Uvicorn with SSL if key/cert are available
    if os.path.exists("key.pem") and os.path.exists("cert.pem"):
        print(f"\n==================================================")
        print(f"Server is running on your Local Area Network (LAN)")
        print(f"Access it via HTTPS: https://{lan_ip}:{port}")
        print(f"==================================================\n")
        uvicorn.run("main:app", host="0.0.0.0", port=port, ssl_keyfile="key.pem", ssl_certfile="cert.pem", reload=True)
    else:
        print(f"\n==================================================")
        print(f"Server is running on your Local Area Network (LAN)")
        print(f"Access it via HTTP (fallback): http://{lan_ip}:{port}")
        print(f"==================================================\n")
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
