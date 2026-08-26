import os
import json
from datetime import datetime
import streamlit as st
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from tinydb import TinyDB, Query

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
    """Saves raw text content into the saved_documents directory."""
    file_path = os.path.join(DOCS_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path

# ---------------------------------------------------------
# MODULE 2: Plagiarism Detection Algorithms
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

# ---------------------------------------------------------
# MODULE 3: Database & History Management
# ---------------------------------------------------------
def log_analysis_result(doc1_name, doc2_name, tfidf_score, seq_score, max_score):
    """Logs check metadata to TinyDB (repository.json)."""
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "doc1": doc1_name,
        "doc2": doc2_name,
        "tfidf_similarity": round(tfidf_score * 100, 2),
        "sequence_similarity": round(seq_score * 100, 2),
        "overall_plagiarism_score": round(max_score * 100, 2)
    }
    db.insert(record)

# ---------------------------------------------------------
# MODULE 4: Streamlit UI & Interactive Dashboard
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
                # Module 1 Execution
                text1 = extract_text_from_file(uploaded_doc1)
                text2 = extract_text_from_file(uploaded_doc2)
                
                if not text1 or not text2:
                    st.error("One or both documents contain no extractable text.")
                else:
                    # Save to local repository
                    save_document(uploaded_doc1.name, text1)
                    save_document(uploaded_doc2.name, text2)
                    
                    # Module 2 Execution
                    tfidf_score = compute_tfidf_similarity(text1, text2)
                    seq_score = compute_sequence_similarity(text1, text2)
                    overall_score = max(tfidf_score, seq_score)
                    
                    # Module 3 Execution
                    log_analysis_result(
                        uploaded_doc1.name, 
                        uploaded_doc2.name, 
                        tfidf_score, 
                        seq_score, 
                        overall_score
                    )
                    
                    # Module 4 UI Displays
                    st.success("Analysis Complete!")
                    st.divider()
                    
                    # Score Cards
                    m1, m2, m3 = st.columns(3)
                    m1.metric("TF-IDF Similarity", f"{round(tfidf_score * 100, 2)}%")
                    m2.metric("Sequence Match", f"{round(seq_score * 100, 2)}%")
                    m3.metric("Overall Plagiarism Risk", f"{round(overall_score * 100, 2)}%")
                    
                    # Risk Assessment
                    if overall_score > 0.7:
                        st.error("⚠️ **High Risk:** Significant overlap detected across documents.")
                    elif overall_score > 0.3:
                        st.warning("⚡ **Moderate Risk:** Some matching phrases and structural similarities found.")
                    else:
                        st.info("✅ **Low Risk:** Documents appear substantially unique.")
                        
                    # Text Comparison Side-by-Side
                    with st.expander("Compare Document Content"):
                        c1, c2 = st.columns(2)
                        c1.text_area("Primary Document Content", text1, height=250)
                        c2.text_area("Comparison Document Content", text2, height=250)

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
