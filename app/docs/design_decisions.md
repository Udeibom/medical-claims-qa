# Design decisions — Medical Claims Extraction & QA Service

> Short document summarising the main architecture and implementation choices, trade-offs, and rationale for this task.

---

# Overview
This service accepts a PDF or image of a medical claim, runs OCR, extracts structured fields (patient, diagnoses, medications, procedures, admission, total_amount), stores the parsed JSON in memory keyed by a `document_id`, and provides a QA endpoint (`/ask`) that answers natural language questions about the parsed document.

The implementation prioritises a pragmatic, auditable, and reproducible approach suitable for this kind of task: deterministic, testable regex/heuristic extraction with an optional mock-LLM fallback behind a config flag.

---

# Extraction strategy — "regex first"
**Choice:** I used deterministic regexes and heuristics to extract fields from cleaned OCR text as the primary extraction mechanism.

**Why:**
- Predictability and auditability — every extracted token is traceable to a regex or heuristic.
- Easier to test with unit tests and to debug when extraction fails.
- Low infra footprint — no external LLM API required by default.

**How it works:**
1. OCR → normalized text (line trimming, de-duplication of blank lines).
2. Pre-clean lines to remove common boilerplate (headers, invoice columns, vendor footers).
3. Section detection using heading variants (e.g., `Diagnosis`, `Medications`, `TREATMENTS`) and line-level parsing within sections.
4. Conservative heuristics to avoid false positives (e.g., require med names to include letters, strip trailing numeric invoice columns from procedure names).

**Tradeoffs / limitations:**
- Regexes are brittle for extreme layout variability, also vendor-specific templates may still fail.
- OCR noise can break label detection (missing headings, line breaks in awkward places).
- This approach favours precision over recall: it will often return fewer items but with higher confidence.

---

# Mock-LLM fallback (configurable)
**Choice:** keep a *mock* LLM fallback for demo purposes and put any real LLM calls strictly behind config flags.

**Rationale:**
- The assignment requested LLM-like behaviour optionally; for safety, the code contains a mock LLM component that uses simple heuristics to produce reasonable defaults without external calls.
- Real LLMs introduce cost, latency, and dependency concerns; they also complicate reproducibility for reviewers.

**Configuration:**
- `USE_LLM_EXTRACTION` (bool) — when `True`, if regex extraction returns empty, call the fallback `_extract_with_llm()` (mock).
- `USE_LLM_QA` (bool) — when `True`, QA endpoint will use mock LLM reasoning if structured answers are not found.

**Notes:**
- Mock LLM is deterministic and local; if integrating a real LLM later, do so behind these flags and add opt-in environment variables (API keys, timeouts, rate limits).

---

# OCR choices
**Libraries used:**
- `pdfplumber` for extracting page text from PDFs and for extracting embedded images where text extraction fails.
- `pytesseract` (Tesseract) for image OCR and for OCR of PDF page images when needed.
- `Pillow` (PIL) for image handling.

**Why these:**
- They are OSS, widely available, and easy to install for reviewers.
- `pdfplumber` extracts text directly from PDFs when textual content exists (faster and more reliable than image OCR).
- `pytesseract` is a reasonable local OCR solution for scanned documents in a take-home setting.

**Operational notes:**
- OS dependency: Tesseract must be installed on the host (documented in README).
- PDFs with scanned images fallback to image OCR via `pdfplumber` image extraction → `pytesseract`.
- Temporary files are written during OCR and are removed in a `finally` block to avoid disk leaks.

**Tradeoffs:**
- Local OCR (Tesseract) is less accurate than cloud OCR/vision LLMs but keeps the project self-contained for reviewers.
- For production, consider a managed OCR or vision LLM for better accuracy on messy scans.

---

# In-memory store design
**Implementation:** a thread-safe in-process Python dict with an `RLock`, plus optional persistence to disk (JSON file).

**API:**
- `save_parsed(document_id, parsed_data, persist: bool = False)`
- `get_parsed(document_id)`
- `delete_parsed(document_id)`
- `list_all()`

**Rationale:**
- One of the requirement is persistence in memory to allow `/ask` to reference prior extractions — an in-memory store is the simplest and fastest for this purpose.
- Optional disk persistence (`PERSIST_PATH`) is available for demo convenience; this behavior is explicit (not automatic) to avoid surprising the reviewer.

**Tradeoffs & caveats:**
- The in-memory store is ephemeral; it will be lost on process restart unless persisted.
- For production: replace with a proper datastore (Redis, PostgreSQL, S3) if durability, scaling, or multi-instance access is required.
- Write persistence is atomic (tmp file → replace) to reduce corruption risk.

---

# API design & behavior notes
- `POST /extract/` (multipart/form-data): accepts file, performs OCR → parse → saves parsed JSON under a UUID `document_id`, returns `{ document_id, parsed }`.
- `POST /ask/` (JSON): accepts `{ document_id, question }`, looks up parsed JSON, runs deterministic answer logic and falls back to mock LLM if configured.
- `GET /` root health endpoint.

**Validation & UX:**
- The router validates files are non-empty and returns clear HTTP errors for OCR/parsing failures.
- File size/type validation is recommended (documented in README) to avoid abuse.

---

# Testing strategy
- Unit tests: focus on extraction helpers and QA logic using synthetic OCR text; these are deterministic and fast.
- Integration tests: upload a representative sample (or bypass OCR and feed sample text) to test the whole pipeline (`/extract` → `/ask`).
- Tests are written with FastAPI `TestClient` so the API contract (schemas) is verified.

---

# Future improvements & roadmap
- **Replace mock LLM with a gated real LLM** (e.g., vector-search + LLM re-rank): keep it opt-in, with rate limits and API keys.
- **Improve layout robustness**: add a lightweight template detection or ML classifier to pick vendor-specific parsing rules.
- **Use a proper datastore** (Redis/Postgres) for persistence and multi-instance support.
- **Better OCR**: evaluate managed OCR (Google Vision, Azure, AWS Textract) or vision LLMs for higher accuracy on messy scans.
- **User feedback loop**: UI or API for human corrections that are used to retrain heuristics/LLM prompts.
- **Monitoring & metrics**: add request tracing, error rates, and extraction accuracy metrics.

---

# Final notes
The design favours reproducibility, explainability, and testability for a take-home submission. The code is intentionally conservative (regex-first, mock LLM, opt-in persistence).
