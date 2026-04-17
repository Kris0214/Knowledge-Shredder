// ── State ──────────────────────────────────────────────────────────────────
let allDomains = [];
let selectedFile = null;
let previewDocId = null;
let pollTimer = null;

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await loadDomains();
    await loadDocuments();
    setupDropZone();
    setupDomainForm();
    setupUploadForm();
});

// ── Domains ────────────────────────────────────────────────────────────────
async function loadDomains() {
    try {
        allDomains = await apiGet('/domains');
        renderDomainChips();
        renderDomainTable();
    } catch (e) {
        toast('載入領域失敗：' + e.message, 'error');
    }
}

function renderDomainChips() {
    const grid = document.getElementById('domain-chips');
    grid.innerHTML = allDomains.map(d => `
    <label class="domain-chip" data-id="${d.domain_id}">
      <input type="checkbox" value="${d.domain_id}">
      #${d.domain_name}
    </label>
  `).join('');
    grid.querySelectorAll('.domain-chip input[type=checkbox]').forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            checkbox.closest('.domain-chip').classList.toggle('selected', checkbox.checked);
        });
    });
}

function renderDomainTable() {
    const tbody = document.querySelector('#domain-table tbody');
    if (!allDomains.length) {
        tbody.innerHTML = '<tr><td colspan="3" style="color:var(--muted);text-align:center">尚無領域，請先新增</td></tr>';
        return;
    }
    tbody.innerHTML = allDomains.map(d => `
    <tr>
      <td><span class="badge badge-blue">#${d.domain_name}</span></td>
      <td>${d.description || '—'}</td>
      <td>
        <button class="btn btn-ghost btn-sm" onclick="deleteDomain(${d.domain_id}, '${d.domain_name}')">刪除</button>
      </td>
    </tr>
  `).join('');
}

function setupDomainForm() {
    document.getElementById('domain-form').addEventListener('submit', async e => {
        e.preventDefault();
        const name = document.getElementById('domain-name').value.trim();
        const desc = document.getElementById('domain-desc').value.trim();
        if (!name) return;
        try {
            await apiPost('/domains', { domain_name: name, description: desc || null });
            toast(`領域 #${name} 已新增`, 'success');
            document.getElementById('domain-form').reset();
            await loadDomains();
        } catch (e) {
            toast('新增失敗：' + e.message, 'error');
        }
    });
}

async function deleteDomain(id, name) {
    if (!confirm(`確定要刪除領域 #${name}？`)) return;
    try {
        await apiDelete(`/domains/${id}`);
        toast(`已刪除 #${name}`, 'info');
        await loadDomains();
    } catch (e) {
        toast('刪除失敗：' + e.message, 'error');
    }
}

// ── Drop Zone ──────────────────────────────────────────────────────────────
function setupDropZone() {
    const zone = document.getElementById('drop-zone');
    const input = document.getElementById('file-input');
    const label = document.getElementById('file-label');

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('dragover');
        const f = e.dataTransfer.files[0];
        if (f) setFile(f);
    });
    input.addEventListener('change', () => { if (input.files[0]) setFile(input.files[0]); });

    function setFile(f) {
        selectedFile = f;
        label.textContent = f.name;
        label.style.color = 'var(--primary)';
    }
}

// ── Upload ─────────────────────────────────────────────────────────────────
function setupUploadForm() {
    document.getElementById('upload-form').addEventListener('submit', async e => {
        e.preventDefault();
        if (!selectedFile) { toast('請先選擇文件', 'error'); return; }
        const selected = [...document.querySelectorAll('.domain-chip.selected input')]
            .map(i => parseInt(i.value));
        if (!selected.length) { toast('至少選擇一個領域', 'error'); return; }

        const trainerId = document.getElementById('trainer-id').value.trim();
        if (!trainerId) { toast('請輸入訓練師 ID', 'error'); return; }

        const btn = document.getElementById('upload-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> 上傳中…';

        try {
            const fd = new FormData();
            fd.append('file', selectedFile);
            fd.append('trainer_id', trainerId);
            fd.append('domain_ids', JSON.stringify(selected));

            const res = await apiPostForm('/documents/upload', fd);
            toast(`文件已送出，AI 粉碎中… (doc_id: ${res.doc_id})`, 'info');
            previewDocId = res.doc_id;

            // 重置表單
            document.getElementById('upload-form').reset();
            selectedFile = null;
            document.getElementById('file-label').textContent = '拖曳或點擊選擇 PDF / Word / TXT';
            document.getElementById('file-label').style.color = '';
            document.querySelectorAll('.domain-chip.selected').forEach(c => c.classList.remove('selected'));

            await loadDocuments();
            startPolling(res.doc_id);
        } catch (e) {
            toast('上傳失敗：' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '上傳並粉碎';
        }
    });
}

// ── Documents List ─────────────────────────────────────────────────────────
async function loadDocuments() {
    try {
        const docs = await apiGet('/documents');
        const tbody = document.querySelector('#docs-table tbody');
        if (!docs.length) {
            tbody.innerHTML = '<tr><td colspan="5" style="color:var(--muted);text-align:center">尚無文件</td></tr>';
            return;
        }
        tbody.innerHTML = docs.map(d => {
            const previewBtn = d.status === 'done'
                ? `<button class="btn btn-primary btn-sm" onclick="loadPreview(${d.doc_id}, false)">預覽模組</button>`
                : d.status === 'pending_review'
                    ? `<button class="btn btn-warning btn-sm" onclick="loadPreview(${d.doc_id}, true)">👁️ 預覽並確認</button>`
                    : '';
            const canDelete = !['pending', 'processing'].includes(d.status);
            const deleteBtn = canDelete
                ? `<button class="btn btn-ghost btn-sm" style="color:var(--danger)" onclick="deleteDocument(${d.doc_id}, '${d.file_name.replace(/'/g, "\\'")}')">🗑️ 刪除</button>`
                : '';
            const actions = [previewBtn, deleteBtn].filter(Boolean).join(' ') || '—';
            return `
      <tr>
        <td>${d.doc_id}</td>
        <td>${d.file_name}</td>
        <td>${d.trainer_id}</td>
        <td><span class="status-${d.status}">${statusLabel(d.status)}</span></td>
        <td style="white-space:nowrap">${actions}</td>
      </tr>`;
        }).join('');
    } catch (e) {
        toast('載入文件列表失敗', 'error');
    }
}

function statusLabel(s) {
    return {
        pending: '⏳ 等待中',
        processing: '⚙️ 處理中',
        pending_review: '👁️ 待確認',
        done: '✅ 完成',
        failed: '❌ 失敗'
    }[s] || s;
}

// ── Polling ────────────────────────────────────────────────────────────────
function startPolling(docId) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
        try {
            const doc = await apiGet(`/documents/${docId}`);
            await loadDocuments();
            if (doc.status === 'pending_review') {
                toast('👁️ AI 粉碎完成！請預覽確認後再發布', 'info', 6000);
                clearInterval(pollTimer);
                await loadPreview(docId, true);
            } else if (doc.status === 'failed') {
                toast('❌ 粉碎失敗：' + (doc.error_message || ''), 'error');
                clearInterval(pollTimer);
            }
        } catch { /* ignore */ }
    }, 4000);
}

// ── Split Screen Preview ───────────────────────────────────────────────────
async function loadPreview(docId, pendingReview = false) {
    previewDocId = docId;
    try {
        const [doc, modules] = await Promise.all([
            apiGet(`/documents/${docId}`),
            apiGet(`/modules?doc_id=${docId}`),
        ]);

        // 顯示原始文字
        document.getElementById('raw-text').textContent =
            doc.status === 'done' || doc.status === 'pending_review'
                ? (doc.raw_text || '（原始文字未儲存）')
                : '（尚未完成）';

        // 顯示模組
        const container = document.getElementById('modules-output');
        if (!modules.length) {
            container.innerHTML = '<p style="color:var(--muted)">尚無模組</p>';
            return;
        }

        const domainNames = allDomains
            .filter(d => modules.some(() => true))  // 稍後可細化
            .map(d => `<span class="badge badge-blue">#${d.domain_name}</span>`)
            .join(' ');

        container.innerHTML = modules.map((m, i) => `
      <div class="module-card" id="mc-${m.module_id}">
        <div class="mc-header" onclick="toggleModule(${m.module_id})">
          <span>模組 ${i + 1}：${m.module_title}</span>
          <span class="badge badge-gray">${m.reading_time_minutes} min</span>
        </div>
        <div class="mc-body">
          <p>${m.module_content}</p>
          ${m.quiz_question ? `
          <div class="mc-quiz">
            <strong>📝 測驗：</strong>${m.quiz_question}
            <div class="options" id="opts-${m.module_id}">
              ${(m.quiz_options || []).map((opt, idx) => {
            const key = ['A', 'B', 'C', 'D'][idx];
            return `<div class="option" style="cursor:pointer"
                  onclick="checkPreviewAnswer(${m.module_id}, '${key}', '${m.quiz_answer}')"
                >${opt}</div>`;
        }).join('')}
            </div>
            <small id="ans-${m.module_id}" style="color:var(--muted);margin-top:.5rem;display:block">
              點擊選項查看答案
            </small>
          </div>` : ''}
        </div>
      </div>
    `).join('');

        // 確認發布 Bar
        const bar = document.getElementById('confirm-bar');
        if (pendingReview) {
            document.getElementById('confirm-doc-name').textContent = doc.file_name;
            bar.style.display = 'flex';
        } else {
            bar.style.display = 'none';
        }

        // 捲動至預覽區
        document.getElementById('preview-section').scrollIntoView({ behavior: 'smooth' });
    } catch (e) {
        toast('載入預覽失敗：' + e.message, 'error');
    }
}

function toggleModule(id) {
    document.getElementById(`mc-${id}`).classList.toggle('open');
}

function checkPreviewAnswer(moduleId, chosen, correct) {
    const opts = document.querySelectorAll(`#opts-${moduleId} .option`);
    opts.forEach((el, idx) => {
        const key = ['A', 'B', 'C', 'D'][idx];
        el.style.cursor = 'default';
        el.onclick = null;
        if (key === correct) {
            el.style.background = '#dcfce7';
            el.style.borderColor = 'var(--success)';
            el.style.fontWeight = '600';
        } else if (key === chosen) {
            el.style.background = '#fee2e2';
            el.style.borderColor = 'var(--danger)';
        }
    });
    const label = document.getElementById(`ans-${moduleId}`);
    if (label) {
        label.textContent = chosen === correct
            ? `✅ 正確！答案是 ${correct}`
            : `❌ 答錯了，正確答案是 ${correct}`;
        label.style.color = chosen === correct ? 'var(--success)' : 'var(--danger)';
        label.style.fontWeight = '600';
    }
}

// ── Confirm / Reject / Delete Document ────────────────────────────────────
async function confirmDocument() {
    if (!previewDocId) return;
    try {
        await apiPost(`/documents/${previewDocId}/confirm`, {});
        toast('✅ 文件已發布！學習者現在可以開始學習', 'success');
        document.getElementById('confirm-bar').style.display = 'none';
        await loadDocuments();
    } catch (e) {
        toast('確認失敗：' + e.message, 'error');
    }
}

async function rejectDocument() {
    const fileName = document.getElementById('confirm-doc-name').textContent;
    if (!confirm(`確定不發布並刪除文件「${fileName}」？\n此操作無法復原。`)) return;
    await _doDeleteDocument(previewDocId);
}

async function deleteDocument(docId, fileName) {
    if (!confirm(`確定要刪除文件「${fileName}」？\n相關模組與學習紀錄將一併刪除，此操作無法復原。`)) return;
    await _doDeleteDocument(docId);
}

async function _doDeleteDocument(docId) {
    try {
        await apiDelete(`/documents/${docId}`);
        toast('🗑️ 文件已刪除', 'info');
        if (previewDocId === docId) {
            previewDocId = null;
            document.getElementById('raw-text').textContent = '點擊文件列表中的「預覽模組」';
            document.getElementById('raw-text').style.color = 'var(--muted)';
            document.getElementById('modules-output').innerHTML = '<p style="color:var(--muted)">尚未選擇文件</p>';
            document.getElementById('confirm-bar').style.display = 'none';
        }
        await loadDocuments();
    } catch (e) {
        toast('刪除失敗：' + e.message, 'error');
    }
}
