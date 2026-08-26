import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import PyPDF2
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
import docx
from tinydb import TinyDB
import re
import io
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Create dedicated folder for physical document storage
STORAGE_FOLDER = "saved_documents"
if not os.path.exists(STORAGE_FOLDER):
    os.makedirs(STORAGE_FOLDER)

# 1. Initialize Database & AI Models
db = TinyDB('repository.json')

if len(db) == 0:
    db.insert({
        'title': 'Paper_1_Java_Basics.txt',
        'file_path': '',
        'text': 'Java is a high-level, class-based, object-oriented programming language designed to have as few implementation dependencies as possible.'
    })
    db.insert({
        'title': 'Paper_2_DBMS_Intro.txt',
        'file_path': '',
        'text': 'A database management system is software used to store, retrieve, and run queries on data. SQL is the standard language for relational databases.'
    })
    db.insert({
        'title': 'Paper_3_IoT_Greenhouse.txt',
        'file_path': '',
        'text': 'The automated smart greenhouse monitoring system uses IoT sensors to track temperature, soil moisture, and humidity in real-time.'
    })

@st.cache_resource
def load_models():
    return SentenceTransformer('all-MiniLM-L6-v2')

semantic_model = load_models()

# Enhanced Text Extraction Engine
def extract_text_from_file(uploaded_file):
    extracted_text = ""
    try:
        if uploaded_file.type == "application/pdf":
            file_bytes = uploaded_file.read()

            # 1. Try pdfplumber
            uploaded_file.seek(0)
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t: 
                        extracted_text += t + "\n"

            # 2. Try PyPDF2 fallback
            if not extracted_text.strip():
                uploaded_file.seek(0)
                reader = PyPDF2.PdfReader(uploaded_file)
                for page in reader.pages:
                    t = page.extract_text()
                    if t: 
                        extracted_text += t + "\n"

            # 3. OCR Fallback for scanned image PDFs
            if not extracted_text.strip():
                images = convert_from_bytes(file_bytes)
                for img in images:
                    extracted_text += pytesseract.image_to_string(img) + "\n"

        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                extracted_text += para.text + "\n"

        elif uploaded_file.type == "text/plain":
            extracted_text = str(uploaded_file.read().decode("utf-8"))

    except Exception as e:
        st.error(f"Extraction error: {e}")

    return extracted_text

# MODULE 4: Exclusion Filters
def apply_exclusion_filters(text, ignore_quotes, ignore_refs):
    filtered_text = text
    if ignore_quotes:
        filtered_text = re.sub(r'"[^"]*"', '', filtered_text)
        filtered_text = re.sub(r'“[^”]*”', '', filtered_text)
    if ignore_refs:
        filtered_text = re.split(r'\b(references|bibliography)\b', filtered_text, flags=re.IGNORECASE)[0]
    return filtered_text

# Keyword Highlighting
def highlight_matches(student_text, target_text):
    stop_words = {
        'the', 'and', 'that', 'them', 'then', 'this', 'with', 'from', 'have', 'were', 
        'which', 'also', 'some', 'than', 'about', 'each', 'such', 'used', 'into', 'been',
        'there', 'their', 'what', 'when', 'where', 'who', 'will', 'more', 'other', 'only',
        'they', 'would', 'could', 'should', 'has', 'had', 'does', 'did', 'are', 'was', 'is'
    }
    raw_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', target_text.lower()))
    main_keywords = raw_words - stop_words
    
    if not main_keywords:
        return student_text

    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, main_keywords)) + r')\b', re.IGNORECASE)
    highlighted = pattern.sub(
        r'<mark style="background-color: #b71c1c; color: #ffffff; font-weight: bold; padding: 2px 5px; border-radius: 3px;">\1</mark>', 
        student_text
    )
    return highlighted

# PDF Generator
def generate_pdf_report(filename, results, highest_match_doc, highest_score, threshold):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor("#1A2B4C"), spaceAfter=12)
    story.append(Paragraph("Institutional Plagiarism Detection Report", title_style))
    story.append(Spacer(1, 10))

    meta_text = f"<b>Submitted File:</b> {filename}<br/><b>Flag Threshold:</b> {threshold}%<br/><b>Highest Similarity:</b> {highest_score:.2f}% ({highest_match_doc})"
    story.append(Paragraph(meta_text, styles['Normal']))
    story.append(Spacer(1, 15))

    table_data = [["Repository Document", "Lexical (TF-IDF)", "Semantic (S-BERT)", "Final Score", "Status"]]
    for row in results:
        table_data.append([
            row["Compared Repository Document"],
            row["Word-Match Similarity (TF-IDF)"],
            row["AI Meaning Similarity (S-BERT)"],
            row["Final Decision Metric"],
            row["Status"]
        ])

    pdf_table = Table(table_data, colWidths=[160, 85, 95, 75, 110])
    pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1A2B4C")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    story.append(pdf_table)
    doc.build(story)
    buffer.seek(0)
    return buffer

# UI Layout
st.set_page_config(page_title="Institutional Plagiarism Checker", layout="wide")
st.title("🛡️ AI-Based Plagiarism & Similarity Engine")
st.subheader("Institutional Repository Prototype")
st.write("---")

# Sidebar
st.sidebar.header("Workflow Configurations")

if 'threshold' not in st.session_state:
    st.session_state['threshold'] = 10

match_threshold = st.sidebar.slider(
    "Flag Threshold Limit (%)", 
    min_value=0, 
    max_value=100, 
    value=st.session_state['threshold'], 
    key='threshold_slider'
)

st.sidebar.write("---")
st.sidebar.header("Module 4 Filters")
ignore_quotes = st.sidebar.checkbox("Ignore Direct Quotes (\"...\")", value=True)
ignore_refs = st.sidebar.checkbox("Ignore References / Bibliography", value=True)

st.sidebar.write("---")
st.sidebar.header("Repository Metrics")
st.sidebar.info(f"📁 Total Stored Papers: **{len(db)}**")

# Sidebar File Inspector
st.sidebar.write("---")
st.sidebar.header("📁 Browse Saved Physical Files")
all_docs = db.all()
doc_titles = [d['title'] for d in all_docs]
selected_doc_title = st.sidebar.selectbox("Select a file to inspect:", doc_titles)

if selected_doc_title:
    selected_doc = next(item for item in all_docs if item["title"] == selected_doc_title)
    with st.sidebar.expander(f"📖 View details for {selected_doc_title}"):
        if selected_doc.get("file_path") and os.path.exists(selected_doc["file_path"]):
            st.write(f"**Saved Path:** `{selected_doc['file_path']}`")
        st.write("**Extracted Text Preview:**")
        st.text_area("", selected_doc["text"], height=150, disabled=True)

# Step 1: Input
st.header("Step 1: Submit Student Assignment")
input_option = st.radio("Choose submission method:", ["Upload Document (.pdf, .docx, .txt)", "Paste Plain Text"])

student_paper = ""
uploaded_file_obj = None
uploaded_filename = "Manual_Submission.txt"

if input_option == "Paste Plain Text":
    student_paper = st.text_area("Paste text here:", height=180)
else:
    uploaded_file_obj = st.file_uploader("Upload student assignment:", type=["pdf", "docx", "txt"])
    if uploaded_file_obj is not None:
        student_paper = extract_text_from_file(uploaded_file_obj)
        uploaded_filename = uploaded_file_obj.name
        if student_paper.strip():
            st.success(f"File '{uploaded_file_obj.name}' processed successfully!")
        else:
            st.warning(f"File '{uploaded_file_obj.name}' was uploaded, but no text could be extracted.")

# Step 2: Execution
if st.button("Run Plagiarism Analysis"):
    if not student_paper.strip():
        st.error("Please provide text or upload a valid text-based file to analyze.")
    else:
        st.write("---")
        st.header("Step 2: Analysis Results")
        
        processed_student_text = apply_exclusion_filters(student_paper, ignore_quotes, ignore_refs)
        
        all_records = db.all()
        repo_titles = [doc['title'] for doc in all_records]
        repo_texts = [doc['text'] for doc in all_records]
        
        # TF-IDF
        tfidf_vectorizer = TfidfVectorizer()
        all_texts = [processed_student_text] + repo_texts
        tfidf_matrix = tfidf_vectorizer.fit_transform(all_texts)
        tfidf_similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        # S-BERT
        student_embedding = semantic_model.encode([processed_student_text])
        repo_embeddings = semantic_model.encode(repo_texts)
        ai_similarities = cosine_similarity(student_embedding, repo_embeddings).flatten()

        results_data = []
        for i in range(len(repo_titles)):
            lexical_score = round(float(tfidf_similarities[i]) * 100, 2)
            semantic_score = round(float(ai_similarities[i]) * 100, 2)
            final_score = max(lexical_score, semantic_score)
            
            status = "🔴 PLAGIARISM FLAGGED" if final_score >= match_threshold else "🟢 CLEAR"
            
            results_data.append({
                "Compared Repository Document": repo_titles[i],
                "Word-Match Similarity (TF-IDF)": f"{lexical_score}%",
                "AI Meaning Similarity (S-BERT)": f"{semantic_score}%",
                "Final Decision Metric": f"{final_score}%",
                "Status": status
            })
            
        st.table(results_data)
        
        max_idx = ai_similarities.argmax()
        highest_score = max(tfidf_similarities[max_idx], ai_similarities[max_idx]) * 100
        
        if highest_score >= match_threshold:
            st.warning(f"⚠️ **High Flag Alert:** Strong match found with **{repo_titles[max_idx]}**.")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info("**Student Submission (Highlighted Matches):**")
                highlighted_student = highlight_matches(processed_student_text, repo_texts[max_idx])
                st.markdown(
                    f'<div style="background-color: #ffffff; color: #000000; padding: 15px; border: 1px solid #ccc; border-radius: 5px; height: 300px; overflow-y: auto; line-height: 1.8;">{highlighted_student}</div>', 
                    unsafe_allow_html=True
                )
            with col2:
                st.info("**Matching Repository Source Text:**")
                st.markdown(
                    f'<div style="background-color: #ffffff; color: #000000; padding: 15px; border: 1px solid #ccc; border-radius: 5px; height: 300px; overflow-y: auto; line-height: 1.8;">{repo_texts[max_idx]}</div>', 
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ Clean submission. No structural plagiarism detected.")

        # Step 3: Export & Repository Management
        st.write("---")
        st.header("Step 3: Export & Repository Management")
        
        pdf_bytes = generate_pdf_report(uploaded_filename, results_data, repo_titles[max_idx], highest_score, match_threshold)
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button(
                label="📄 Download Official PDF Report",
                data=pdf_bytes,
                file_name=f"Plagiarism_Report_{uploaded_filename}.pdf",
                mime="application/pdf"
            )
        with col_b:
            if st.button("➕ Save Submission to Local Physical Directory"):
                saved_path = ""
                
                if uploaded_file_obj is not None:
                    # Save actual uploaded PDF/DOCX/TXT file to local disk
                    saved_path = os.path.join(STORAGE_FOLDER, uploaded_filename)
                    uploaded_file_obj.seek(0)
                    with open(saved_path, "wb") as f:
                        f.write(uploaded_file_obj.read())
                else:
                    # If text was manually pasted, write it out to a physical .txt file
                    saved_path = os.path.join(STORAGE_FOLDER, uploaded_filename)
                    with open(saved_path, "w", encoding="utf-8") as f:
                        f.write(student_paper)

                # Store metadata inside TinyDB
                db.insert({
                    'title': uploaded_filename, 
                    'file_path': saved_path,
                    'text': student_paper
                })
                
                st.success(f"Physical file saved to `{saved_path}` and linked to database!")
                st.rerun()