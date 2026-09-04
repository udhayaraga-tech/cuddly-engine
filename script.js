let chartInstance = null;
let uploadedPrimaryFiles = [];
let uploadedComparisonFiles = [];
let activeBatchResults = [];

// Accumulative file upload reader
async function handleMultiFileSelect(files, labelId, textareaId) {
  if (!files || files.length === 0) return;

  const targetArray = (textareaId === 'text1') ? uploadedPrimaryFiles : uploadedComparisonFiles;

  for (let file of files) {
    if (!targetArray.some(doc => doc.name === file.name)) {
      let extracted = await parseFileContent(file);
      targetArray.push({ name: file.name, text: extracted });
    }
  }

  const label = document.getElementById(labelId);
  if (label) label.innerText = `${targetArray.length} file(s) selected`;

  let combinedText = targetArray
    .map(doc => `--- File: ${doc.name} ---\n${doc.text}`)
    .join('\n\n');

  const textarea = document.getElementById(textareaId);
  if (textarea) textarea.value = combinedText.trim();
}

async function parseFileContent(file) {
  try {
    if (file.name.endsWith('.txt')) {
      return await file.text();
    } else if (file.name.endsWith('.pdf')) {
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      let textArray = [];
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        textArray.push(content.items.map(item => item.str).join(" "));
      }
      return textArray.join("\n");
    } else if (file.name.endsWith('.docx')) {
      const arrayBuffer = await file.arrayBuffer();
      const result = await mammoth.extractRawText({ arrayBuffer: arrayBuffer });
      return result.value;
    }
  } catch (err) {
    console.error("File parse error:", err);
    return "";
  }
}

// Chart Renderer
function renderCompositionChart(directCopy, paraphrase, unique) {
  const canvas = document.getElementById('compositionChart');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Direct Copy', 'Paraphrase', 'Unique Content'],
      datasets: [{
        data: [directCopy, paraphrase, unique],
        backgroundColor: ['#ef4444', '#f59e0b', '#10b981'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#94a3b8', font: { size: 12 } }
        }
      },
      cutout: '70%'
    }
  });
}

// Saved Docs API Handlers
async function loadSavedDocsList() {
  const res = await fetch('/saved-docs');
  const data = await res.json();
  const listEl = document.getElementById('savedDocsFileList');
  if (!listEl) return;
  
  listEl.innerHTML = '';
  data.saved_files.forEach(file => {
    listEl.innerHTML += `
      <div style="display: flex; align-items: center; justify-content: space-between; font-size: 12px; margin-bottom: 4px;">
        <label style="color: #cbd5e1;">
          <input type="checkbox" class="saved-file-checkbox" value="${file}" checked> ${file}
        </label>
        <button onclick="deleteSingleSavedDoc('${file}')" style="background: transparent; color: #f87171; border: none; cursor: pointer;">Delete</button>
      </div>`; 
  });
}

function toggleSavedDocsList() {
  const isChecked = document.getElementById('toggleSavedDocs').checked;
  const container = document.getElementById('savedDocsContainer');
  if (isChecked) {
    container.classList.remove('hidden');
    loadSavedDocsList();
  } else {
    container.classList.add('hidden');
  }
}

async function deleteSingleSavedDoc(filename) {
  if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
  await fetch('/saved-docs/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename })
  });
  loadSavedDocsList();
}

async function purgeAllSavedDocs() {
  if (!confirm("Clear all repository documents for the new semester? This cannot be undone.")) return;
  await fetch('/saved-docs/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ purge_all: true })
  });
  loadSavedDocsList();
}

// Trigger Full Matrix Cross-Analysis
async function runAnalysis() {
  let primaryDocs = [...uploadedPrimaryFiles];
  let comparisonDocs = [...uploadedComparisonFiles];

  if (primaryDocs.length === 0 && document.getElementById('text1').value.trim()) {
    primaryDocs.push({ name: "Primary Input Text", text: document.getElementById('text1').value });
  }
  if (comparisonDocs.length === 0 && document.getElementById('text2').value.trim()) {
    comparisonDocs.push({ name: "Comparison Input Text", text: document.getElementById('text2').value });
  }

  const useSavedDocs = document.getElementById('toggleSavedDocs').checked;
  const selectedSavedFiles = Array.from(document.querySelectorAll('.saved-file-checkbox:checked')).map(cb => cb.value);

  try {
    const response = await fetch('/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        primary_docs: primaryDocs, 
        comparison_docs: comparisonDocs,
        use_saved_docs: useSavedDocs,
        selected_saved_files: selectedSavedFiles
      })
    });
    
    const data = await response.json();
    activeBatchResults = data.batch_results;

    if (activeBatchResults.length > 0) {
      setupBatchSelector(activeBatchResults);
      loadBatchPair(0);
    } else {
      alert("Please upload at least 2 files or enter text on both sides to perform cross-comparison.");
    }
  } catch (error) {
    console.error("Analysis request failed:", error);
  }
}

// Populate Cross-Pair Select Dropdown
function setupBatchSelector(results) {
  const container = document.getElementById('batchSelectorContainer');
  const select = document.getElementById('batchSelect');
  if (!container || !select) return;
  select.innerHTML = '';

  if (results.length > 0) {
    container.classList.remove('hidden');
    results.forEach((res, idx) => {
      const opt = document.createElement('option');
      opt.value = idx;
      opt.innerText = `Pair ${idx + 1}: [${res.doc1_name}] vs [${res.doc2_name}] ➔ Risk: ${res.overall_risk}%`;
      select.appendChild(opt);
    });
  }
}

// Load Pair Data into UI
function loadBatchPair(index) {
  const data = activeBatchResults[index];
  if (!data) return;
  document.getElementById('directCopyScore').innerText = `${data.direct_copy}%`;
  document.getElementById('paraphraseScore').innerText = `${data.paraphrase_similarity}%`;
  document.getElementById('aiProbScore').innerText = `${data.ai_probability}%`;
  document.getElementById('overallRiskScore').innerText = `${data.overall_risk}%`;
  document.getElementById('primaryContentPreview').innerHTML = data.highlighted_doc1;
  document.getElementById('comparisonContentPreview').innerHTML = data.highlighted_doc2;
  renderCompositionChart(data.direct_copy, data.paraphrase_similarity, data.unique_content);
}

// Executive PDF Report Generator
function downloadExecutivePDFReport() {
  if (!activeBatchResults || activeBatchResults.length === 0) {
    alert("No scan results available to print. Please run the analysis first.");
    return;
  }
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();
  const timestamp = new Date().toLocaleString();

  // Page 1: Header & Summary Matrix
  doc.setFillColor(15, 23, 42);
  doc.rect(0, 0, 210, 40, 'F');
  doc.setFontSize(20);
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.text("FULL BATCH MULTI-FILE SCAN REPORT", 14, 22);
  doc.setFontSize(10);
  doc.setTextColor(148, 163, 184);
  doc.setFont("helvetica", "normal");
  doc.text(`AI Deep-Scan Engine v4.0 | Generated: ${timestamp}`, 14, 32);
  doc.setFontSize(14);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(15, 23, 42);
  doc.text("Master Pairwise Comparison Summary", 14, 52);

  const summaryRows = activeBatchResults.map((res, index) => [
    `#${index + 1}`,
    res.doc1_name,
    res.doc2_name,
    `${res.direct_copy}%`,
    `${res.paraphrase_similarity}%`,
    `${res.ai_probability}%`,
    `${res.overall_risk}%`
  ]);

  doc.autoTable({
    startY: 58,
    head: [['#', 'Document A', 'Document B', 'Direct Copy', 'Paraphrase', 'AI Prob.', 'Overall Risk']],
    body: summaryRows,
    headStyles: { fillColor: [79, 70, 229], textColor: [255, 255, 255], fontStyle: 'bold' },
    bodyStyles: { textColor: [30, 41, 59], fontSize: 9 },
    alternateRowStyles: { fillColor: [241, 245, 249] },
    didParseCell: function (data) {
      if (data.section === 'body' && data.column.index === 6) {
        const val = parseFloat(data.cell.raw);
        if (val > 10.0) {
          data.cell.styles.textColor = [220, 38, 38];
          data.cell.styles.fontStyle = 'bold';
        } else {
          data.cell.styles.textColor = [22, 163, 74];
          data.cell.styles.fontStyle = 'bold';
        }
      }
    }
  });

  // Subsequent Pages: Pair breakdowns
  activeBatchResults.forEach((pair, idx) => {
    doc.addPage();
    doc.setFillColor(30, 41, 59);
    doc.rect(0, 0, 210, 25, 'F');
    doc.setFontSize(12);
    doc.setTextColor(255, 255, 255);
    doc.setFont("helvetica", "bold");
    doc.text(`Pair Breakdown #${idx + 1}: ${pair.doc1_name}  VS  ${pair.doc2_name}`, 14, 16);

    doc.autoTable({
      startY: 32,
      head: [['Metric Parameter', 'Match Ratio', 'Status Rating', 'Threshold Limit']],
      body: [
        ['Direct Copy', `${pair.direct_copy}%`, pair.direct_copy > 10.0 ? 'UNACCEPTABLE' : 'PASS', '> 10.0%'],
        ['Paraphrase Similarity', `${pair.paraphrase_similarity}%`, pair.paraphrase_similarity > 10.0 ? 'UNACCEPTABLE' : 'PASS', '> 10.0%'],
        ['AI Content Probability', `${pair.ai_probability}%`, pair.ai_probability > 10.0 ? 'HIGH AI' : 'HUMAN', '> 10.0%'],
        ['Overall Plagiarism Risk', `${pair.overall_risk}%`, pair.overall_risk > 10.0 ? 'CRITICAL RISK' : 'ACCEPTABLE', '> 10.0%']
      ],
      headStyles: { fillColor: [79, 70, 229], textColor: [255, 255, 255] },
      bodyStyles: { textColor: [30, 41, 59] },
      alternateRowStyles: { fillColor: [248, 250, 252] },
      didParseCell: function (data) {
        if (data.section === 'body' && data.column.index === 2) {
          const val = data.cell.raw;
          if (val === 'UNACCEPTABLE' || val === 'CRITICAL RISK' || val === 'HIGH AI') {
            data.cell.styles.textColor = [220, 38, 38];
            data.cell.styles.fontStyle = 'bold';
          } else {
            data.cell.styles.textColor = [22, 163, 74];
            data.cell.styles.fontStyle = 'bold';
          }
        }
      }
    });

    let currentY = doc.lastAutoTable.finalY + 10;
    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(15, 23, 42);
    doc.text("Top Detected Matching Passages:", 14, currentY);
    currentY += 8;

    if (pair.matched_snippets && pair.matched_snippets.length > 0) {
      pair.matched_snippets.forEach((snippet, sIdx) => {
        if (currentY > 260) {
          doc.addPage();
          currentY = 20;
        }
        doc.setFillColor(254, 243, 199);
        doc.rect(14, currentY, 182, 12, 'F');
        doc.setTextColor(180, 83, 9);
        doc.setFontSize(9);
        doc.setFont("helvetica", "bold");
        doc.text(`Match ${sIdx + 1}:`, 18, currentY + 8);
        doc.setTextColor(51, 65, 85);
        doc.setFont("helvetica", "normal");
        const cleanSnippet = snippet.replace(/<[^>]*>?/gm, '');
        const truncated = cleanSnippet.length > 80 ? cleanSnippet.substring(0, 80) + "..." : cleanSnippet;
        doc.text(truncated, 36, currentY + 8);
        currentY += 15;
      });
    } else {
      doc.setFontSize(9);
      doc.setFont("helvetica", "italic");
      doc.setTextColor(100, 116, 139);
      doc.text("No matching text excerpts surpassed the minimum length threshold for this pair.", 14, currentY + 4);
    }
  });

  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setDrawColor(226, 232, 240);
    doc.line(14, 282, 196, 282);
    doc.setFontSize(8);
    doc.setTextColor(148, 163, 184);
    doc.setFont("helvetica", "normal");
    doc.text("CONFIDENTIAL — COMPREHENSIVE BATCH PLAGIARISM REPORT", 14, 288);
    doc.text(`Page ${i} of ${totalPages}`, 175, 288);
  }

  doc.save(`Full_Batch_Plagiarism_Report_${Date.now()}.pdf`);
}

// Highlight Click Linker and Scroll Handler
function jumpToMatch(currentId, targetId) {
  document.querySelectorAll('mark.match-mark').forEach(el => {
    el.classList.remove('active-target');
  });
  const currentEl = document.getElementById(currentId);
  const targetEl = document.getElementById(targetId);

  if (currentEl) {
    currentEl.classList.add('active-target');
    scrollToInsideContainer(currentEl);
  }
  if (targetEl) {
    targetEl.classList.add('active-target');
    scrollToInsideContainer(targetEl);
  }
}

function scrollToInsideContainer(element) {
  const container = element.closest('.scroll-content') || element.closest('#primaryContentPreview') || element.closest('#comparisonContentPreview');
  if (!container) return;
  const containerTop = container.getBoundingClientRect().top;
  const elementTop = element.getBoundingClientRect().top;
  const relativeOffset = elementTop - containerTop - (container.clientHeight / 2) + (element.clientHeight / 2);
  container.scrollTo({
    top: container.scrollTop + relativeOffset,
    behavior: 'smooth'
  });
}