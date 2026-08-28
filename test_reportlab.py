from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import io

buffer = io.BytesIO()
doc = SimpleDocTemplate(buffer)
styles = getSampleStyleSheet()
story = [Paragraph("Test Emoji: ✅ ❌", styles["Normal"])]
try:
    doc.build(story)
    print("SUCCESS")
except Exception as e:
    print("FAILED:", e)
