from pathlib import Path
from xml.sax.saxutils import escape
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Preformatted
)

source = Path("docs/design_document.md")
target = Path("docs/design_document.pdf")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="DocTitle", parent=styles["Title"],
    fontSize=19, leading=24, alignment=TA_CENTER,
    textColor=colors.HexColor("#17365D"), spaceAfter=16
))
styles.add(ParagraphStyle(
    name="H1Custom", parent=styles["Heading1"],
    fontSize=15, leading=19, textColor=colors.HexColor("#17365D"),
    spaceBefore=14, spaceAfter=8
))
styles.add(ParagraphStyle(
    name="H2Custom", parent=styles["Heading2"],
    fontSize=11, leading=14, textColor=colors.HexColor("#24527A"),
    spaceBefore=10, spaceAfter=5
))
styles.add(ParagraphStyle(
    name="BodyCustom", parent=styles["BodyText"],
    fontSize=9, leading=13, spaceAfter=6
))
styles.add(ParagraphStyle(
    name="TableLine", parent=styles["Code"],
    fontSize=7, leading=9, spaceAfter=2
))

def safe(text):
    text = text.encode("cp1252", errors="replace").decode("cp1252")
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
    return text

story = []
lines = source.read_text(encoding="utf-8-sig").splitlines()
paragraph = []
in_code = False
code_lines = []

def flush_paragraph():
    if paragraph:
        story.append(Paragraph(safe(" ".join(paragraph)), styles["BodyCustom"]))
        paragraph.clear()

for line in lines:
    stripped = line.strip()

    if stripped.startswith("```"):
        flush_paragraph()
        if in_code:
            story.append(Preformatted(
                "\n".join(code_lines), styles["Code"],
                maxLineLength=95
            ))
            story.append(Spacer(1, 6))
            code_lines.clear()
            in_code = False
        else:
            in_code = True
        continue

    if in_code:
        code_lines.append(line)
        continue

    if not stripped:
        flush_paragraph()
        continue

    if stripped.startswith("# "):
        flush_paragraph()
        story.append(Paragraph(safe(stripped[2:]), styles["DocTitle"]))
    elif stripped.startswith("## "):
        flush_paragraph()
        story.append(Paragraph(safe(stripped[3:]), styles["H1Custom"]))
    elif stripped.startswith("### "):
        flush_paragraph()
        story.append(Paragraph(safe(stripped[4:]), styles["H2Custom"]))
    elif stripped.startswith("|"):
        flush_paragraph()
        if not re.match(r"^\|[\s:\-|]+\|$", stripped):
            story.append(Paragraph(safe(stripped), styles["TableLine"]))
    elif stripped.startswith("- ") or re.match(r"^\d+\.\s", stripped):
        flush_paragraph()
        item = re.sub(r"^-\s", "• ", stripped)
        story.append(Paragraph(safe(item), styles["BodyCustom"]))
    else:
        paragraph.append(stripped)

flush_paragraph()

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(20 * mm, 12 * mm, "T104 - PS-086 | Design Document")
    canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()

document = SimpleDocTemplate(
    str(target), pagesize=A4,
    rightMargin=20 * mm, leftMargin=20 * mm,
    topMargin=18 * mm, bottomMargin=20 * mm,
    title="T104 PS-086 Design Document"
)
document.build(story, onFirstPage=footer, onLaterPages=footer)

print(f"PDF created: {target}")
print(f"File size: {target.stat().st_size} bytes")
