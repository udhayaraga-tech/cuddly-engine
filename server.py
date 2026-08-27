import os
import re
import io
import numpy as np
import docx
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from sentence_transformers import SentenceTransformer
from tinydb import TinyDB

# PDF Generation imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
CORS(app)

DOCS_DIR = "saved_documents"
DB_FILE = "repository.json"

os.makedirs(DOCS_DIR, exist_ok=True)
db = TinyDB(DB_FILE)

semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

def extract_text_from_file(file_storage):
    file_extension = os.path.splitext(file_storage.filename)[1].lower()
    extracted_text = ""
    try:
        if file_extension == ".txt":
            extracted_text = file_storage.read().decode("utf-8", errors="ignore")
        elif file_extension == ".pdf":
            reader = PdfReader(file_storage)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        elif file_extension == ".docx":
            doc = docx.Document(file_storage)
            extracted_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        print(f"Error reading file {file_storage.filename}: {e}")
        return ""
    return extracted_text.strip()

def compute_tfidf_similarity(doc1_text, doc2_text):
    vectorizer = TfidfVectorizer().fit_transform([doc1_text, doc2_text])
    vectors = vectorizer.toarray()
    return float(cosine_similarity([vectors[0]], [vectors[1]])[0][0])

def compute_semantic_similarity(doc1_text, doc2_text):
    embeddings = semantic_model.encode([doc1_text, doc2_text])
    score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    return float(score)

def detect_ai_generated(text):
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    if len(sentences) < 3:
        return 0.0

    sentence_lengths = [len(s.split()) for s in sentences]
    variance = float(np.var(sentence_lengths))

    if variance < 10:
        ai_score = 85.0
    elif variance < 25:
        ai_score = 60.0
    else:
        ai_score = max(5.0, 100.0 - variance)

    return round(ai_score, 2)

def generate_interactive_highlights(doc1_text, doc2_text):
    matcher = SequenceMatcher(None, doc1_text, doc2_text)
    doc1_html, doc2_html = [], []
    opcodes = matcher.get_opcodes()
    
    match_id = 0
    for tag, i1, i2, j1, j2 in opcodes:
        sub1 = doc1_text[i1:i2]
        if tag in ('replace', 'equal') and len(sub1.strip()) > 3:
            match_id += 1
            doc1_html.append(f'<mark id="m1_{match_id}" class="match-mark" data-match="m2_{match_id}" title="Match #{match_id}">{sub1}</mark>')
        else:
            doc1_html.append(sub1)

    match_id = 0
    for tag, i1, i2, j1, j2 in opcodes:
        sub2 = doc2_text[j1:j2]
        if tag in ('replace', 'equal') and len(sub2.strip()) > 3:
            match_id += 1
            doc2_html.append(f'<mark id="m2_{match_id}" class="match-mark target-mark" data-match="m1_{match_id}" title="Match #{match_id}">{sub2}</mark>')
        else:
            doc2_html.append(sub2)

    return "".join(doc1_html), "".join(doc2_html)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    text1, text2 = "", ""
    doc1_name, doc2_name = "Input Text 1", "Input Text 2"

    if "doc1" in request.files and request.files["doc1"].filename != "":
        file1 = request.files["doc1"]
        text1 = extract_text_from_file(file1)
        doc1_name = file1.filename
    elif "text1" in request.form and request.form["text1"].strip() != "":
        text1 = request.form["text1"].strip()

    if "doc2" in request.files and request.files["doc2"].filename != "":
        file2 = request.files["doc2"]
        text2 = extract_text_from_file(file2)
        doc2_name = file2.filename
    elif "text2" in request.form and request.form["text2"].strip() != "":
        text2 = request.form["text2"].strip()

    if not text1 or not text2:
        return jsonify({"error": "Unable to extract text from inputs."}), 400

    direct_copy = compute_tfidf_similarity(text1, text2) * 100
    paraphrase_score = compute_semantic_similarity(text1, text2) * 100
    ai_prob = detect_ai_generated(text1)
    overall_score = max(direct_copy, paraphrase_score)
    unique_score = max(0.0, 100.0 - overall_score)

    highlighted_html1, highlighted_html2 = generate_interactive_highlights(text1, text2)

    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "doc1": doc1_name,
        "doc2": doc2_name,
        "direct_copy_score": round(direct_copy, 2),
        "paraphrase_score": round(paraphrase_score, 2),
        "ai_generated_probability": ai_prob,
        "overall_score": round(overall_score, 2)
    }
    db.insert(record)

    return jsonify({
        "status": "success",
        "results": {
            "direct_copy": round(direct_copy, 2),
            "paraphrase_score": round(paraphrase_score, 2),
            "ai_probability": ai_prob,
            "overall_score": round(overall_score, 2),
            "unique_score": round(unique_score, 2)
        },
        "highlighted_html1": highlighted_html1,
        "highlighted_html2": highlighted_html2
    })

@app.route("/api/download-report", methods=["POST"])
def download_report():
    data = request.json or {}
    direct = data.get("direct_copy", "0%")
    para = data.get("paraphrase_score", "0%")
    ai = data.get("ai_probability", "0%")
    overall = data.get("overall_score", "0%")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor("#4F46E5"),
        spaceAfter=12
    )
    
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=20
    )

    story = [
        Paragraph("Plagiarism & Similarity Analysis Report", title_style),
        Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", meta_style),
        Spacer(1, 10)
    ]

    table_data = [
        [Paragraph("<b>Metric</b>", styles['Normal']), Paragraph("<b>Score</b>", styles['Normal'])],
        ["Direct Copy", str(direct) + "%"],
        ["Paraphrase Similarity", str(para) + "%"],
        ["AI Content Probability", str(ai) + "%"],
        ["Overall Risk", str(overall) + "%"]
    ]

    t = Table(table_data, colWidths=[250, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E0E7FF")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#1E1B4B")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
    ]))

    story.append(t)
    doc.build(story)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="Plagiarism_Report.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(port=5000, debug=True)