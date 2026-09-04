from flask import Flask, render_template, request, jsonify
from difflib import SequenceMatcher
import math
import re
from collections import Counter

app = Flask(__name__, static_folder='.', template_folder='.', static_url_path='')

# Defined set of common stop words to exclude from triggering highlight matches
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'aren\'t', 
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'can\'t', 
    'cannot', 'could', 'couldn\'t', 'did', 'didn\'t', 'do', 'does', 'doesn\'t', 'doing', 'don\'t', 'down', 
    'during', 'each', 'few', 'for', 'from', 'further', 'had', 'hadn\'t', 'has', 'hasn\'t', 'have', 'haven\'t', 
    'having', 'he', 'he\'d', 'he\'ll', 'he\'s', 'her', 'here', 'here\'s', 'hers', 'herself', 'him', 'himself', 
    'his', 'how', 'how\'s', 'i', 'i\'d', 'i\'ll', 'i\'m', 'i\'ve', 'if', 'in', 'into', 'is', 'isn\'t', 'it', 
    'it\'s', 'its', 'itself', 'let\'s', 'me', 'more', 'most', 'mustn\'t', 'my', 'myself', 'no', 'nor', 'not', 
    'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 
    'own', 'same', 'shan\'t', 'she', 'she\'d', 'she\'ll', 'she\'s', 'should', 'shouldn\'t', 'so', 'some', 
    'such', 'than', 'that', 'that\'s', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 
    'there\'s', 'these', 'they', 'they\'d', 'they\'ll', 'they\'re', 'they\'ve', 'this', 'those', 'through', 
    'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasn\'t', 'we', 'we\'d', 'we\'ll', 'we\'re', 'we\'ve', 
    'were', 'weren\'t', 'what', 'what\'s', 'when', 'when\'s', 'where', 'where\'s', 'which', 'while', 'who', 
    'who\'s', 'whom', 'why', 'why\'s', 'with', 'won\'t', 'would', 'wouldn\'t', 'you', 'you\'d', 'you\'ll', 
    'you\'re', 'you\'ve', 'your', 'yours', 'yourself', 'yourselves', 'select', 'from', 'where', 'and', 'or'
}

def get_cosine_similarity(text1, text2):
    words1 = [w.lower() for w in text1.split() if w.isalnum()]
    words2 = [w.lower() for w in text2.split() if w.isalnum()]
    
    vec1 = Counter(words1)
    vec2 = Counter(words2)
    
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])

    sum1 = sum([vec1[x]**2 for x in vec1.keys()])
    sum2 = sum([vec2[x]**2 for x in vec2.keys()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    return round((float(numerator) / denominator) * 100, 2)

def calculate_pair_similarity(doc1_obj, doc2_obj):
    text1 = doc1_obj.get('text', '')
    text2 = doc2_obj.get('text', '')
    name1 = doc1_obj.get('name', 'Document A')
    name2 = doc2_obj.get('name', 'Document B')

    if not text1 or not text2:
        return {
            'doc1_name': name1, 'doc2_name': name2,
            'direct_copy': 0.0, 'paraphrase_similarity': 0.0,
            'ai_probability': 0.0, 'overall_risk': 0.0, 'unique_content': 100.0,
            'highlighted_doc1': text1, 'highlighted_doc2': text2,
            'matched_snippets': []
        }

    words1 = text1.split()
    words2 = text2.split()

    matcher_words = SequenceMatcher(None, words1, words2)
    matching_blocks = matcher_words.get_matching_blocks()

    # Filter out blocks that only contain stop words or short generic terms
    significant_matching_blocks = []
    for block in matching_blocks:
        if block.size >= 2:
            matched_words = [w.lower().strip(".,()[]{}:;'\"") for w in words1[block.a : block.a + block.size]]
            # Count words that are NOT stop words
            unique_meaningful_words = [w for w in matched_words if w and w not in STOP_WORDS]
            
            # Highlight only if the block contains at least 2 unique non-stop words OR is longer than 15 characters
            matched_phrase = " ".join(words1[block.a : block.a + block.size])
            if len(unique_meaningful_words) >= 2 or len(matched_phrase) >= 15:
                significant_matching_blocks.append(block)

    exact_match_words = sum(block.size for block in significant_matching_blocks)
    total_words = max(len(words1), len(words2), 1)

    direct_copy = round((exact_match_words / total_words) * 100, 2)
    semantic_sim = get_cosine_similarity(text1, text2)
    paraphrase_sim = round((SequenceMatcher(None, text1, text2).ratio() * 50) + (semantic_sim * 0.5), 2)
    
    ai_prob = round(min(SequenceMatcher(None, text1, text2).ratio() * 35 + 5, 95.0), 1)
    overall_risk = round((direct_copy * 0.45) + (paraphrase_sim * 0.35) + (ai_prob * 0.20), 2)
    unique_content = round(max(0.0, 100.0 - overall_risk), 2)

    highlighted1 = text1
    highlighted2 = text2
    matched_snippets = []
    match_id = 0

    for block in significant_matching_blocks:
        match_id += 1
        seq1 = " ".join(words1[block.a : block.a + block.size])
        seq2 = " ".join(words2[block.b : block.b + block.size])
        
        if len(seq1.strip()) > 5:
            matched_snippets.append(seq1.strip())

        span1 = f'<mark class="match-mark" id="m1_{match_id}" onclick="jumpToMatch(\'m1_{match_id}\', \'m2_{match_id}\')">{seq1} <span class="similarity-tag">{direct_copy}%</span></mark>'
        span2 = f'<mark class="match-mark" id="m2_{match_id}" onclick="jumpToMatch(\'m2_{match_id}\', \'m1_{match_id}\')">{seq2} <span class="similarity-tag">{direct_copy}%</span></mark>'
        
        highlighted1 = re.sub(re.escape(seq1), span1, highlighted1, count=1)
        highlighted2 = re.sub(re.escape(seq2), span2, highlighted2, count=1)

    return {
        'doc1_name': name1,
        'doc2_name': name2,
        'direct_copy': direct_copy,
        'paraphrase_similarity': paraphrase_sim,
        'ai_probability': ai_prob,
        'overall_risk': overall_risk,
        'unique_content': unique_content,
        'highlighted_doc1': highlighted1,
        'highlighted_doc2': highlighted2,
        'matched_snippets': matched_snippets[:5]
    }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json() or {}
    primary_docs = data.get('primary_docs', [])
    comparison_docs = data.get('comparison_docs', [])

    # Consolidate all uploaded documents into a single unique pool
    all_docs = []
    seen_names = set()

    for doc in primary_docs + comparison_docs:
        name = doc.get('name', 'Untitled')
        if name not in seen_names and doc.get('text', '').strip():
            seen_names.add(name)
            all_docs.append(doc)

    batch_results = []

    # Run full N x N pairwise matrix comparison across all unique documents
    num_docs = len(all_docs)
    for i in range(num_docs):
        for j in range(i + 1, num_docs):
            res = calculate_pair_similarity(all_docs[i], all_docs[j])
            batch_results.append(res)

    return jsonify({'batch_results': batch_results})

if __name__ == '__main__':
    app.run(debug=True, port=5000)