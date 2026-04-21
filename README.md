# Knowledge Shredder — 知識粉碎機

> 本項目為2026 KGI 凱基金控 MA Project
> 上傳訓練文件，由 AI 自動切割成「2 分鐘微學習模組」，並以間隔重複演算法（SM-2）驅動個人化複習排程。

---

## 目錄

1. [專案簡介](#專案簡介)
2. [整體架構](#整體架構)
3. [技術棧](#技術棧)
4. [目錄結構](#目錄結構)
5. [資料庫結構](#資料庫結構)
6. [API 路由總覽](#api-路由總覽)
7. [核心服務說明](#核心服務說明)
8. [快速啟動](#快速啟動)
9. [環境變數](#環境變數)

---

## 專案簡介

Knowledge Shredder（知識粉碎機）專為金融服務業設計，解決訓練材料龐大、員工難以消化的問題。  
流程如下：

1. **訓練者（Trainer）** 上傳 PDF / Word / TXT 格式的文件，並標記所屬知識領域。
2. **LLM** 自動將文件「粉碎」成數個 2 分鐘可讀的微模組，每個模組附帶一道四選一測驗題。
3. **學習者（Learner）** 依照 SM-2 間隔重複演算法排定的複習佇列，每天完成學習並作答測驗。
4. 系統根據作答表現，動態調整下次複習時間，確保遺忘曲線最佳化。

---

## 整體架構

```
┌─────────────────────────────────────────────────────┐
│                  瀏覽器前端 (Static HTML/JS)          │
│   trainer.html（訓練者介面）  learner.html（學習者介面）  │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP REST API
┌─────────────────▼───────────────────────────────────┐
│               FastAPI 應用程式                        │
│  /documents  /domains  /modules  /learning           │
└─────────────────────────────────────────────────────┘
                           │
                           ▼ 文件粉碎（同步，於 API 程序內執行）
                   ┌──────────────────────────┐
                   │   LLM Provider（可插拔）  │
                   │   azure_openai / openai  │
                   │   gemini / ...           │
                   └──────────────────────────┘
                   ┌──────────────────────────┐
                   │   SQLite (Async)         │
                   │   所有業務資料持久化       │
                   └──────────────────────────┘
```

---

## 技術棧

| 分類 | 技術 |
|------|------|
| Web 框架 | FastAPI 0.115 + Uvicorn |
| 資料庫 ORM | SQLAlchemy 2.0（asyncio）+ aiosqlite |
| 資料驗證 | Pydantic 2.9 |
| LLM | 多 Provider 可插拔設計（`openai` SDK 1.51），目前實作 Azure OpenAI |
| 文件解析 | pdfplumber（PDF）、python-docx（Word）|
| 前端 | 原生 HTML / CSS / JavaScript |

---

## 目錄結構

```
Knowledge-Shredder/
├── requirements.txt            
├── backend/
│   ├── .env                    # 環境變數（不納入版控）
│   └── src/
│       ├── main.py             # FastAPI 應用入口
│       ├── database.py         # 非同步資料庫引擎與 Session
│       ├── config.py           # Pydantic Settings（環境變數載入）
│       ├── api/
│       │   └── routes/
│       │       ├── documents.py    # 文件上傳與查詢
│       │       ├── domains.py      # 知識領域
│       │       ├── modules.py      # 微模組查詢
│       │       └── learning.py     # 學習佇列、測驗提交、統計
│       ├── models/
│       │   ├── db.py           # SQLAlchemy ORM 模型（資料表定義）
│       │   └── schemas.py      # Pydantic Request / Response Schema
│       ├── services/
│       │   ├── content_filter.py   # Prompt Injection 偵測與文字清理
│       │   ├── document_parser.py  # PDF / DOCX / TXT 文字擷取
│       │   ├── spaced_repetition.py # SM-2 間隔重複演算法
│       │   └── llm/
│       │       ├── base.py         # LLM 抽象介面
│       │       ├── factory.py      # 依設定選擇 LLM 供應商
│       │       ├── aoai_provider.py # Azure OpenAI 實作
│       │       └── prompts/
│       │           ├── system.txt  # LLM System Prompt
│       │           └── user.txt    # LLM User Prompt 模板

└── static/
    ├── trainer.html            # 訓練者介面
    ├── learner.html            # 學習者介面
    ├── css/style.css
    └── js/
        ├── api.js              # API 呼叫封裝
        ├── trainer.js
        └── learner.js
```

---

## 資料庫結構

使用 **SQLite**（透過 aiosqlite 非同步驅動），開發環境無需額外安裝資料庫服務。  
ORM 採用 SQLAlchemy 2.0，所有資料表在應用啟動時由 `init_db()` 自動建立。

### ER 關係圖

```
knowledge_domains ─────┐
       │ 1             │
       │               │
       ▼ N             │
document_domain_map ◄──┘
       │ N
       │
       ▼ 1
source_documents
       │ 1
       │
       ▼ N
micro_modules
       │ 1
       │
       ├──► N  user_progress  (1 per user per module)
       │
       └──► N  quiz_attempts  (每次作答一筆)
```

---

### 資料表說明

#### `knowledge_domains` — 知識領域字典

管理訓練內容的分類標籤（例如：保險法規、投資理財、合規稽核）。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `domain_id` | INTEGER PK | 自動遞增主鍵 |
| `domain_name` | VARCHAR(100) UNIQUE | 領域名稱，不可重複 |
| `description` | TEXT | 領域描述（可為空） |
| `created_at` | DATETIME | 建立時間（UTC） |

---

#### `source_documents` — 原始訓練文件

儲存訓練者上傳的文件基本資訊與 AI 處理狀態。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `doc_id` | INTEGER PK | 自動遞增主鍵 |
| `trainer_id` | VARCHAR(100) | 上傳者 ID |
| `file_name` | VARCHAR(255) | 原始檔案名稱 |
| `raw_text` | TEXT | 擷取的純文字內容 |
| `upload_timestamp` | DATETIME | 上傳時間（UTC） |
| `status` | VARCHAR(20) | 處理狀態：`pending` → `processing` → `done` \| `failed` |
| `error_message` | TEXT | 失敗原因（可為空） |

---

#### `document_domain_map` — 文件與領域多對多關聯

一份文件可屬於多個知識領域，一個領域也可包含多份文件。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `map_id` | INTEGER PK | 自動遞增主鍵 |
| `doc_id` | INTEGER FK | 參照 `source_documents.doc_id`（CASCADE DELETE）|
| `domain_id` | INTEGER FK | 參照 `knowledge_domains.domain_id`（CASCADE DELETE）|

> 唯一約束：`(doc_id, domain_id)` 組合不可重複。

---

#### `micro_modules` — AI 生成的微模組

由 LLM 從原始文件切割出的最小學習單元，每個模組約 2 分鐘閱讀時間並附帶測驗題。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `module_id` | INTEGER PK | 自動遞增主鍵 |
| `doc_id` | INTEGER FK | 來源文件（CASCADE DELETE）|
| `module_title` | VARCHAR(200) | 模組標題（最多 15 字） |
| `module_content` | TEXT | 學習內容正文 |
| `quiz_question` | TEXT | 測驗題目 |
| `quiz_options` | JSON | 四個選項，格式：`["A) ...", "B) ...", "C) ...", "D) ..."]` |
| `quiz_answer` | VARCHAR(10) | 正確答案代號（`A` \| `B` \| `C` \| `D`） |
| `reading_time_minutes` | FLOAT | 預估閱讀時間（分鐘，預設 2.0）|
| `created_at` | DATETIME | 建立時間（UTC） |

---

#### `user_progress` — 學習者進度（SM-2 間隔重複）

記錄每位學習者對每個微模組的複習狀態，支援 SM-2 間隔重複演算法。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `progress_id` | INTEGER PK | 自動遞增主鍵 |
| `user_id` | VARCHAR(100) | 學習者 ID |
| `module_id` | INTEGER FK | 對應微模組（CASCADE DELETE）|
| `ease_factor` | FLOAT | SM-2 難易係數（初始 2.5，下限 1.3）|
| `interval_days` | INTEGER | 下次複習間隔天數（初始 1）|
| `next_review` | DATETIME | 下次應複習時間 |
| `repetitions` | INTEGER | 累計連續答對次數 |
| `last_score` | FLOAT | 最近一次得分（0.0 ~ 1.0）|
| `last_reviewed_at` | DATETIME | 最近一次複習時間 |

> 唯一約束：`(user_id, module_id)` 組合不可重複（每人每模組只有一筆進度）。

---

#### `quiz_attempts` — 答題歷史

每次作答皆記錄一筆，用於統計連續學習天數、每日趨勢、各領域正確率等報表。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `attempt_id` | INTEGER PK | 自動遞增主鍵 |
| `user_id` | VARCHAR(100) | 學習者 ID（已建立索引）|
| `module_id` | INTEGER FK | 對應微模組（CASCADE DELETE）|
| `chosen_answer` | VARCHAR(10) | 學習者選擇的答案 |
| `correct_answer` | VARCHAR(10) | 正確答案 |
| `is_correct` | INTEGER | 是否答對（1 = 正確，0 = 錯誤）|
| `answered_at` | DATETIME | 作答時間（UTC）|

---

## API 路由總覽

互動式 API 文件可在啟動後訪問：`http://localhost:8000/docs`

### 知識領域 `/domains`

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/domains` | 列出所有知識領域 |
| POST | `/domains` | 建立新領域 |
| PUT | `/domains/{domain_id}` | 更新領域名稱/描述 |
| DELETE | `/domains/{domain_id}` | 刪除領域（連帶刪除關聯資料）|

### 文件管理 `/documents`

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/documents/upload` | 上傳文件並觸發 AI 切割（multipart/form-data）|
| GET | `/documents` | 列出所有文件（不含原始文字）|
| GET | `/documents/{doc_id}` | 取得單一文件詳情（含原始文字）|

### 微模組 `/modules`

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/modules` | 列出微模組（可依 `domain_id` 或 `doc_id` 篩選）|
| GET | `/modules/{module_id}` | 取得單一微模組詳情 |

### 學習功能 `/learning`

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/learning/queue/{user_id}` | 取得今日複習佇列（優先到期模組，再補充新模組）|
| POST | `/learning/submit/{user_id}/{module_id}` | 提交測驗答案，更新 SM-2 排程 |
| GET | `/learning/progress/{user_id}` | 取得學習者整體進度摘要 |
| GET | `/learning/stats/{user_id}` | 取得統計數據（連續學習天數、每日趨勢、領域正確率、最難模組 Top 5）|

---

## 核心服務說明

### 1. 文件解析器（`document_parser.py`）

支援 PDF、DOCX/DOC、TXT 三種格式。  
擷取後會驗證文字品質：
- 內容少於 50 字元 → 拒絕（可能是掃描圖片 PDF）
- 可讀字元比例低於 50% → 拒絕（可能是亂碼或非標準字型嵌入）

### 2. LLM 供應商（`services/llm/`）

採用**抽象工廠模式**設計，透過 `LLM_PROVIDER` 環境變數在執行期選擇供應商，主程式碼無需修改。

| `LLM_PROVIDER` 值 | 說明 |
|-------------------|------|
| `azure_openai` | Azure OpenAI（目前已實作）|
| `openai` | 標準 OpenAI API（預留擴充點）|
| `anthropic` | Anthropic Claude（預留擴充點）|

新增供應商只需三步驟：
1. 在 `services/llm/` 下建立新 Provider 檔案，繼承 `BaseLLMProvider` 並實作 `shred_document()` 方法。
2. 在 `factory.py` 的 `get_llm_provider()` 加入對應的 `if` 分支。
3. 在 `.env` 中更新 `LLM_PROVIDER` 設定值。

LLM 的 System Prompt 要求模型以繁體中文輸出，並嚴格遵守 JSON 格式。  
User Prompt 模板支援動態注入 `{domains}` 與 `{raw_text}`。

### 3. SM-2 間隔重複演算法（`spaced_repetition.py`）

實作 SuperMemo SM-2 演算法：

| 作答結果 | 說明 |
|----------|------|
| 答對（score ≥ 0.6） | 依 EF 值計算下次間隔（1 → 6 → `前次間隔 × EF`）|
| 答錯（score < 0.6） | 重置連續答對次數，間隔歸 1 天 |

難易係數（EF）更新公式：
$$EF_{new} = EF + (0.1 - (5-q) \times (0.08 + (5-q) \times 0.02))$$

其中 $q$ 為得分映射至 0–5 量表的值，EF 下限為 1.3。

### 4. 安全防護（`content_filter.py`）

在文件文字進入 LLM 前，以正規表達式偵測常見的 Prompt Injection 攻擊模式，包括：
- `ignore all previous instructions`
- `disregard your guidelines`
- `<system>` / `<prompt>` 等特殊標籤注入
- `jailbreak` 關鍵字

超過 80,000 字元的文件會自動截斷，避免超出 Token 上限。

---

## 快速啟動

### 前置需求

- 任一支援的 LLM 服務帳號（Azure OpenAI、OpenAI等）

### 步驟

```bash
# 1. 複製專案
git clone https://github.com/Kris0214/Knowledge-Shredder.git
cd Knowledge-Shredder
pip install -r requirements.txt

# 2. 建立環境變數檔
cp backend/.env
# 編輯 backend/.env，填入 LLM 金鑰與 LLM_PROVIDER 設定

# 3. 啟動 API 伺服器
cd backend
uvicorn src.main:app --reload --port 8000

# 4. 開啟瀏覽器
# 訓練者介面：http://localhost:8000/static/trainer.html
# 學習者介面：http://localhost:8000/static/learner.html
# API 文件：  http://localhost:8000/docs
```

## 環境變數
可視自己的LLM接口新增變數

| 變數名稱 | 必填 | 預設值 | 說明 |
|----------|------|--------|------|
| `APP_ENV` | 否 | `development` | 環境識別（`development` \| `production`）|
| `DATABASE_URL` | 否 | `sqlite+aiosqlite:///./knowledge.db` | 資料庫連線字串 |
| `AZURE_OPENAI_ENDPOINT` | 是 | — | Azure OpenAI 端點 URL |
| `AZURE_OPENAI_API_KEY` | 是 | — | Azure OpenAI API 金鑰 |
| `AZURE_OPENAI_DEPLOYMENT` | 是 | — | 部署名稱（例如：`gpt-4o`）|
| `AZURE_OPENAI_API_VERSION` | 否 | `2024-08-01-preview` | API 版本 |
| `LLM_PROVIDER` | 否 | `aoai` | LLM 供應商識別碼 |
| `UPLOAD_MAX_SIZE_MB` | 否 | `20` | 上傳檔案大小上限（MB）|
