import os
import re
import numpy as np
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from sentence_transformers import SentenceTransformer
from tinydb import TinyDB

app = Flask(__name__)
CORS(app)

DOCS_DIR = "saved_documents"
DB_FILE = "repository.json"

os.makedirs(DOCS_DIR, exist_ok=True)
db = TinyDB(DB_FILE)

# Load lightweight sentence embedding model for Paraphrase Detection
semantic_model = SentenceTransformer('all-MiniLM-L6-v2')

def extract_text_from_file(file_storage):
    file_extension = os.path.splitext(file_storage.filename)[1].lower()
    extracted_text = ""
    try:
        if file_extension == ".txt":
            extracted_text = file_storage.read().decode("utf-8")
        elif file_extension == ".pdf":
            reader = PdfReader(file_storage)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
    except Exception as e:
        print(f"Error reading file: {e}")
        return ""
    return extracted_text.strip()

# ---------------------------------------------------------
# DETECTORS
# ---------------------------------------------------------
def compute_tfidf_similarity(doc1_text, doc2_text):
    vectorizer = TfidfVectorizer().fit_transform([doc1_text, doc2_text])
    vectors = vectorizer.toarray()
    return float(cosine_similarity([vectors[0]], [vectors[1]])[0][0])

def compute_semantic_similarity(doc1_text, doc2_text):
    """Detects Paraphrasing using Vector Embeddings"""
    embeddings = semantic_model.encode([doc1_text, doc2_text])
    score = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
    return float(score)

def detect_ai_generated(text):
    """Calculates AI probability based on Burstiness (Sentence Variance)"""
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    if len(sentences) < 3:
        return 0.0

    sentence_lengths = [len(s.split()) for s in sentences]
    variance = float(np.var(sentence_lengths))

    # Low variance in sentence length indicates high AI probability (flat burstiness)
    if variance < 10:
        ai_score = 85.0
    elif variance < 25:
        ai_score = 60.0
    else:
        ai_score = max(5.0, 100.0 - variance)

    return round(ai_score, 2)

def get_highlighted_html(doc1_text, doc2_text):
    matcher = SequenceMatcher(None, doc1_text, doc2_text)
    doc1_html = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        sub1 = doc1_text[i1:i2]
        if tag in ('replace', 'equal') and len(sub1.strip()) > 3:
            doc1_html.append(f'<mark style="background-color: #f59e0b; color: #000; padding: 2px 4px; border-radius: 3px; font-weight: bold;">{sub1}</mark>')
        else:
            doc1_html.append(sub1)
            
    return "".join(doc1_html)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    text1 = ""
    text2 = ""
    doc1_name = "Input Text 1"
    doc2_name = "Input Text 2"

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
        return jsonify({"error": "Please provide either files or text for both inputs."}), 400

    # Execute all 3 Engines
    direct_copy = compute_tfidf_similarity(text1, text2) * 100
    paraphrase_score = compute_semantic_similarity(text1, text2) * 100
    ai_prob = detect_ai_generated(text1)

    overall_score = max(direct_copy, paraphrase_score)
    highlighted_html1 = get_highlighted_html(text1, text2)

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
            "overall_score": round(overall_score, 2)
        },
        "highlighted_html1": highlighted_html1,
        "text2_preview": text2
    })

if __name__ == "__main__":
    app.run(port=5000, debug=True)