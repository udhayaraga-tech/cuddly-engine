import os
import json
import re
from datetime import datetime
import streamlit as st
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from tinydb import TinyDB
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io

# Config & Directory Setup
st.set_page_config(page_title="AI Plagiarism & Similarity Engine", layout="wide")

DOCS_DIR = "saved_documents"
DB_FILE = "repository.json"

os.makedirs(DOCS_DIR, exist_ok=True)
db = TinyDB(DB_FILE)

# ---------------------------------------------------------
# MODULE 1: Document Processing & Extraction
# ---------------------------------------------------------
def extract_text_from_file(uploaded_file):
    """Extracts text from TXT or PDF files."""
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    extracted_text = ""
    
    try:
        if file_extension == ".txt":
            extracted_text = uploaded_file.read().decode("utf-8")
        elif file_extension == ".pdf":
            reader = PdfReader(uploaded_file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
    except Exception as e:
        st.error(f"Error reading {uploaded_file.name}: {str(e)}")
        return ""
        
    return extracted_text.strip()

def save_document(file_name, content):
    """Saves raw text content into saved_documents directory."""
    file_path = os.path.join(DOCS_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path

# ---------------------------------------------------------
# MODULE 2: Algorithms & Text Highlighting
# ---------------------------------------------------------
def compute_tfidf_similarity(doc1_text, doc2_text):
    """Calculates Cosine Similarity using TF-IDF vectorization."""
    if not doc1_text or not doc2_text:
        return 0.0
    vectorizer = TfidfVectorizer().fit_transform([doc1_text, doc2_text])
    vectors = vectorizer.toarray()
    return float(cosine_similarity([vectors[0]], [vectors[1]])[0][0])

def compute_sequence_similarity(doc1_text, doc2_text):
    """Calculates exact phrase match ratio using SequenceMatcher."""
    if not doc1_text or not doc2_text:
        return 0.0
    return SequenceMatcher(None, doc1_text, doc2_text).ratio()

def get_highlighted_html(doc1_text, doc2_text):
    """Highlights matching phrase sequences with background colors."""
    matcher = SequenceMatcher(None, doc1_text, doc2_text)
    doc1_html = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        sub1 = doc1_text[i1:i2]
        if tag in ('replace', 'equal') and len(sub1.strip()) > 3:
            doc1_html.append(f'<mark style="background-color: #ffc107; padding: 2px; border-radius: 3px;">{sub1}</mark>')
        else:
            doc1_html.append(sub1)
            
    return "".join(doc1_html)

# ---------------------------------------------------------
# MODULE 3: PDF Export Engine
# ---------------------------------------------------------
def generate_pdf_report(doc1_name, doc2_name, tfidf_s, seq_s, overall_s):
    """Generates downloadable PDF report using ReportLab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>AI Plagiarism & Similarity Report</b>", styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Generated On:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Paragraph(f"<b>Primary File:</b> {doc1_name}", styles['Normal']))
    story.append(Paragraph(f"<b>Comparison File:</b> {doc2_name}", styles['Normal']))
    story.append(Spacer(1, 18))
    
    story.append(Paragraph(f"<b>TF-IDF Similarity:</b> {round(tfidf_s * 100, 2)}%", styles['Heading2']))
    story.append(Paragraph(f"<b>Sequence Match Score:</b> {round(seq_s * 100, 2)}%", styles['Heading2']))
    story.append(Paragraph(f"<b>Overall Plagiarism Risk:</b> {round(overall_s * 100, 2)}%", styles['Heading2']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# MODULE 4: Streamlit UI
# ---------------------------------------------------------
st.title("🛡️ AI Plagiarism & Similarity Engine")
st.markdown("Analyze documents for structural overlap, phrase matching, and content plagiarism.")

tab1, tab2 = st.tabs(["📄 Document Checker", "📜 Analysis History"])

with tab1:
    st.subheader("Compare Two Documents")
    col1, col2 = st.columns(2)
    
    with col1:
        uploaded_doc1 = st.file_uploader("Upload Primary Document", type=["txt", "pdf"], key="doc1")
    with col2:
        uploaded_doc2 = st.file_uploader("Upload Comparison Document", type=["txt", "pdf"], key="doc2")
        
    if uploaded_doc1 and uploaded_doc2:
        if st.button("Run Plagiarism Check", type="primary"):
            with st.spinner("Extracting content and analyzing similarity..."):
                text1 = extract_text_from_file(uploaded_doc1)
                text2 = extract_text_from_file(uploaded_doc2)
                
                if not text1 or not text2:
                    st.error("One or both documents contain no extractable text.")
                else:
                    save_document(uploaded_doc1.name, text1)
                    save_document(uploaded_doc2.name, text2)
                    
                    tfidf_score = compute_tfidf_similarity(text1, text2)
                    seq_score = compute_sequence_similarity(text1, text2)
                    overall_score = max(tfidf_score, seq_score)
                    
                    # Log record
                    db.insert({
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "doc1": uploaded_doc1.name,
                        "doc2": uploaded_doc2.name,
                        "tfidf_similarity": round(tfidf_score * 100, 2),
                        "sequence_similarity": round(seq_score * 100, 2),
                        "overall_plagiarism_score": round(overall_score * 100, 2)
                    })
                    
                    st.success("Analysis Complete!")
                    st.divider()
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("TF-IDF Similarity", f"{round(tfidf_score * 100, 2)}%")
                    m2.metric("Sequence Match", f"{round(seq_score * 100, 2)}%")
                    m3.metric("Overall Plagiarism Risk", f"{round(overall_score * 100, 2)}%")
                    
                    # Export PDF Button
                    pdf_data = generate_pdf_report(
                        uploaded_doc1.name, uploaded_doc2.name, 
                        tfidf_score, seq_score, overall_score
                    )
                    st.download_button(
                        label="📥 Download PDF Summary Report",
                        data=pdf_data,
                        file_name=f"Plagiarism_Report_{uploaded_doc1.name}.pdf",
                        mime="application/pdf"
                    )
                    
                    # Highlighted Inspector
                    st.subheader("🔍 Matching Text Inspector")
                    highlighted_doc1 = get_highlighted_html(text1, text2)
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption("Primary Document (Highlighted Matches):")
                        st.markdown(f'<div style="height: 300px; overflow-y: scroll; padding: 10px; border: 1px solid #ccc; border-radius: 5px;">{highlighted_doc1}</div>', unsafe_allow_html=True)
                    with c2:
                        st.caption("Comparison Document:")
                        st.text_area("Plain Text Content", text2, height=300)

with tab2:
    st.subheader("Past Analysis Records")
    records = db.all()
    if records:
        st.dataframe(records, use_container_width=True)
        if st.button("Clear History"):
            db.truncate()
            st.rerun()
    else:
        st.info("No analysis records stored in database yet.")
