# Crystal AI — Design Review v2

**Reviewer:** Design Review Subagent  
**Document reviewed:** `.agents/tasks/design.md` (Status: Revised design, post-review v2)  
**Date:** 2025  
**Verdict:** CHANGES_REQUESTED

---

## Findings

### HIGH Severity

---

**F1 — `Config` class body raises `KeyError` at import time, breaking every test run**

**Where:** `config.py`, class `Config`, lines defining `SECRET_KEY` and `GROQ_API_KEY`.

**Problem:**
```python
class Config:
    SECRET_KEY  = os.environ["SECRET_KEY"]    # raises KeyError at Python import time
    GROQ_API_KEY = os.environ["GROQ_API_KEY"] # same
```
Python executes class bodies at definition time — when `config.py` is imported. The `TestingConfig` override (`SECRET_KEY = "test-secret-key"`) is a subclass attribute that is only evaluated *after* the parent class definition succeeds. Because the parent class definition raises `KeyError`, `TestingConfig` is never created. Every `pytest` invocation fails at import unless `SECRET_KEY` and `GROQ_API_KEY` are already set in the shell environment.

The `run.py` entry-point calls `load_dotenv()` before importing `config`, so production/dev mode works, but the test `conftest.py` does not call `load_dotenv()`.

**Concrete fix:**
```python
class Config:
    SECRET_KEY   = os.getenv("SECRET_KEY")    # None by default
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # None by default
    ...

# Validate required values inside create_app(), not at class definition time:
def create_app(config_name="development"):
    app = Flask(...)
    app.config.from_object(config[config_name])
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is not set.")
    if config_name != "testing" and not app.config.get("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")
    ...
```
`TestingConfig` can then safely override these with test values and the validation only fires inside `create_app()` where the subclass values are already in effect.

---

**F2 — `FAISSVectorStore.search()` acquires no lock; concurrent `add_chunks()` causes a race condition**

**Where:** `app/rag/vector_store.py`, `FAISSVectorStore.search()`.

**Problem:**  
`add_chunks()` correctly acquires the per-key `threading.Lock` before loading, mutating, and saving the index. But `search()` calls `self.load()` without acquiring any lock. With `ThreadPoolExecutor(max_workers=4)`, a search request can concurrently read an index file while another thread is writing it (mid-`faiss.write_index`), resulting in a corrupt read or a crash.

The current code:
```python
def search(self, key, query_vec, top_k=10, allowed_chunk_ids=None):
    index, meta = self.load(key)   # ← no lock held
    ...
```

**Concrete fix:**
```python
def search(self, key, query_vec, top_k=10, allowed_chunk_ids=None):
    with self._get_lock(key):          # acquire same per-key lock
        index, meta = self.load(key)
    ...
```
Alternatively, load into an in-memory copy inside the lock and release before doing the FAISS search computation (FAISS search is CPU-bound; holding the lock only for the file I/O is fine).

---

**F3 — Remember-me cookie users bypass `password_version` invalidation**

**Where:** `app/__init__.py` or `app/extensions.py`, `user_loader` callback (Section 5.2).

**Problem:**  
The `user_loader` protects session-based logins by comparing `flask_session.get("password_version")` with `user.password_version`. But when a user is loaded from a *remember-me cookie* (not a session cookie), Flask-Login calls `user_loader` with a freshly created (empty) session. `flask_session.get("password_version")` returns `None`, and the design's guard is:
```python
if stored_version is not None and stored_version != user.password_version:
    return None
```
Since `stored_version` is `None`, the condition is `False` — the stale remember-me cookie user is returned without any password-version check. A user whose password was changed (or who was deactivated) on another device remains fully authenticated via the remember-me cookie indefinitely.

**Concrete fix — store `password_version` in the remember-me cookie payload, or reject cookie-based loads after a password change:**
```python
@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(User, int(user_id))
    if user is None or not user.is_active:
        return None
    stored_version = flask_session.get("password_version")
    if stored_version is None:
        # Loading via remember-me cookie (session is empty).
        # Reject if any password change has occurred since version 0.
        # Alternatively, store version in session here and allow:
        flask_session["password_version"] = user.password_version
    elif stored_version != user.password_version:
        return None
    return user
```
The remember-me cookie cannot carry `password_version` because Flask-Login's cookie format is fixed. The safest approach is to *always* populate `flask_session["password_version"]` from the DB on remember-me loads (as shown above) so subsequent requests do have a session value to compare against.

---

**F4 — `_resolve_file_path()` is called but never defined**

**Where:** `app/ingestion/pipeline.py`, `ingest_document()` (Section 9.5).

**Problem:**
```python
file_path = _resolve_file_path(doc)   # called here, never defined anywhere in the design
```
The design shows the call but provides no signature, body, or specification for this function. The implementation requires knowledge of the upload directory layout: private files go under `uploads/private/<user_id>/` and college-wide files under `uploads/college_wide/`. Without this helper's specification, the implementer must infer the path logic, which could diverge from the upload route's logic in Section 9.2.

**Concrete fix — add the specification:**
```python
def _resolve_file_path(doc: Document) -> Path:
    """Reconstruct the full disk path for a Document's stored file."""
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    if doc.scope == DocumentScope.PRIVATE:
        return upload_folder / "private" / str(doc.user_id) / doc.filename_stored
    else:  # COLLEGE_WIDE
        return upload_folder / "college_wide" / doc.filename_stored
```
This must exactly match the directory used by the upload route in Section 9.2.

---

**F5 — `api.js API.request()` returns `undefined` on 401/403; callers crash with `TypeError`**

**Where:** `static/js/api.js`, `API.request()` and `static/js/chat.js`, `sendMessage()` (Sections 12.2–12.3).

**Problem:**  
`API.request()` returns early (implicitly `undefined`) when `res.status === 401` or `res.status === 403`:
```javascript
if (res.status === 401) { window.location.href = '/login'; return; }  // returns undefined
if (res.status === 403) { showToast('Access denied.', 'error'); return; }  // returns undefined
```
`chat.js` then does:
```javascript
const res = await API.post(...);
const { message } = await res.json();   // TypeError: Cannot read properties of undefined
```
Every caller that destructures the response will throw an unhandled `TypeError`, which silently kills the async function with no user-visible error message other than possibly a broken UI state.

**Concrete fix — throw a typed error instead of returning `undefined`:**
```javascript
async request(method, url, body = null, isFormData = false) {
    const headers = { 'X-CSRFToken': this._csrfToken() };
    if (!isFormData) headers['Content-Type'] = 'application/json';
    const opts = { method, headers, credentials: 'same-origin' };
    if (body) opts.body = isFormData ? body : JSON.stringify(body);
    try {
        const res = await fetch(url, opts);
        if (res.status === 401) { window.location.href = '/login'; throw new Error('Unauthorized'); }
        if (res.status === 403) { showToast('Access denied.', 'error'); throw new Error('Forbidden'); }
        return res;
    } catch (err) {
        if (err.message !== 'Unauthorized' && err.message !== 'Forbidden') {
            showToast('Network error. Please check your connection.', 'error');
        }
        throw err;
    }
},
```
Callers must wrap `await API.post(...)` in `try/catch`.

---

### MEDIUM Severity

---

**F6 — `PUT /auth/profile` and `DELETE /auth/account` referenced in frontend but never specified in the backend**

**Where:** Section 12.3, Profile page description; Section 3.2 auth blueprint table.

**Problem:**  
The profile page JS calls `PUT /auth/profile` and `DELETE /auth/account`. Neither route appears in any backend section — not in Section 5 (Authentication Flow), not in the auth blueprint route table (Section 3.2), not in any API specification. `GET /auth/me` is listed in the blueprint table but also never defined. The implementer has no spec for body format, validation rules, authorization checks, or response shapes for these three endpoints.

**Concrete fix — add explicit specifications for each:**

- `PUT /auth/profile` — body `{display_name: str, max 100 chars}`, validates, updates `user.display_name`, returns `{user: {id, display_name}}` HTTP 200.
- `DELETE /auth/account` — body `{password: str}`, re-authenticates, soft-deletes user (`is_active=False`) or hard-deletes depending on policy choice (pick one), logs audit event, calls `logout_user()`, returns 204. Specify whether user data (sessions, documents) is cascade-deleted immediately or retained.
- `GET /auth/me` — returns `{user: {id, email, display_name, role}}` for the current authenticated user, HTTP 200 or 401 if not authenticated.

---

**F7 — CSRF and rate-limit tests are disabled by the very config they need to test**

**Where:** `tests/conftest.py`, `TestingConfig`, `test_security.py` (Section 13).

**Problem:**  
`TestingConfig` sets `WTF_CSRF_ENABLED = False` and `RATELIMIT_ENABLED = False`. `test_security.py` then tests:
```python
def test_csrf_required_on_state_changing_request(client):   # WTF_CSRF is off
def test_login_rate_limit(client):                           # rate limiting is off
```
Both tests will *pass* or *fail* for wrong reasons — the CSRF test will get a 200 (no CSRF enforcement) and the rate-limit test will never see a 429.

**Concrete fix:**
```python
# In conftest.py, add a second fixture with CSRF/rate-limit enabled:
@pytest.fixture
def security_app():
    _app = create_app("testing")
    _app.config["WTF_CSRF_ENABLED"]  = True
    _app.config["RATELIMIT_ENABLED"] = True
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.drop_all()

@pytest.fixture
def security_client(security_app):
    return security_app.test_client()
```
`test_security.py` must use `security_client` for CSRF and rate-limit tests, not the default `client`.

---

**F8 — DOCX page number estimation is completely undefined**

**Where:** Section 9.3, `docx_parser.py` description.

**Problem:**  
The only guidance is "Page number estimated from heading count." `python-docx` provides no page number API. "Estimated from heading count" is not an implementable rule — does each heading start a new logical page? What if a document has no headings? What is the mapping formula?

**Concrete fix — pick one concrete rule and state it:**
```
Option A (simplest): All DOCX content is assigned page_number=1. Chunker handles
                     subdivision. Source citations show "page 1" for all DOCX content.
Option B: Assign a synthetic page for each Heading 1 paragraph encountered.
          page_number increments each time a Heading 1 is seen.
          All content before the first heading is page 0 or page 1.
```
Recommend Option A — it is honest and avoids false precision. State explicitly which option is chosen.

---

**F9 — `sources_list` construction is absent from the `send_message` flow**

**Where:** Section 6.5, `send_message` steps 6–9.

**Problem:**  
Step 6 returns `[RetrievedChunk]`. Step 7 builds the prompt. Step 9 persists `ChatMessage(..., sources=sources_list)`. But `sources_list` is never built. The `ChatMessage.sources_json` format is `{doc_id, chunk_id, title, page}` (from the model comment), but no code or step in the flow converts a `RetrievedChunk` into that format.

**Concrete fix — add an explicit step between 8 and 9:**
```
Step 8b: Build sources_list from retrieved chunks:
    sources_list = [
        {
            "doc_id":   chunk.document_id,
            "chunk_id": chunk.chunk_db_id,
            "title":    chunk.doc_title,
            "page":     chunk.page_number,
        }
        for chunk in chunks
    ]
```
This step needs to be in the design so the implementer knows exactly what to serialize.

---

**F10 — `AI_PROVIDER_CLASS` config key is claimed but not implemented in `create_app()`**

**Where:** Section 7.2 ("Swapping providers requires only a config change plus a new concrete class") and `create_app()` in Section 3.1.

**Problem:**  
Section 7.2 states: "Swapping to another provider requires only a config change and implementing `AIProvider`." The claim implies a runtime-configurable `AI_PROVIDER_CLASS` key. But `create_app()` hardcodes:
```python
from app.ai.groq_provider import GroqProvider
provider = GroqProvider(api_key=..., model_id=...)
```
There is no config lookup. Swapping providers requires a code change, not just a config change. The abstraction exists (good) but the claim is false.

**Concrete fix — either implement the dynamic lookup or correct the claim:**
```python
# Option A: Implement config-driven selection
provider_class_path = app.config.get("AI_PROVIDER_CLASS", "app.ai.groq_provider.GroqProvider")
module_path, class_name = provider_class_path.rsplit(".", 1)
import importlib
module = importlib.import_module(module_path)
ProviderClass = getattr(module, class_name)
provider = ProviderClass(api_key=app.config["GROQ_API_KEY"], model_id=app.config["GROQ_MODEL_ID"])

# Option B (simpler): Change the documentation claim to:
# "Swapping providers requires adding a new concrete class and editing create_app()."
```

---

**F11 — Image files without OCR complete with `status=READY` but zero retrievable chunks**

**Where:** Section 9.3, `image_parser.py`; Section 9.5, ingestion error matrix.

**Problem:**  
When Tesseract is unavailable and an image file is uploaded, `image_parser.py` returns empty text and logs a warning. The chunker produces zero chunks. The ingestion pipeline commits `doc.status = DocumentStatus.READY` and `job.status = JobStatus.DONE`. From the user's perspective, the document shows as "Ready" but no content was extracted — queries against it return nothing, with no explanation.

**Concrete fix:**
```python
# In pipeline.py, after chunking:
if len(chunks) == 0 and doc.file_type in ("png", "jpg", "jpeg"):
    # Image with no text extracted — set a meaningful status
    if not OCR_AVAILABLE:
        doc.status = DocumentStatus.FAILED
        job.status = JobStatus.FAILED
        job.error_message = (
            "No text could be extracted from this image. "
            "Tesseract OCR is not installed on the server."
        )
    else:
        doc.status = DocumentStatus.FAILED
        job.status = JobStatus.FAILED
        job.error_message = "No text was found in this image."
    db.session.commit()
    return
```
Alternatively, introduce a `DocumentStatus.EMPTY` or `DocumentStatus.NO_CONTENT` state.

---

**F12 — `auth_headers` test fixture uses fragile manual cookie injection**

**Where:** `tests/conftest.py`, `auth_headers` fixture (Section 13.1).

**Problem:**
```python
return {"Cookie": res.headers.get("Set-Cookie", "")}
```
Flask's `Set-Cookie` header may contain multiple cookies (`session`, `remember_token`, `csrf_token`). Extracting the raw header string and passing it back as a `Cookie:` header is brittle — it will not survive redirects, cookie renewal, or multi-cookie scenarios. Additionally, using `client.post(..., headers=auth_headers)` with a manual `Cookie` header does not integrate with Flask-Login's session management in the test client.

**Concrete fix — use Flask test client's built-in session management:**
```python
@pytest.fixture
def authenticated_client(app, client):
    with app.app_context():
        user = User(email="student@test.com", display_name="Test Student")
        user.set_password("Test@1234")
        _db.session.add(user)
        _db.session.commit()
        user_id = user.id
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["password_version"] = 0
    return client
```
This avoids the registration/login round-trip and is immune to cookie string parsing issues.

---

**F13 — College-wide document upload endpoint is ambiguous**

**Where:** Section 9.2 (`POST /api/documents` with `scope=college_wide`) and Section 11.1 (`POST /admin/documents`).

**Problem:**  
The design defines *two* upload paths that appear to overlap for college-wide documents:
1. `POST /api/documents` (documents blueprint) — Section 9.2 says "Admin-only scope on non-admin user: abort 403", implying admins *can* use this endpoint for college-wide uploads.
2. `POST /admin/documents` (admin blueprint) — Section 11.1 lists this as a separate route.

It is unclear whether there is one implementation shared by both URLs, or two separate implementations. The `delete_document` for college-wide in Section 6.9 says "admins may delete COLLEGE_WIDE docs via `/admin/documents/<id>` (separate route, same logic)" — suggesting different routes but same logic. But for upload, which route does `admin.js` call?

**Concrete fix — pick one canonical route and eliminate the ambiguity:**
```
Option A: College-wide upload uses POST /admin/documents exclusively.
          POST /api/documents always creates PRIVATE scope.
          The scope field is removed from /api/documents.

Option B: College-wide upload uses POST /api/documents with scope=college_wide.
          POST /admin/documents is an alias that delegates to the same handler.
          The admin blueprint upload route is removed.
```
Recommend Option A — it makes the authorization boundary clear and removes a redundant code path.

---

**F14 — Vector store directory layout in Section 2 contradicts the path keys in Section 8.3**

**Where:** Section 2 (directory layout), Section 8.3 (`FAISSVectorStore` key scheme).

**Problem:**  
Section 2 shows:
```
vector_store/
├── private/
│   └── {user_id}.index
│   └── {user_id}.meta.json
└── college_wide/
    ├── college_wide.index
    └── college_wide.meta.json
```
But `FAISSVectorStore._paths(key)` produces:
```python
self.base_path / f"{key}.index"      # key = "private_1" → vector_store/private_1.index
self.base_path / f"{key}.meta.json"  # key = "college_wide" → vector_store/college_wide.index
```
The directory tree in Section 2 (`private/1.index`) does not match the actual paths generated by the code (`private_1.index`). During the Windows developer setup (Section 15), creating `vector_store\private` and `vector_store\college_wide` directories is useless — the code puts everything flat under `vector_store/`.

**Concrete fix — align Section 2 with the actual key scheme:**
```
vector_store/
├── private_1.index
├── private_1.meta.json
├── college_wide.index
└── college_wide.meta.json
```
Or change the code to use sub-directories. Either is fine; they just need to match.

---

**F15 — Bulk delete sessions mentioned in the UI but no backend endpoint exists**

**Where:** Section 12.3, Chat history page description; Section 6.1 route table.

**Problem:**  
The chat history page (`history.html`) has a "Bulk delete (checkbox + button)" feature. The route table in Section 6.1 has no bulk-delete endpoint. The only session delete is `DELETE /api/sessions/<session_id>` (single session). The `history.js` module has no implementation note. Implementing bulk delete from the single-delete endpoint requires N sequential requests, which is fragile and slow.

**Concrete fix — either specify a bulk delete endpoint or remove the feature:**
```
Option A: Add DELETE /api/sessions endpoint accepting body {"session_ids": [int, ...], max 50}.
          Validates each ID belongs to current_user, deletes in a single transaction.
          Returns 200 {"deleted": N}.

Option B: Remove "Bulk delete" from the history page feature list and use only
          the existing single-delete action per row.
```

---

### NIT Severity

---

**N1 — MIME mismatch silently ignores the warning comment**

**Where:** Section 9.1, `validators.py`, MIME check block.

```python
if ALLOWED_MIMES.get(ext) and content_type and ...:
    pass  # Log warning; don't block on client MIME alone
```
The comment says "Log warning" but the code is `pass` — no `app.logger.warning(...)` or `current_app.logger.warning(...)` call. The implementer will copy this snippet and silently drop the log.

**Fix:** Replace `pass` with `current_app.logger.warning("MIME mismatch for %s: expected %s, got %s", original_name, ALLOWED_MIMES[ext], content_type)`.

---

**N2 — `reranker.py` is in the directory layout and architecture diagram but is never called**

**Where:** Section 2 (directory layout), Section 8.1 (architecture diagram).

The diagram shows `Reranker` as a pipeline step, and `app/rag/reranker.py` appears in the directory layout. But `HybridRetriever.retrieve()` in Section 8.4 never calls `reranker`. The file is dead code from the start.

**Fix:** Either show the reranker call in `retrieve()` after the sort step, or remove it from the directory layout and add a comment that it is a future extension.

---

**N3 — `txt_parser` pre-chunks into ~500-line blocks before the chunker runs (double-chunking)**

**Where:** Section 9.3, `txt_parser.py` description.

All other parsers return full pages/slides and let the word-based chunker in Section 9.4 do the splitting. `txt_parser` pre-splits into ~500-line synthetic pages, which then get chunked again by the word chunker. The TXT path produces chunk sizes inconsistent with other formats.

**Fix:** Remove the 500-line pre-split from `txt_parser`. Return the whole file as a single `ParsedPage` (or one `ParsedPage` per real blank-line-separated section) and let the word chunker handle sizing uniformly.

---

**N4 — `session_protection = "strong"` may interfere unexpectedly with the remember-me flow on IP change**

**Where:** `app/extensions.py`, `login_manager.session_protection = "strong"`.

With `"strong"` protection, Flask-Login clears the session (not just marks it non-fresh) when the client's `_id` (hash of IP + User-Agent) changes. On mobile networks with dynamic IPs, this logs the user out silently on what appears to be a normal page load. This is a UX concern and may conflict with the design's 8-hour session intent for students on mobile.

**Fix (design decision, not a code bug):** Document this known trade-off in `config.py` or in a setup note, or downgrade to `"basic"` and compensate with the `password_version` check (which is already implemented).

---

**N5 — `list_sessions` response shape is not specified**

**Where:** Section 6.4.

`create_session` response is fully specified: `{id, title, created_at, updated_at, message_count: 0}`. But `list_sessions` only shows the wrapper: `{"sessions": [...], "total": N, "page": 1, "pages": M}`. The per-item fields are `[...]` — unspecified. Does each session include `message_count`? The dashboard widget and chat sidebar both display session titles (they can infer just `{id, title, updated_at}`), but a `message_count` would require a subquery.

**Fix:** List the exact fields returned per session in Section 6.4.

---

**N6 — `hmac.compare_digest` dummy check mentioned but never shown**

**Where:** Section 5.2, Login flow, step 3.

"If user not found OR `not user.check_password(password)`: wait constant time (use `hmac.compare_digest` dummy check)." No code is shown. Without an implementation snippet, a naive implementer may call `check_password` only when the user exists (short-circuit), creating a timing oracle.

**Fix:**
```python
# Constant-time response regardless of whether user exists
dummy_hash = "$pbkdf2-sha256$600000$..."  # any valid hash

if user is None:
    hmac.compare_digest(dummy_hash, dummy_hash)  # consume similar time
    return jsonify({"error": "Invalid email or password."}), 401
if not user.check_password(password):
    return jsonify({"error": "Invalid email or password."}), 401
```

---

## Verified Assumptions

| Assumption | Status | Evidence |
|---|---|---|
| `faiss-cpu==1.10.0` ships a `cp312-win_amd64` wheel | ✅ VERIFIED | `pip install faiss-cpu==1.10.0 --dry-run` downloads `faiss_cpu-1.10.0-cp312-cp312-win_amd64.whl` |
| Python 3.12.10 is on the target machine | ✅ VERIFIED | `python --version` → `Python 3.12.10` |
| `groq==1.7.0` has `RateLimitError`, `APITimeoutError`, `AuthenticationError`, `APIError` | ✅ VERIFIED | `from groq import RateLimitError, APITimeoutError, AuthenticationError, APIError` succeeds |
| `groq.Groq` client has `.models.list()` method | ✅ VERIFIED | `g.models.list` exists on `groq.resources.models.Models` |
| FAISS handles Windows backslash paths in `write_index`/`read_index` | ✅ VERIFIED | Test with `Path(tempdir) / 'test.index'` passes on Windows |
| `sentence-transformers==3.4.1` is installable on Python 3.12 | ✅ VERIFIED | `pip install sentence-transformers==3.4.1 --dry-run` succeeds |
| `sentence-transformers==3.4.1` is the last 3.x release | ✅ VERIFIED | PyPI shows next version is 4.0.0 |
| `RATELIMIT_ENABLED` is the correct Flask-Limiter 3.8.0 config key | ✅ VERIFIED | `ConfigVars.ENABLED` → `"RATELIMIT_ENABLED"` |
| `python-pptx` `MSO_SHAPE_TYPE.PICTURE == 13` | ✅ VERIFIED | `MSO_SHAPE_TYPE.PICTURE.real == 13` confirmed |
| `shape.image.blob` is valid for pptx Picture shapes | ✅ VERIFIED | `Image.blob` exists in `pptx.parts.image.Image` |
| Flask-SQLAlchemy 3.1.1 `Query.paginate()` still exists | ✅ VERIFIED | `flask_sqlalchemy.query.Query.paginate` is present |
| `flask_sqlalchemy.query.Query.paginate` accepts `page`, `per_page`, `error_out` kwargs | ✅ VERIFIED | Signature confirmed |
| Werkzeug 3.x does NOT require `python-multipart` for file uploads | ✅ VERIFIED | Werkzeug uses its own `sansio.multipart` module |
| `import fitz` (PyMuPDF) still works at the pinned version 1.24.11 (deprecated only in 1.25+) | ✅ VERIFIED | Deprecation warning appears in 1.28.2 but `fitz.open()` is still present; 1.24.11 has no deprecation |
| `lazy="dynamic"` relationships are still supported in SQLAlchemy 2.0 | ✅ VERIFIED | No error on relationship definition; `DynamicMapped` exists |

---

## Unverified / Wrong Assumptions

| Assumption | Status | Issue |
|---|---|---|
| `TestingConfig.SECRET_KEY = "test-secret-key"` prevents `KeyError` at import | ❌ WRONG | Parent class body executes at import, raises `KeyError` before subclass is defined (F1) |
| `user_loader` `password_version` check covers remember-me cookie users | ❌ WRONG | `flask_session.get("password_version")` is `None` for remember-me loads; check is bypassed (F3) |
| `_resolve_file_path(doc)` is defined somewhere in the codebase | ❌ UNVERIFIED | Not present anywhere in the design document (F4) |
| `API.request()` returning `undefined` on 401/403 is safe for callers | ❌ WRONG | `chat.js sendMessage` does `const { message } = await res.json()` which throws `TypeError` (F5) |
| `FAISSVectorStore.search()` is safe to call concurrently with `add_chunks()` | ❌ WRONG | `search()` acquires no lock; concurrent write from `add_chunks()` can corrupt the read (F2) |
| `PUT /auth/profile` and `DELETE /auth/account` are defined in the backend | ❌ UNVERIFIED | Neither endpoint appears in any backend section (F6) |
| "Swapping providers requires only a config change" | ❌ WRONG | `create_app()` hardcodes `GroqProvider`; no `AI_PROVIDER_CLASS` config lookup exists (F10) |
| `txt_parser` 500-line pre-splitting produces the same chunk granularity as other parsers | ❌ WRONG | TXT files get chunked twice; other formats go through the word chunker only once (N3) |
| Section 2 directory layout for `vector_store/` matches `FAISSVectorStore` path generation | ❌ WRONG | Section 2 shows `private/{user_id}.index`; code generates `private_{user_id}.index` flat (F14) |

---

## Verdict

**5 HIGH findings + 10 MEDIUM findings → CHANGES_REQUESTED**

The design is substantially well-structured and the first review's findings have been properly addressed. The remaining issues are all solvable without redesign: the config KeyError pattern, the FAISS read lock, the remember-me bypass, the missing helper specification, the frontend crash on 401/403, and the scattered missing endpoint specs. None require architectural changes.
