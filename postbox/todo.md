# SENTINAL v2 — Task Postbox

> This file is the shared task queue between Claude (orchestrator) and Gemini (coder).
> Claude writes tasks here. Gemini picks them up. Both agents check this file.

---

## OPEN (not yet built)

### Phase 10 — Security Hardening & Bug Fixes

### TASK-068
- **File:** `engine/stream/mjpeg.py`
- **Agent:** haiku-writer
- **Depends on:** none
- **Spec:** Audit B2 — `asyncio.get_event_loop()` deprecated in Python 3.10+, raises RuntimeError in Python 3.12 when no running loop exists
- **Requirements:**
  - In `MJPEGBuffer.__init__()`, the `except RuntimeError` fallback at line 43 calls `asyncio.get_event_loop()` — replace this single line with `self._loop = asyncio.new_event_loop()`
  - Add the following warning log immediately after that line: `logger.warning("MJPEGBuffer[%s]: no running event loop — created a new loop. Pass loop= explicitly.", cam_id)`
  - Do NOT change any other logic: `__init__` signature, `push_frame`, `_safe_put`, `frame_generator` must remain identical
  - All existing type hints and docstrings must be preserved unchanged
- **Test:** `python -c "from engine.stream.mjpeg import MJPEGBuffer; print('OK')"` with venv active
- **Status:** COMPLETED

---

### TASK-069
- **File:** `api/routers/auth.py`
- **Agent:** gemini-coder
- **Depends on:** none
- **Spec:** Audit B7 follow-up — `@limiter.limit("5/minute")` is currently applied to an inner `_login` function, not to the registered FastAPI route handler. `slowapi` cannot intercept requests for the inner callable; the rate limit is silently never enforced.
- **Requirements:**
  - Remove the inner `_login` async function entirely and remove the `return await _login(request, form_data)` tail call
  - Move the credential-check + JWT-creation logic directly into the `login` function body
  - Apply `@limiter.limit("5/minute")` as a decorator directly on the `login` route function, placed on the line immediately above `@router.post("/login")`
  - The `login` function signature must remain: `async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, str]:`
  - For the limiter import, use a guarded module-level import to avoid circular imports: `try:\n    from api.main import limiter as _rate_limiter\nexcept ImportError:\n    _rate_limiter = None` then define `_rate_limit = _rate_limiter.limit("5/minute") if _rate_limiter else lambda f: f` and decorate `login` with `@_rate_limit` above `@router.post("/login")`
  - All existing type hints, docstrings, the `SECRET_KEY` constant, and `ALGORITHM` constant must remain unchanged
- **Test:** `python -c "from api.routers.auth import router; print('OK')"` with venv active; `python -m pytest tests/test_api_integration.py -v -k login` — login tests must still pass
- **Status:** COMPLETED

---

### TASK-070
- **File:** `api/main.py`
- **Agent:** haiku-writer
- **Depends on:** TASK-069
- **Spec:** Audit C9 — No health check endpoint. Docker health probes, Kubernetes liveness checks, and load balancers need `GET /health` returning 200 without authentication.
- **Requirements:**
  - Add the following route directly to the `app` object at the end of `api/main.py`, after all `app.include_router(...)` calls: `@app.get("/health")` with handler `async def health_check() -> dict:` returning `{"status": "ok", "service": "SENTINAL v2"}`
  - This route must NOT appear in the `_auth_dep` dependency list — it must be publicly accessible without a JWT
  - Do NOT modify any existing imports, middleware, lifespan function, CORS configuration, or router registrations
- **Test:** `python -c "from api.main import app; routes = [r.path for r in app.routes]; assert '/health' in routes, 'health route missing'; print('OK')"` with venv active
- **Status:** COMPLETED

---

### TASK-071
- **File:** `docker-compose.yml`
- **Agent:** haiku-writer
- **Depends on:** none
- **Spec:** Audit D8 — `version: '3.9'` at line 1 is deprecated and ignored by Docker Compose v2+; generates a warning on every invocation
- **Requirements:**
  - Delete line 1 (`version: '3.9'`) from `docker-compose.yml`
  - Delete the blank line immediately following it so the file starts directly with `services:`
  - Do NOT change any other content — all service definitions, environment variables, volumes, network_mode settings, and the postgres healthcheck must remain identical
- **Test:** `python -c "import yaml; d=yaml.safe_load(open('docker-compose.yml')); assert 'version' not in d, 'version key still present'; assert 'services' in d; print('OK')"`
- **Status:** COMPLETED

---

### Phase 9 — Final Gaps

### TASK-067
- **File:** `dashboard/src/components/ZoneEditor.jsx`
- **Agent:** react-builder
- **Depends on:** none
- **Spec:** SPEC.md Section 10 — components/ZoneEditor.jsx
- **Requirements:**
  - Standalone reusable component; accepts props: `cameraId`, `streamUrl`, `existingZone` (optional for edit mode), `onSave(zoneData)`, `onCancel()`
  - Renders camera MJPEG stream as background: `<img src={streamUrl} style={{ width:'100%' }} />`
  - Overlaid `<svg>` positioned absolutely, sized to match the img; click on SVG canvas adds polygon vertex at pointer coordinates
  - Double-click closes the polygon (connect last point to first); apply 300ms debounce so the double-click does not also register as two single-clicks adding two points
  - Vertex dragging: render each vertex as a `<circle r={6}>` element; `onMouseDown` on a circle enters drag mode; `onMouseMove` on the SVG updates that vertex position; `onMouseUp` exits drag mode
  - Color picker: `<input type="color" value={color} onChange={...}>` for zone fill color; default `#FF0000`
  - Label input: `<input type="text" placeholder="Zone label" value={label} onChange={...}>`
  - "SAVE" button: scales pixel coordinates from display size to natural image size using `getBoundingClientRect()`; calls `onSave({ label, color, polygon: [[x,y],...] })`
  - "CANCEL" button: calls `onCancel()` without saving
  - "CLEAR" button: resets vertex list to empty
  - Inline styles only; dark theme (`background: '#0d0d0d'`, accent `#00e5ff`, surface `#1a1a1a`) matching the existing dashboard
  - `Zones.jsx` must import `ZoneEditor` and use it for the drawing canvas, replacing its current inline SVG click handler with the component; `Zones.jsx` passes `streamUrl` derived from `${API_BASE}/api/stream/${selectedCamId}` and handles `onSave`/`onCancel`
- **Test:** `cd dashboard && npm run build` with 0 errors; `ZoneEditor.jsx` exists at `dashboard/src/components/ZoneEditor.jsx`
- **Status:** COMPLETED

---

### Phase 8 — Polish, Missing Tests & Bug Fixes

### TASK-064
- **File:** `dashboard/src/store/useStore.js`
- **Agent:** react-builder
- **Depends on:** none
- **Spec:** Bug fix — fetchEvents error return is a truthy non-array object, causing runtime TypeError in callers
- **Requirements:**
  - In `fetchEvents`, the catch/error path currently returns `{ events: [], total: 0 }` — a truthy non-array
  - Callers guard with `if (data)` then call `data.slice()` or `data.forEach()` — both throw TypeError on a plain object
  - Fix: change the error-path return value to `null` (one-line change only)
  - Do NOT change any other logic; all existing exports must remain intact
- **Test:** `cd dashboard && npm run build` with 0 errors
- **Status:** COMPLETED

---

### TASK-065
- **File:** `dashboard/src/pages/Events.jsx`
- **Agent:** react-builder
- **Depends on:** TASK-064
- **Spec:** SPEC.md Section 10 — "Export to CSV button"
- **Requirements:**
  - Add an "EXPORT CSV" button in the `<header>` section, sibling to the title block
  - On click: convert current `events` array to CSV with columns: `id`, `timestamp`, `cam_id`, `alert_type`, `zone_id`, `name`, `confidence`
  - `name` field: use `ev.name` if truthy, else `ev.global_ids?.[0] ?? ''`
  - Include header row; wrap comma-containing values in double quotes
  - Trigger download via `new Blob([csv], { type: 'text/csv' })` → temp `<a download="sentinal_events.csv">` → click → revoke URL
  - Use existing `s.btnGhost` inline style; add `Download` icon from `lucide-react` (already installed)
  - Disable button when `events.length === 0`
  - No new npm dependencies
- **Test:** `cd dashboard && npm run build` with 0 errors
- **Status:** COMPLETED

---

### TASK-066
- **File:** `tests/test_ws_auth.py`
- **Agent:** gemini-coder
- **Depends on:** none
- **Spec:** CLAUDE.md — WebSocket /ws/live endpoint auth coverage
- **Requirements:**
  - `httpx.AsyncClient` with `ASGITransport(app=app)` — same pattern as `test_api_integration.py`
  - `@pytest_asyncio.fixture async def client()` identical to existing test file
  - `test_ws_no_token_rejected`: GET `/ws/live` (no token) → assert status in (403, 426)
  - `test_ws_invalid_token_rejected`: GET `/ws/live?token=not_a_valid_jwt` → assert status in (403, 426)
  - `test_ws_valid_token_accepted`: POST login → GET `/ws/live?token=<jwt>` → assert status == 101
  - All test functions: `@pytest.mark.asyncio`, full type hints, docstrings
  - Module-level docstring explaining scope
- **Test:** `python -m pytest tests/test_ws_auth.py -v` — all 3 pass
- **Status:** COMPLETED

---

### Phase 7 — Dashboard Auth & UX Polish

### TASK-059
- **File:** `dashboard/src/store/useStore.js`
- **Agent:** react-builder
- **Depends on:** none
- **Spec:** Add auth token state, login/logout actions, and Authorization headers to all API fetches
- **Requirements:**
  - Add `token` state field initialized from `localStorage.getItem('sentinal_token')` (preserves session on page refresh)
  - Add `login(username, password)` async action: POST `${API_BASE}/api/auth/login` with body `username=<val>&password=<val>` and `Content-Type: application/x-www-form-urlencoded`; on HTTP 200 extract `access_token` from JSON, call `localStorage.setItem('sentinal_token', token)`, set `token` in state, return `true`; on 401 or network error return `false`
  - Add `logout()` action: set `token: null`, call `localStorage.removeItem('sentinal_token')`, call `stopWebSocket()`
  - Update `fetchCameras` and any other fetch calls inside the store to include header `Authorization: Bearer ${get().token}` when `get().token` is non-null
  - In `connectWebSocket`: append `?token=${get().token}` to `WS_URL` before constructing `new WebSocket(...)` when token is non-null
  - Do NOT alter the existing `startWebSocket`, `stopWebSocket`, `weaponAlarm`, `gridLayout`, `dismissWeaponAlarm` logic
  - All existing exported symbols (`API_BASE`, default `useStore`) must remain exported
- **Test:** `cd dashboard && npm run build` with 0 errors
- **Status:** COMPLETED

### TASK-060
- **File:** `dashboard/src/pages/Login.jsx`
- **Agent:** react-builder
- **Depends on:** TASK-059
- **Spec:** Login page with username/password form, calls useStore login action, redirects on success
- **Requirements:**
  - Default export `Login` functional component
  - Full-page vertically and horizontally centered layout; background `#0d0d0d`; font family `monospace`
  - Title "SENTINAL v2" in `#00e5ff`, subtitle "Surveillance Control System" in `#555`
  - Two inputs: `username` (type text) and `password` (type password); dark styling matching the rest of the dashboard
  - Submit button labeled "LOGIN"; during in-flight request: disable button, change label to "Authenticating..."
  - On submit: call `login(username, password)` from `useStore`; if `true` returned, call `navigate('/')` via `useNavigate()`
  - If `false` returned: display error message "Invalid credentials" in `#ff1744` below the button
  - Inline styles only — no external CSS file or component library imports
  - Import `useNavigate` from `react-router-dom`; import `useStore` from `../store/useStore`
- **Test:** `cd dashboard && npm run build` with 0 errors; file exists at `dashboard/src/pages/Login.jsx`
- **Status:** COMPLETED

### TASK-061
- **File:** `dashboard/src/App.jsx`
- **Agent:** react-builder
- **Depends on:** TASK-059, TASK-060
- **Spec:** Add /login route, ProtectedRoute wrapper for all other routes, and logout button in nav bar
- **Requirements:**
  - Define `ProtectedRoute` component inline in App.jsx (not a separate file): reads `token` from `useStore`; if token is null/falsy renders `<Navigate to="/login" replace />`; otherwise renders the nav bar + `<Outlet />`
  - Move the nav bar (`<nav>...</nav>`) inside the `ProtectedRoute` render path so it is NOT visible on the `/login` page
  - Add a logout button at the far right of the nav bar (styled consistently, using the existing button inline style approach): on click calls `useStore.logout()` then `navigate('/login')` via `useNavigate()`
  - Add `<Route path="/login" element={<Login />} />` as a sibling of the protected wrapper, NOT nested inside it
  - Wrap all existing page routes (`/`, `/cameras`, `/events`, `/identities`, `/alerts`, `/analytics`, `/zones`) inside `<Route element={<ProtectedRoute />}>` as their parent
  - Import `Login` from `./pages/Login`; import `Navigate`, `Outlet`, `useNavigate` from `react-router-dom`; import `useStore` from `./store/useStore`
  - `AlertBanner` must remain rendered inside the protected zone only (move inside ProtectedRoute output if currently at root level)
- **Test:** `cd dashboard && npm run build` with 0 errors; all 7 existing routes still present; `/login` route present
- **Status:** COMPLETED

### TASK-062
- **File:** `dashboard/src/pages/LiveView.jsx`
- **Agent:** react-builder
- **Depends on:** TASK-059, TASK-061
- **Spec:** Add Authorization header to the zones fetch inside CameraCard
- **Requirements:**
  - In `CameraCard`, the `useEffect` fetch to `${API_BASE}/api/zones?cam_id=${camera.cam_id}` currently has no auth header
  - Read the token via `useStore.getState().token` (direct state access — not a hook, since `CameraCard` is not re-rendered on token changes; the token is stable after login)
  - Add `headers: { Authorization: \`Bearer ${token}\` }` to that fetch call when token is non-null
  - Do NOT change any other logic in this file — weapon alarm banner, grid layout, WS indicator, event sidebar all remain as-is
  - The MJPEG `<img src={streamUrl}>` does not need auth (stream endpoint is unprotected by design)
- **Test:** `cd dashboard && npm run build` with 0 errors
- **Status:** COMPLETED

### TASK-063
- **File:** `api/routers/ws.py`
- **Agent:** gemini-coder
- **Depends on:** none (backend task, no dependency on dashboard tasks)
- **Spec:** Add JWT token-as-query-param authentication to the WebSocket /ws/live endpoint
- **Requirements:**
  - Add `token: Optional[str] = Query(default=None)` parameter to `websocket_endpoint(websocket, token)`; import `Optional` from `typing` and `Query` from `fastapi`
  - Before calling `manager.connect()`: if `token` is None or empty string, call `await websocket.close(code=4001)` and return immediately (do not call `accept()` first)
  - Validate token by decoding with `jose.jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])`; import `jwt` from `jose` and `JWTError` from `jose`; import `settings` from `engine.config`
  - If `JWTError` is raised, call `await websocket.close(code=4001)` and return; log `logger.warning("WS rejected: invalid or missing token")`
  - If token is valid, proceed to `await manager.connect(websocket)` as before
  - Do NOT modify `ConnectionManager`, `broadcast_event`, or any other existing logic
  - All type hints and docstrings on modified functions must be preserved/updated
- **Test:** `python -c "from api.routers.ws import router, manager, broadcast_event; print('OK')"` run with venv active
- **Status:** COMPLETED

---

## COMPLETED

### TASK-058
- **File:** `tests/test_performance.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-08
- **Test:** PASS — 4-camera mock benchmark: 1523 fps/camera (threshold 13.5); no time.sleep; threading.Event timing; cv2.resize proxy; pytest test_pipeline_4cam_throughput passes

### TASK-057
- **File:** `tests/test_api_integration.py` + `pytest.ini` + `tests/conftest.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-08
- **Test:** PASS — 11/11 pytest tests; login_success, login_failure, stats_requires_auth, stats_with_auth, events/cameras/zones/identities/alerts with auth; utcnow() deprecation fixed

### TASK-056
- **File:** `api/main.py` (auth wiring)
- **Assigned to:** gemini-coder (applied directly)
- **Completed:** 2026-03-08
- **Test:** PASS — /api/auth/login registered without dep; cameras/zones/events/identities/alerts/stats have Depends(get_current_user); stream + ws unprotected; import OK

### TASK-055
- **File:** `api/middleware/__init__.py` + `api/middleware/auth.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-08
- **Test:** PASS — import OK; oauth2_scheme + get_current_user + ALGORITHM=HS256; uses settings.jwt_secret_key; 401 on JWTError

### TASK-054
- **File:** `api/routers/auth.py` + `engine/config.py` updated (4 auth fields)
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-08
- **Test:** PASS — import OK; `Depends()` fix applied; HS256 algo; SECRET_KEY from settings; 401 on bad creds; python-jose added to requirements.txt

### TASK-053
- **File:** `.env.example`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — 28 fields loaded via dotenv_values; DB_URL + all config.py fields present; no real secrets

### TASK-049
- **File:** `api/routers/stats.py` + `api/main.py` updated
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-08
- **Test:** PASS — `from api.routers.stats import router` OK; StatsResponse Pydantic model with 6 fields; dual SQLite/PG backend; active_cameras from camera_service.list_cameras(); registered in main.py

### TASK-051
- **File:** `api/routers/__init__.py`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — `import api.routers` OK

### TASK-052
- **File:** `api/services/__init__.py`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — `import api.services` OK

### TASK-050
- **File:** `api/__init__.py`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — `import api` OK; module docstring present

### TASK-034
- **File:** `tests/test_reid_face.py`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — 5/5 pytest tests; ReIDEngine gallery (5 distinct IDs, re-query match 5/5, preprocess shape 256×128×3); FaceRecognizer no-crash + analyze returns list; runs without GPU/torchreid/insightface

### TASK-033
- **File:** `engine/pipeline.py` (Re-ID + face fusion + diagnostic logging)
- **Assigned to:** gemini-coder (already implemented in prior session)
- **Completed:** 2026-03-08
- **Test:** PASS — face fusion quality_score>0.7 gate; _debug_reid env flag; frame_count%50 diagnostic log; import OK

### TASK-048
- **File:** `tests/test_phase5_integration.py`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — 4/4 unittest tests OK; db module + async init_db; Docker files exist; /zones in App.jsx; asyncpg in requirements.txt

### TASK-047
- **File:** `requirements.txt` (created with all phases + Phase 5 asyncpg/psycopg2-binary)
- **Assigned to:** haiku-writer (Claude)
- **Completed:** 2026-03-08
- **Test:** PASS — asyncpg>=0.29.0 + psycopg2-binary>=2.9.0 present; all phase 1-4 deps included

### TASK-046
- **File:** `dashboard/src/pages/Zones.jsx` + App.jsx updated
- **Assigned to:** react-builder
- **Completed:** 2026-03-08
- **Test:** PASS — npm run build 0 errors (2414 modules); SVG polygon drawing; click=add vertex, dblclick=close; getBoundingClientRect pixel mapping; 300ms dblclick debounce; POST/PUT/DELETE zone API; zone cards with active toggle; /zones route + nav link added

### TASK-045
- **File:** `docker-compose.yml`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — YAML valid; postgres/engine/dashboard services; pg_isready healthcheck; nvidia runtime; network_mode:host; postgres_data volume; ${POSTGRES_PASSWORD} used

### TASK-044
- **Files:** `dashboard/Dockerfile` + `dashboard/nginx.conf`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — multi-stage node:20-alpine build + nginx:alpine serve; SPA try_files routing; /api/ + /ws/ proxy to engine:8000; WebSocket upgrade headers

### TASK-043
- **File:** `Dockerfile` (engine container)
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-08
- **Test:** PASS — nvidia/cuda:12.1 base; python3.11; pip install requirements; mkdir data/snapshots data/logs models; EXPOSE 8000; uvicorn CMD; no hardcoded secrets

### TASK-042
- **File:** `engine/storage/db.py` (PostgreSQL migration via asyncpg)
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-08
- **Test:** PASS — dual-backend detection (_USE_PG flag); asyncpg pool min=2/max=10; $N param indexing fixed (dynamic); BYTEA for PG embeddings; ON CONFLICT upsert; get_stats() same keys both backends; SQLite path unchanged; import OK

### TASK-041
- **Files:** `dashboard/src/components/AlertBanner.jsx` + `Alerts.jsx` + `Analytics.jsx` + `App.jsx` updated
- **Assigned to:** react-builder
- **Completed:** 2026-03-08
- **Test:** PASS — npm run build 0 errors (2413 modules); AlertBanner full-screen weapon alarm with audio beep + auto-dismiss; Alerts.jsx config form + test buttons; Analytics.jsx recharts line/bar/pie charts; /alerts + /analytics routes added; recharts installed

### TASK-040
- **File:** `api/routers/alerts.py` + `api/main.py` updated
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-08
- **Test:** PASS — GET/PUT/POST /api/alerts/config+test; AlertConfigResponse+AlertConfigUpdate schemas; SMTP password masked; dummy Alert for test; registered in main.py; import OK

### TASK-039
- **File:** `engine/pipeline.py` (weapon + anomaly wiring)
- **Assigned to:** gemini-coder (Claude)
- **Completed:** 2026-03-08
- **Test:** PASS — weapon_detector + anomaly_detector optional params added; weapon check dispatches immediately after detection; anomaly_detector.update() called after zone check; fully backward compatible; import OK

### TASK-038
- **File:** `engine/alerts/webhook.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — post_webhook import OK; httpx.AsyncClient; timeout=5s; enabled+url guard; datetime/enum serialization; silent fail; type hints + docstrings

### TASK-037
- **File:** `engine/alerts/email.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — send_alert_email import OK; aiosmtplib async SMTP; settings.alert_email_enabled gate; silent fail on errors; snapshot attachment; type hints + docstrings

### TASK-036
- **File:** `engine/vision/anomaly.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — AnomalyDetector, Anomaly import OK; loitering/crowding/violence rules implemented; RLock thread-safety; uses settings.alert_cooldown_seconds for crowding; no time.sleep; import test passed

### TASK-035
- **File:** `engine/vision/weapon.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — WeaponDetector, WeaponAlert import OK; 0.55 confidence threshold; case-insensitive weapon keyword matching; returns highest-confidence match; snapshot_path empty string; engine/alerts/__init__.py present

### TASK-032
- **File:** `engine/vision/face.py` (accuracy tuning)
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — CLAHE 3.0, min conf gate 0.6, area gate <500px, 5% padding margin, diagnostic logging, thread-safe, import OK

### TASK-031
- **File:** `engine/vision/reid.py` (accuracy tuning)
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — CLAHE 3.0, EMA α=0.95, threshold 0.80, gallery TTL 300s, diagnostic logging, thread-safe, import OK

### TASK-030
- **Files:** `dashboard/src/pages/Identities.jsx` + `dashboard/src/components/PersonBadge.jsx` + `App.jsx` updated
- **Assigned to:** react-builder
- **Completed:** 2026-03-07
- **Test:** PASS — npm run build succeeds (0 errors); identity cards with inline edit, face enroll, delete; PersonBadge compact pill; /identities route + nav link in App.jsx; lucide-react installed

### TASK-029
- **File:** `engine/pipeline.py` (Phase 3 Re-ID + face wiring)
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — pipeline import OK; reid_engine/face_recognizer optional params; bbox crop per track; get_or_create_global_id called; move_to_lost on disappeared tracks; face recognizer on crop with quality_score; fully backward compatible; no time.sleep/cv2.imshow

### TASK-028
- **File:** `api/routers/identities.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — router import OK; GET/PUT/DELETE/POST enroll routes; IdentityResponse + IdentityUpdate schemas; 404 on missing; 204 on delete; lazy FaceRecognizer singleton; registered in main.py

### TASK-027
- **File:** `engine/storage/db.py` (update — identity functions)
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — upsert_identity (with last_cam param), get_identities, update_identity_name, delete_identity all import OK

### TASK-026
- **File:** `engine/vision/face.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — FaceRecognizer, FaceResult import OK; InsightFace buffalo_l with GPU/CPU fallback; cosine similarity > 0.6; quality threshold from settings; daemon thread DB write in enroll; RLock thread-safety; graceful fallback if insightface missing

### TASK-025
- **File:** `engine/vision/reid.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — ReIDEngine import OK; FAISS IndexFlatIP; CLAHE preprocessing; EMA α=0.90; lost_pool 30s TTL; cosine threshold 0.75; torchreid graceful fallback; RLock thread-safety

### TASK-024
- **Files:** `engine/config.py` + `api/main.py` updated
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — syntax OK; startup_cameras field present with empty default; _load_startup_cameras() skips already-registered cams; parse error logs WARNING and continues; zones + events routers registered in main.py

### TASK-023
- **Files:** `dashboard/src/pages/Cameras.jsx` (new) + `dashboard/src/App.jsx` updated
- **Assigned to:** react-builder
- **Completed:** 2026-03-07
- **Test:** PASS — npm run build succeeds (49 modules, 0 errors); Add Camera form with 409 conflict handling; table with status dots, URL, added_at; Delete with confirm(); 10s auto-refresh; /cameras route + nav link added

### TASK-022
- **Files:** `dashboard/src/pages/Events.jsx`, `dashboard/src/components/ZoneOverlay.jsx`, updated `LiveView.jsx` + `App.jsx`
- **Assigned to:** react-builder
- **Completed:** 2026-03-07
- **Test:** PASS — `npm run build` succeeds (48 modules, 0 errors); Events.jsx paginated table + filter bar + modal; ZoneOverlay SVG with hex→rgba, triggered zones red 30%, others 20%; CameraCard fetches zones on mount; /events route + nav link in App.jsx; react-router-dom installed

### TASK-021
- **File:** `api/services/db_service.py`
- **Assigned to:** haiku-writer
- **Completed:** 2026-03-07
- **Test:** PASS — get_events, get_stats import OK; all 5 functions re-exported; module-level docstring

### TASK-020
- **File:** `engine/pipeline.py` (Phase 2 zone + alert wiring)
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS (asyncio context) — zone_manager/alert_manager optional params; backward compat confirmed; check_intrusions called after tracker.update(); dispatch called per intrusion; triggered zones drawn red with 0.3 alpha fill; non-triggered use zone.color hex→BGR; cv2.polylines outline; zone label at centroid; no time.sleep/cv2.imshow

### TASK-019
- **File:** `api/routers/events.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — syntax OK; router imports OK; GET /api/events paginated with all filters; since parsed via fromisoformat(); GET /api/events/{id} with 404; GET /api/snapshots/{path:path} FileResponse with 404; EventResponse schema covers all events table fields; all DB calls async

### TASK-018
- **File:** `api/routers/zones.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — syntax OK; router imports OK; GET/POST/PUT/DELETE routes; Pydantic ZoneCreate/ZoneUpdate/ZoneResponse schemas; lazy ZoneManager singleton; DB + zones.json sync; reload() called on all mutations; 404 on missing zone_id

### TASK-017
- **File:** `engine/manager.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — MultiCamManager imports OK; RLock thread-safety; ValueError on duplicate; WARNING if >4 cams; remove_camera joins with 5s timeout; restore_cameras reads cameras.json; stop_all stops all pipelines; atomic JSON persist via tmp file

### TASK-016
- **File:** `engine/alerts/manager.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-07
- **Test:** PASS — AlertManager, AlertType, Alert import OK; cooldown logic correct; WEAPON bypass; FACE_MATCH 300s; daemon thread dispatch; RLock thread-safety; asyncio.run_coroutine_threadsafe for WS/DB

### TASK-015
- **File:** `engine/zones/manager.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — ZoneManager/Zone/ZoneIntrusion import OK, bottom-center formula correct, RLock thread-safety, atomic writes, watchdog hot-reload with fallback

### TASK-014
- **File:** `engine/zones/geometry.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — point_in_polygon ray-casting correct, compute_iou correct, edge cases handled, import OK

### TASK-013
- **File:** `dashboard/src/pages/LiveView.jsx` + scaffold
- **Assigned to:** react-builder
- **Completed:** 2026-03-06
- **Test:** PASS — `npm run build` succeeds (34 modules, 0 errors), LiveView renders camera grid + event sidebar + weapon alarm banner + WS connection

### TASK-012
- **File:** `api/services/camera_service.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — Syntax OK, all 8 required methods present, RLock thread-safety, cameras.json persistence, restore_cameras/stop_all lifecycle, module-level singleton

### TASK-011
- **File:** `api/routers/cameras.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — Syntax OK, POST/DELETE/GET/PATCH routes, Pydantic schemas, 409 on duplicate, 404 on missing, lazy camera_service import

### TASK-010
- **File:** `api/routers/stream.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — Syntax OK, StreamingResponse from MJPEGBuffer.frame_generator(), 404 on unknown cam_id, multipart/x-mixed-replace content-type

### TASK-009
- **File:** `api/main.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — Syntax OK, FastAPI lifespan with init_db + camera_service.restore_cameras/stop_all, CORS middleware, routers registered under /api prefix

### TASK-008
- **File:** `engine/pipeline.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — CameraPipeline interface correct, daemon thread, no time.sleep, detect->track->annotate->push loop, green person boxes/red weapon boxes, FPS status bar, stop() joins cleanly

### TASK-007
- **File:** `engine/storage/snapshots.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — save_snapshot interface correct, path format matches SPEC, JPEG quality 85, makedirs with exist_ok, returns relative path, no blocking calls

### TASK-006
- **File:** `engine/storage/db.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — All 4 tables created (events/identities/cameras/zones), full SPEC schema, all 5 async functions implemented, JSON serialization correct, aiosqlite throughout

### TASK-005
- **File:** `engine/stream/mjpeg.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — MJPEGBuffer interface correct, asyncio.Queue(maxsize=2), non-blocking push with oldest-frame drop, multipart format verified, CancelledError handled

### TASK-004
- **File:** `engine/vision/tracker.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — Track dataclass correct (track_id/bbox/confidence), Tracker.update() interface verified, boxmot BoT-SORT primary with graceful fallback, persons-only filter (class_id==0)

### TASK-003
- **File:** `engine/vision/detector.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — Detection dataclass correct, is_person/is_weapon helpers verified, CUDA fallback present, verbose=False

### TASK-002
- **File:** `engine/stream/source.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — interface verified, no time.sleep, threading.Event used, CAP_PROP_BUFFERSIZE=1 set, daemon=True

### TASK-001
- **File:** `engine/config.py`
- **Assigned to:** gemini-coder
- **Completed:** 2026-03-06
- **Test:** PASS — `from engine.config import settings` returns all 20 fields with correct defaults

---

## Session Log

### Session 15 — 2026-03-12
- Phase 10 (Security Hardening & Bug Fixes) planned from Principal Engineer Audit Report
- Read 16 files, cross-referenced all 19 audit items against current codebase
- PRE-FLIGHT FINDING: 15 of 19 audit items already resolved in current code
  - A1-A5 (critical security): all fixed (JWT validator, bcrypt, auth on stream/snapshot, SSRF validation)
  - B1,B3,B4,B5,B6,B7,B8 (major): all fixed (ThreadPoolExecutor, dedup removed, BLOB, timezone.utc, MAX_CAMERAS enforced, slowapi, asyncio.Lock)
  - C1,C3,C4 (medium): all fixed (run_coroutine_threadsafe, deque, watchdog stop)
- 4 genuine gaps remain → TASK-068 through TASK-071
- Agent breakdown: 3x haiku-writer (068, 070, 071), 1x gemini-coder (069)
- Dependency: TASK-069 → TASK-070; TASK-068 and TASK-071 independent

### Session 14 — 2026-03-09
- Full gap audit: read ZoneEditor.jsx, test_ws_auth.py, Login.jsx, api/middleware/auth.py, engine/storage/db.py
- Cross-referenced SPEC.md Sections 9, 10, 11, 12, and 14 exhaustively
- All 5 files confirmed present and complete on disk
- ZoneEditor.jsx: all TASK-067 requirements met (SVG overlay, drag, debounce, coordinate scaling)
- test_ws_auth.py: all 3 WS auth test cases present (no token, bad token, valid token)
- Login.jsx, api/middleware/auth.py: JWT auth stack fully implemented
- engine/storage/db.py: PostgreSQL dual-backend confirmed (_USE_PG flag, asyncpg pool)
- NO GAPS FOUND — all SPEC.md requirements are implemented. 0 new tasks queued.

### Session 13 — 2026-03-08
- Phase 9 final gap audit: complete filesystem scan of all 66 COMPLETED tasks vs SPEC.md
- All engine/, api/, dashboard/, tests/, Docker files confirmed present on disk
- 1 genuine gap found: `dashboard/src/components/ZoneEditor.jsx`
  - SPEC.md Section 10 defines it as a distinct named component with vertex dragging
  - Zones.jsx provides inline SVG polygon drawing but lacks vertex drag and is not a reusable component
- 1 task queued: TASK-067 (react-builder, no dependencies)

### Session 12 — 2026-03-08
- Phase 8 gap audit: read 9 files across dashboard + backend + tests
- Auth header audit: ALL dashboard pages route 100% of API calls through useStore store actions; Bearer tokens injected centrally; zero bare fetch() calls. No auth gaps.
- Analytics.jsx: real API calls via store actions; no mock data. Complete.
- EventFeed.jsx / CameraCard.jsx: inline in LiveView.jsx — functionally complete, not a gap.
- 3 genuine gaps found → TASK-064 through TASK-066:
  - TASK-064 (bug): useStore.fetchEvents error return is `{ events: [], total: 0 }` — truthy non-array causes TypeError on `.slice()`/`.forEach()`. Fix: return `null`.
  - TASK-065 (spec gap): Events.jsx missing CSV export. SPEC.md Section 10 explicitly requires it.
  - TASK-066 (test gap): ws.py 4001 close path is untested. test_api_integration.py covers REST only.
- Dependency order: TASK-064 → TASK-065 (both react-builder); TASK-066 independent (gemini-coder)

### Session 11 — 2026-03-08
- Phase 7 (Dashboard Auth & UX Polish) COMPLETED: 5 tasks (TASK-059 through TASK-063)
- useStore.js: Added token state, login/logout actions, and updated all fetch/websocket calls with auth.
- Login.jsx: Created new login page with styling matching the dashboard.
- App.jsx: Implemented ProtectedRoute, added /login route, and integrated Logout button in nav.
- LiveView.jsx: Updated CameraCard zones fetch with auth header.
- ws.py: Implemented JWT token-as-query-param authentication for WebSockets.
- UX Refactor: Centralized all dashboard API calls into useStore actions for cleaner maintenance and consistent auth.

### Session 10 — 2026-03-08
- Phase 6 (Testing, Auth & Performance) planned: 6 tasks queued (TASK-053 through TASK-058)
- Audit: useStore.js EXISTS + complete; all engine/ subdirectory __init__.py files EXIST; only .env.example was missing
- Agent breakdown: 1x haiku-writer (TASK-053), 5x gemini-coder (TASK-054 through TASK-058)
- Dependency order: TASK-053 → TASK-054 → TASK-055 → TASK-056 → TASK-057; TASK-058 independent
- First task: TASK-053 (.env.example, haiku-writer)

### Session 9 — 2026-03-08
- Full gap audit across all 48 COMPLETED tasks vs SPEC.md and filesystem
- 4 gaps identified: api/__init__.py, api/routers/__init__.py, api/services/__init__.py (missing package markers), api/routers/stats.py (never built, explicitly in SPEC Section 9)
- 4 new tasks queued: TASK-049 (gemini-coder), TASK-050/051/052 (haiku-writer)
- Dependency order: TASK-050 → TASK-051, TASK-052 → TASK-049

### Session 8 — 2026-03-08
- Phase 4 assessment: 3 tasks remain OPEN (TASK-039 pipeline wiring, TASK-040 alerts router, TASK-041 AlertBanner+Alerts+Analytics); TASK-033 IN PROGRESS (face.py tuning); TASK-034 OPEN (Re-ID smoke tests)
- Phase 5 planned: 7 tasks queued (TASK-042 through TASK-048)
- Agent assignments: gemini-coder (TASK-042/043/044/045), react-builder (TASK-046), haiku-writer (TASK-047/048)
- Dependency order: TASK-047 (requirements.txt) → TASK-042 (db.py PG migration) → TASK-043/044/045 (Docker); TASK-046 (Zones.jsx) independent

### Session 7 — 2026-03-07
- Phase 4 planned: 7 tasks queued (TASK-035 through TASK-041)
- weapon.py, anomaly.py, email.py, webhook.py, pipeline wiring, alerts API, dashboard AlertBanner + Alerts + Analytics pages

### Session 6 — 2026-03-07
- Phase 3.1 accuracy improvements started
- TASK-031 (reid.py tuning) COMPLETED: CLAHE 3.0, EMA 0.95, threshold 0.80, gallery TTL 300s
- TASK-032 (face.py tuning) IN PROGRESS

### Session 5 — 2026-03-07
- Phase 3 accuracy diagnosis: Re-ID false positives ~40-50%, face match rate <60%
- Queued 4 tasks (TASK-031 through TASK-034): CLAHE 3.0, EMA 0.95, gallery TTL 300s, threshold 0.80, quality gates, Re-ID+face fusion, smoke tests

### Session 4 — 2026-03-07
- Phase 3 planned: 6 tasks queued (TASK-025 through TASK-030)
- Re-ID (OSNet-AIN + FAISS), Face (InsightFace buffalo_l), DB identity functions, identities API, pipeline wiring, Identities dashboard page

### Session 3 — 2026-03-07
- Phase 2 fully COMPLETED (TASK-017 through TASK-022 all PASS)
- User request: add camera management via frontend UI + .env auto-boot
- Queued TASK-023 (Cameras.jsx UI) and TASK-024 (.env startup_cameras)

### Session 2 — 2026-03-06
- Phase 1 confirmed fully COMPLETED (all 13 tasks PASS)
- Orchestrator queued 9 Phase 2 tasks (TASK-014 through TASK-022)

### Session 1 — 2026-03-06
- Setup repo, CLAUDE.md, SPEC.md, agent files
- Orchestrator queued 13 Phase 1 tasks (TASK-001 through TASK-013)

