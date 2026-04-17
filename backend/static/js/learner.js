// ── State ──────────────────────────────────────────────────────────────────
const USER_ID = 'demo_user';   // 真實系統應由登入取得
let queue = [];
let currentIdx = 0;
let answered = false;
let selectedDocId = null;    // null = 全部文件
let selectedDomainId = null; // null = 全部領域

// ── Init ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    await loadFilters();
    await loadProgress();
    await loadQueue();
    await loadStats();  // 學習報告（背景載入，不阻塞主流程）
});

// ── Filters ───────────────────────────────────────────────────────────────────
async function loadFilters() {
    try {
        const [docs, domains] = await Promise.all([
            apiGet('/documents'),
            apiGet('/domains'),
        ]);
        console.log('[filter] docs:', docs, 'domains:', domains);

        // 領域下拉
        const domainSel = document.getElementById('domain-filter');
        domainSel.innerHTML =
            '<option value="">全部領域</option>' +
            domains.map(d => `<option value="${d.domain_id}">#${d.domain_name}</option>`).join('');
        domainSel.addEventListener('change', () => {
            selectedDomainId = domainSel.value ? parseInt(domainSel.value) : null;
            // 選定領域時清除文件篩選
            const docSel = document.getElementById('doc-filter');
            docSel.value = '';
            selectedDocId = null;
            loadQueue();
        });

        // 文件下拉（只顯示 done）
        const doneDocs = docs.filter(d => d.status === 'done');
        const docSel = document.getElementById('doc-filter');
        docSel.innerHTML =
            '<option value="">全部文件</option>' +
            doneDocs.map(d => `<option value="${d.doc_id}">${d.file_name}</option>`).join('');
        docSel.addEventListener('change', () => {
            selectedDocId = docSel.value ? parseInt(docSel.value) : null;
            // 選定文件時清除領域篩選
            const domSel = document.getElementById('domain-filter');
            domSel.value = '';
            selectedDomainId = null;
            loadQueue();
        });
    } catch (e) {
        console.error('[filter] 錯誤：', e);
        toast('載入篩選選項失敗：' + e.message, 'error');
    }
}

// ── Progress Summary ───────────────────────────────────────────────────────
async function loadProgress() {
    try {
        const p = await apiGet(`/learning/progress/${USER_ID}`);
        document.getElementById('total-seen').textContent = p.total_modules_seen;
        document.getElementById('due-today').textContent = p.modules_due_today;
        document.getElementById('avg-score').textContent = (p.average_score * 100).toFixed(0) + '%';
    } catch { /* ignore if no progress yet */ }
}

// ── Learning Queue ─────────────────────────────────────────────────────────
async function loadQueue() {
    try {
        const params = new URLSearchParams({ limit: 10 });
        if (selectedDocId) params.set('doc_id', selectedDocId);
        if (selectedDomainId) params.set('domain_id', selectedDomainId);
        queue = await apiGet(`/learning/queue/${USER_ID}?${params}`);
        currentIdx = 0;
        if (!queue.length) {
            document.getElementById('learn-area').innerHTML =
                `<div class="card" style="text-align:center;padding:3rem">
          <p style="font-size:1.5rem">🎉</p>
          <p style="font-weight:600;margin-top:.5rem">今日學習已全部完成！</p>
          <p style="color:var(--muted);font-size:.875rem;margin-top:.3rem">明天再來複習下一批</p>          <button class="btn btn-ghost" style="margin-top:1rem" onclick="retryQueue()">🔁 立刻重新練習一次</button>        </div>`;
            return;
        }
        updateProgressBar();
        renderModule(queue[currentIdx]);
    } catch (e) {
        toast('載入學習佇列失敗：' + e.message, 'error');
    }
}

// ── Progress Bar ───────────────────────────────────────────────────────────
function updateProgressBar() {
    const pct = queue.length ? Math.round((currentIdx / queue.length) * 100) : 0;
    document.getElementById('progress-bar').style.width = pct + '%';
    document.getElementById('progress-text').textContent =
        `${currentIdx} / ${queue.length} 完成`;
}

// ── Render Module ──────────────────────────────────────────────────────────
function renderModule(m) {
    answered = false;
    const area = document.getElementById('learn-area');
    area.innerHTML = `
    <div class="card learn-module">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
        <span class="badge badge-blue">模組 ${currentIdx + 1} / ${queue.length}</span>
        <span class="badge badge-gray">⏱ ${m.reading_time_minutes} 分鐘</span>
      </div>

      <h2 style="font-size:1.1rem;margin-bottom:.75rem">${m.module_title}</h2>
      <p style="font-size:.9rem;line-height:1.8;color:var(--text)">${m.module_content}</p>

      ${m.quiz_question ? `
      <hr style="margin:1.25rem 0;border:none;border-top:1px solid var(--border)">
      <p style="font-weight:600;margin-bottom:.25rem">📝 測驗</p>
      <p style="font-size:.9rem">${m.quiz_question}</p>
      <div class="quiz-options" id="quiz-options">
        ${(m.quiz_options || []).map((opt, i) => `
          <button class="quiz-option" data-key="${['A', 'B', 'C', 'D'][i]}"
            onclick="submitAnswer(${m.module_id}, '${['A', 'B', 'C', 'D'][i]}', '${m.quiz_answer}')">
            ${opt}
          </button>
        `).join('')}
      </div>
      <div id="quiz-feedback" style="margin-top:.75rem;font-size:.875rem"></div>
      ` : `
      <div style="margin-top:1.5rem;text-align:right">
        <button class="btn btn-primary" onclick="nextModule()">下一個 →</button>
      </div>
      `}
    </div>
  `;
}

// ── Submit Answer ──────────────────────────────────────────────────────────
async function submitAnswer(moduleId, chosen, correctAnswer) {
    if (answered) return;
    answered = true;

    // 鎖定所有按鈕
    document.querySelectorAll('.quiz-option').forEach(btn => {
        btn.onclick = null;
        btn.style.cursor = 'default';
    });

    // 視覺回饋
    document.querySelectorAll('.quiz-option').forEach(btn => {
        if (btn.dataset.key === correctAnswer) btn.classList.add('correct');
        else if (btn.dataset.key === chosen) btn.classList.add('wrong');
    });

    try {
        const result = await apiPost(`/learning/submit/${USER_ID}/${moduleId}`, { answer: chosen });
        const fb = document.getElementById('quiz-feedback');
        if (result.correct) {
            fb.innerHTML = `<span style="color:var(--success);font-weight:600">✅ 答對了！下次複習：${result.next_review_days} 天後</span>`;
        } else {
            fb.innerHTML = `<span style="color:var(--danger);font-weight:600">❌ 答錯了，正確答案是 ${result.correct_answer}。明天再複習一次。</span>`;
        }
        fb.innerHTML += `<div style="margin-top:.75rem;text-align:right">
      <button class="btn btn-primary" onclick="nextModule()">下一個 →</button>
    </div>`;
        await loadProgress();
    } catch (e) {
        toast('提交失敗：' + e.message, 'error');
    }
}

// ── Next Module ────────────────────────────────────────────────────────────
function nextModule() {
    currentIdx++;
    updateProgressBar();
    if (currentIdx >= queue.length) {
        document.getElementById('learn-area').innerHTML = `
      <div class="card" style="text-align:center;padding:3rem">
        <p style="font-size:1.5rem">🎉</p>
        <p style="font-weight:600;margin-top:.5rem">今日所有模組學習完畢！</p>
        <p style="color:var(--muted);font-size:.875rem;margin-top:.4rem">SM-2 已安排下次複習時間</p>
        <div style="display:flex;gap:.75rem;justify-content:center;margin-top:1rem">
          <button class="btn btn-ghost" onclick="retryQueue()">🔁 立即重新練習</button>
          <button class="btn btn-primary" onclick="loadQueue()">重新整理佇列</button>
        </div>
      </div>`;
        return;
    }
    renderModule(queue[currentIdx]);
}

// ── Retry Queue ────────────────────────────────────────────────────────────
async function retryQueue() {
    try {
        const params = new URLSearchParams({ limit: 10 });
        if (selectedDocId) params.set('doc_id', selectedDocId);
        if (selectedDomainId) params.set('domain_id', selectedDomainId);
        queue = await apiPost(`/learning/retry/${USER_ID}?${params}`, {});
        currentIdx = 0;
        if (!queue.length) {
            toast('此範圍目前沒有模組可以練習', 'info');
            return;
        }
        toast(`🔁 已重設 ${queue.length} 個模組，開始練習！`, 'success');
        updateProgressBar();
        renderModule(queue[currentIdx]);
    } catch (e) {
        toast('重新練習失敗：' + e.message, 'error');
    }
}

// ── Learning Stats ─────────────────────────────────────────────────────────
async function loadStats() {
    try {
        const s = await apiGet(`/learning/stats/${USER_ID}`);

        // 沒有任何答題紀錄時隱藏整個報告區
        const hasData = s.daily_trend.some(d => d.total > 0);
        const section = document.getElementById('stats-section');
        if (!hasData) { section.style.display = 'none'; return; }
        section.style.display = '';

        // 連續學習天數
        const badge = document.getElementById('streak-badge');
        badge.textContent = s.streak_days > 0 ? `🔥 連續 ${s.streak_days} 天` : '';

        // 折線圖
        drawTrendChart(s.daily_trend);

        // 各領域正確率 bar
        const barsEl = document.getElementById('domain-bars');
        if (!s.domain_accuracy.length) {
            barsEl.innerHTML = '<span style="color:var(--muted);font-size:.85rem">尚無領域資料</span>';
        } else {
            barsEl.innerHTML = s.domain_accuracy.map(d => {
                const pct = Math.round(d.accuracy * 100);
                const color = pct >= 80 ? 'var(--success)' : pct >= 60 ? 'var(--warning)' : 'var(--danger)';
                return `
                <div style="margin-bottom:.6rem">
                  <div style="display:flex;justify-content:space-between;font-size:.825rem;margin-bottom:.2rem">
                    <span>#${d.domain_name}</span>
                    <span style="color:${color};font-weight:600">${pct}% (${d.correct}/${d.total})</span>
                  </div>
                  <div style="background:var(--border);border-radius:999px;height:6px">
                    <div style="background:${color};width:${pct}%;height:6px;border-radius:999px;transition:width .4s"></div>
                  </div>
                </div>`;
            }).join('');
        }

        // 最難模組表格
        const tbody = document.querySelector('#hard-table tbody');
        if (!s.hardest_modules.length) {
            tbody.innerHTML = '<tr><td colspan="3" style="color:var(--muted);text-align:center;padding:.5rem">尚無資料</td></tr>';
        } else {
            tbody.innerHTML = s.hardest_modules.map(m => {
                const pct = Math.round(m.accuracy * 100);
                const color = pct >= 80 ? 'var(--success)' : pct >= 60 ? 'var(--warning)' : 'var(--danger)';
                return `<tr style="border-bottom:1px solid var(--border)">
                  <td style="padding:.4rem .5rem">${m.title}</td>
                  <td style="text-align:center;padding:.4rem .5rem">${m.attempts}</td>
                  <td style="text-align:center;padding:.4rem .5rem;color:${color};font-weight:600">${pct}%</td>
                </tr>`;
            }).join('');
        }
    } catch (e) {
        // 靜默失敗：統計不影響主要學習流程
        console.warn('[stats] 載入失敗：', e.message);
    }
}

function drawTrendChart(dailyTrend) {
    const canvas = document.getElementById('trend-chart');
    if (!canvas) return;
    // 讓 canvas 寬度跟隨父元素
    canvas.width = canvas.offsetWidth || 600;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const PAD = { top: 10, right: 10, bottom: 28, left: 28 };
    const chartW = W - PAD.left - PAD.right;
    const chartH = H - PAD.top - PAD.bottom;

    ctx.clearRect(0, 0, W, H);

    const maxVal = Math.max(...dailyTrend.map(d => d.total), 1);
    const n = dailyTrend.length;
    const stepX = chartW / (n - 1 || 1);

    const xOf = i => PAD.left + i * stepX;
    const yOf = v => PAD.top + chartH - (v / maxVal) * chartH;

    // 格線
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    [0, 0.25, 0.5, 0.75, 1].forEach(r => {
        const y = PAD.top + chartH * r;
        ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(W - PAD.right, y); ctx.stroke();
    });

    // 答對（綠色填充）
    ctx.beginPath();
    ctx.moveTo(xOf(0), yOf(dailyTrend[0].correct));
    dailyTrend.forEach((d, i) => ctx.lineTo(xOf(i), yOf(d.correct)));
    ctx.lineTo(xOf(n - 1), yOf(0)); ctx.lineTo(xOf(0), yOf(0)); ctx.closePath();
    ctx.fillStyle = 'rgba(22,163,74,.15)';
    ctx.fill();

    // 總答題（藍色線）
    ctx.beginPath();
    ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 2;
    dailyTrend.forEach((d, i) => i === 0 ? ctx.moveTo(xOf(i), yOf(d.total)) : ctx.lineTo(xOf(i), yOf(d.total)));
    ctx.stroke();

    // 答對（綠色線）
    ctx.beginPath();
    ctx.strokeStyle = '#16a34a'; ctx.lineWidth = 2;
    dailyTrend.forEach((d, i) => i === 0 ? ctx.moveTo(xOf(i), yOf(d.correct)) : ctx.lineTo(xOf(i), yOf(d.correct)));
    ctx.stroke();

    // X 軸日期標籤（每 7 天一個）
    ctx.fillStyle = '#64748b'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
    dailyTrend.forEach((d, i) => {
        if (i % 7 === 0 || i === n - 1) {
            const label = d.date.slice(5); // MM-DD
            ctx.fillText(label, xOf(i), H - 6);
        }
    });

    // 圖例
    ctx.textAlign = 'left'; ctx.font = '11px sans-serif';
    ctx.fillStyle = '#2563eb'; ctx.fillRect(PAD.left, 4, 10, 4);
    ctx.fillStyle = '#1e293b'; ctx.fillText('總答題', PAD.left + 14, 10);
    ctx.fillStyle = '#16a34a'; ctx.fillRect(PAD.left + 65, 4, 10, 4);
    ctx.fillStyle = '#1e293b'; ctx.fillText('答對', PAD.left + 79, 10);
}
