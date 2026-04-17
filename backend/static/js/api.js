// ── Config ─────────────────────────────────────────────────────────────────
const API = '';   // 同源，FastAPI 在同一個 origin

// ── Toast ──────────────────────────────────────────────────────────────────
function toast(msg, type = 'info', duration = 3500) {
    const c = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    c.appendChild(el);
    setTimeout(() => el.remove(), duration);
}

// ── HTTP helpers ───────────────────────────────────────────────────────────

/** 安全解析錯誤回應：先嘗試 JSON，失回 status text */
async function _errorMsg(r) {
    try {
        const data = await r.json();
        return data.detail || JSON.stringify(data);
    } catch {
        const text = await r.text().catch(() => '');
        return text || `HTTP ${r.status} ${r.statusText}`;
    }
}

async function apiGet(path) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(await _errorMsg(r));
    return r.json();
}

async function apiPost(path, body) {
    const r = await fetch(API + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await _errorMsg(r));
    return r.json();
}

async function apiPostForm(path, formData) {
    const r = await fetch(API + path, { method: 'POST', body: formData });
    if (!r.ok) throw new Error(await _errorMsg(r));
    return r.json();
}

async function apiDelete(path) {
    const r = await fetch(API + path, { method: 'DELETE' });
    if (!r.ok && r.status !== 204) throw new Error(await _errorMsg(r));
}
