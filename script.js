// Theme Toggle
function updateTheme(themeName) {
  document.documentElement.setAttribute('data-theme', themeName);
}

// Interactive Highlight Focus Jump Functionality
function jumpToMatch(currentId, targetId) {
  document.querySelectorAll('.match-mark.active-target').forEach(el => {
    el.classList.remove('active-target');
  });

  const currentEl = document.getElementById(currentId);
  const targetEl = document.getElementById(targetId);

  if (currentEl) currentEl.classList.add('active-target');
  if (targetEl) {
    targetEl.classList.add('active-target');
    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// Setup Drag & Drop Listeners
document.addEventListener('DOMContentLoaded', () => {
  setupDropZone('drop1', 'text1');
  setupDropZone('drop2', 'text2');
});

function setupDropZone(dropZoneId, targetTextareaId) {
  const zone = document.getElementById(dropZoneId);
  if (!zone) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    zone.addEventListener(eventName, e => e.preventDefault(), false);
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    zone.addEventListener(eventName, () => zone.classList.add('drag-active'), false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    zone.addEventListener(eventName, () => zone.classList.remove('drag-active'), false);
  });

  zone.addEventListener('drop', e => {
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file, targetTextareaId, dropZoneId);
  });
}

// File Parsing Handler (.txt, .pdf, .docx)
async function handleFileSelect(file, targetTextareaId, dropZoneId) {
  if (!file) return;
  const textarea = document.getElementById(targetTextareaId);
  const zone = document.getElementById(dropZoneId);

  try {
    let extractedText = "";

    if (file.name.endsWith('.txt')) {
      extractedText = await file.text();
    } else if (file.name.endsWith('.pdf')) {
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      let textArray = [];
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        textArray.push(content.items.map(item => item.str).join(" "));
      }
      extractedText = textArray.join("\n\n");
    } else if (file.name.endsWith('.docx')) {
      const arrayBuffer = await file.arrayBuffer();
      const result = await mammoth.extractRawText({ arrayBuffer: arrayBuffer });
      extractedText = result.value;
    } else {
      alert("Unsupported file type. Please upload .txt, .pdf, or .docx");
      return;
    }

    textarea.value = extractedText;
    if (zone) zone.querySelector('.drop-zone-text').textContent = `Loaded: ${file.name}`;
  } catch (err) {
    console.error("Error reading file:", err);
    alert("Could not extract text from the selected file.");
  }
}

// Perform Deep Analysis API Request
async function runAnalysis() {
  const text1 = document.getElementById('text1')?.value || "";
  const text2 = document.getElementById('text2')?.value || "";

  try {
    const response = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text1, text2 })
    });

    const data = await response.json();

    if (document.getElementById('directCopyScore')) {
      document.getElementById('directCopyScore').innerText = `${data.direct_copy}%`;
    }
    if (document.getElementById('paraphraseScore')) {
      document.getElementById('paraphraseScore').innerText = `${data.paraphrase_similarity}%`;
    }
    if (document.getElementById('aiProbScore')) {
      document.getElementById('aiProbScore').innerText = `${data.ai_probability}%`;
    }
    if (document.getElementById('overallRiskScore')) {
      document.getElementById('overallRiskScore').innerText = `${data.overall_risk}%`;
    }

    const container1 = document.getElementById('primaryContentPreview');
    const container2 = document.getElementById('comparisonContentPreview');

    if (container1) container1.innerHTML = data.highlighted_doc1;
    if (container2) container2.innerHTML = data.highlighted_doc2;

  } catch (error) {
    console.error("Error conducting deep analysis:", error);
  }
}