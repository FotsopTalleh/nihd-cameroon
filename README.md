# NIHD — National Internet Health Dashboard
## Complete Implementation Breakdown

> **Project:** Final Year B.Tech project — monitoring internet connectivity quality across 10 regions of Cameroon, across 4 ISPs, in real time.

---

## 📚 Library Inventory & Why Each Was Chosen

### Backend (Python / Flask ecosystem)

| Library | Why It's Here |
|---|---|
| **Flask 3.0** | Core web framework. Serves both the HTML pages (Jinja2 templates) and the REST API endpoints. Lightweight enough for a single-developer project but has a mature extension ecosystem. |
| **Flask-SQLAlchemy** | ORM layer over SQLAlchemy. Maps Python classes (`Measurement`, `Alert`, `User`, `Download`) to SQL tables, lets you write `Measurement.query.filter(...)` instead of raw SQL. Supports SQLite locally and PostgreSQL in production with zero code changes. |
| **Flask-Login** | Session-based authentication. Manages the logged-in user across requests via a secure cookie. Provides `@login_required` decorator and `current_user` proxy. Only needed for protected routes (CSV/PDF download). The dashboard itself is **public** — anyone can view data without an account. |
| **Flask-Bcrypt** | Wraps `bcrypt` for password hashing. `bcrypt.generate_password_hash()` on registration, `bcrypt.check_password_hash()` on login. Chosen because bcrypt is adaptive (the work factor can be increased as hardware gets faster). |
| **Flask-SocketIO** | WebSocket support for real-time live updates. When the probe agent finishes a measurement cycle, it emits events directly to all connected browser tabs — no polling required. |
| **Flask-WTF / WTForms** | CSRF protection and form validation on the auth forms. Prevents cross-site request forgery on login/register. |
| **SQLAlchemy 2.0** | The underlying ORM. `db.session.bulk_save_objects(batch)` is used in the seeder for fast batch inserts (thousands of rows at once). |
| **eventlet** | An async I/O library that monkey-patches Python's stdlib (`socket`, `ssl`, `threading`, etc.) to be non-blocking. **Required** for Flask-SocketIO's `async_mode='eventlet'` — this is what allows the server to handle hundreds of simultaneous WebSocket connections without spawning a thread per connection. Must be imported and monkey-patched **before everything else** in `app.py`. |
| **APScheduler** | Background job scheduler. Runs `run_probe_cycle()` every 30 seconds inside the Flask process (no separate Celery worker needed). `max_instances=1` prevents overlapping runs if a cycle takes longer than 30 seconds. |
| **ReportLab** | PDF generation library. Builds professional A4 PDFs with branded headers, styled tables, executive summaries, and per-region breakdowns. Uses `SimpleDocTemplate`, `Paragraph`, `Table`, and `TableStyle` from its `platypus` layout engine. |
| **pandas** | Listed in requirements — available for potential CSV generation and data analysis. The CSV generator uses Python's stdlib `csv` module in practice, but pandas is available for more complex aggregations. |
| **python-dotenv** | Loads `.env` file into environment variables for local development. In production (Railway/Render), real environment variables are injected directly. |
| **subprocess** (stdlib) | Used by the probe agent to run system `ping` commands (`ping -n 4` on Windows, `ping -c 4` on Linux). Cross-platform ping via the OS CLI. |
| **re** (stdlib) | Regex parsing of ping output to extract average latency and packet loss percentages from the platform-specific text format. |

### Frontend (Jinja2 Templates + CDN Libraries)

| Library | Why It's Here |
|---|---|
| **Bootstrap 5** | Responsive grid, navbar, cards, badges, pagination, modals. The entire UI is built on Bootstrap components — it's a data dashboard where content matters more than custom design, so Bootstrap's utility-first approach is appropriate. |
| **Bootstrap Icons** | Icon font used throughout the UI (`bi-wifi`, `bi-exclamation-triangle`, etc.) for visual status indicators. |
| **Chart.js** | Client-side charting library. Powers the real-time latency line chart, uptime trend charts, and ISP comparison bar charts. Used via CDN. Each page that needs charts initializes a `Chart` instance from JSON data rendered by Jinja2 or fetched via the API. |
| **Socket.IO JS client** | The browser-side WebSocket client. Connects to the Flask-SocketIO server, listens for `kpi_update`, `region_update`, `probe_status`, and `new_alert` events, and updates the DOM in real time without page refresh. |
| **DataTables** (implied by usage) | Used on the historical and regional pages for sortable, filterable measurement tables. |

---

## 🗂️ Database Schema (4 Tables)

The DB is **SQLite** locally (`instance/dashboard.db`) and **PostgreSQL** in production (Railway injects `DATABASE_URL`). The `config.py` handles the `postgres://` → `postgresql://` rewrite for legacy Heroku-style URLs.

```
users
  id          INTEGER PK
  email       VARCHAR(150) UNIQUE
  password_hash VARCHAR(256)
  full_name   VARCHAR(150)
  organization VARCHAR(150)
  created_at  DATETIME
  is_active   BOOLEAN
  → downloads (one-to-many)

measurements
  id            INTEGER PK
  region        VARCHAR(100)  ← one of 10 Cameroon regions
  isp           VARCHAR(100)  ← Camtel / MTN / Orange / Nexttel
  latency       FLOAT (ms)
  packet_loss   FLOAT (%)
  uptime        FLOAT (%)
  download_speed FLOAT (Mbps)
  upload_speed  FLOAT (Mbps)
  jitter        FLOAT (ms)
  timestamp     DATETIME

traceroutes
  id            INTEGER PK
  source        VARCHAR(150)  ← e.g. "Yaoundé (Centre)"
  destination   VARCHAR(150)  ← e.g. "8.8.8.8 (Google DNS)"
  hops          TEXT          ← JSON-serialized list of hop dicts
  total_hops    INTEGER
  total_latency FLOAT (ms)
  timestamp     DATETIME

alerts
  id          INTEGER PK
  type        VARCHAR(100)   ← "High Latency Detected", "Packet Loss Spike", "Uptime Drop"
  severity    VARCHAR(20)    ← "critical", "warning", "info"
  region      VARCHAR(100)
  message     TEXT
  is_resolved BOOLEAN
  resolved_at DATETIME
  timestamp   DATETIME

downloads
  id          INTEGER PK
  user_id     INTEGER FK → users.id
  file_type   VARCHAR(10)  ← "pdf" or "csv"
  region      VARCHAR(100)
  file_path   VARCHAR(500)
  file_name   VARCHAR(200)
  file_size   INTEGER (bytes)
  created_at  DATETIME
```

---

## 🔄 Data Flow — From Probe to Dashboard

### Step 0 — App Startup (`app.py → create_app()`)

```
eventlet.monkey_patch()     ← MUST run first, before any stdlib imports
Flask app created
  ├─ db.init_app(app)          SQLAlchemy connected
  ├─ bcrypt.init_app(app)      Password hashing ready
  ├─ login_manager.init_app()  Session auth ready
  ├─ socketio.init_app(app)    WebSocket server ready
  ├─ Register 4 Blueprints:
  │    /auth    → auth_bp      login / register / logout
  │    /        → dashboard_bp index, /regions, /traceroute, /historical, /alerts, /sources, /about
  │    /        → api_bp       JSON API endpoints
  │    /        → download_bp  CSV/PDF download (login required)
  ├─ Register SocketIO events  (connect, disconnect, request_latest)
  ├─ db.create_all()           Create tables if not exist
  ├─ seed_database()           Insert sample data if DB is empty
  └─ _start_probe_scheduler()  APScheduler → run_probe_cycle every 30s
```

---

### Step 1 — Database Seeding (First Boot Only)

`utils/seed_data.py → seed_database()`:
- Checks `if Measurement.query.first(): return` — runs only once
- Generates **30 days of historical data** (every 2 hours, 10 regions × 2 random ISPs = ~7,200 `Measurement` rows)
- Each measurement is computed from a `REGION_PROFILE` (base latency/uptime/loss for that region) × an `ISP_MULTIPLIER` × a time-of-day peak factor (1.3× during 8am–10pm) + Gaussian noise
- Generates 30 sample `Alert` records (all pre-resolved — only live probe creates active alerts)
- Generates 30 sample `Traceroute` records with realistic hop chains (local gateway → ISP edge → AFRIXP → JINX → SEACOM → Google DNS)
- Uses `db.session.bulk_save_objects(batch)` for fast bulk insert (one SQL INSERT per batch, not per row)

**Why seed data?** The dashboard looks meaningful immediately, even before the probe agent has collected enough live data. Visitors see 30 days of historical trends, not an empty chart.

---

### Step 2 — Live Probe Cycle (Every 30 Seconds)

`utils/probe_agent.py → run_probe_cycle(app, socketio)`:

**2a. Real ping to internet hosts:**
```python
PING_TARGETS = ['8.8.8.8', '1.1.1.1', '208.67.222.222']  # Google, Cloudflare, OpenDNS
```
For each target, `subprocess.run(['ping', '-n', '3', host], ...)` is called.
The output is regex-parsed:
- Windows: `Average = 45ms` → latency; `Lost = 1 (25% loss)` → packet_loss
- Linux: `rtt min/avg/max = .../45.2/...` → latency; `25% packet loss` → packet_loss

The 3 targets are averaged together to get a **base measurement** representing the current real-world network conditions from the machine running the server.

**2b. Derive per-region measurements:**
```
for each of 10 regions:
    pick a random ISP
    latency  = base_latency × region_factor × isp_lat_mult + Gaussian noise
    loss     = base_loss    × isp_loss_mult + region_loss_add + Gaussian noise
    uptime   = region_uptime_base + Gaussian noise
    dl_speed = random.uniform(1, 50) × (1 / isp_lat_mult)
    jitter   = latency × 0.15 + Gaussian noise
```

**Region factors** (realistic multipliers reflecting geographic reality):
| Region | Latency Factor | Why |
|---|---|---|
| Douala (Littoral) | 0.90× | Best-connected city, undersea cable proximity |
| Yaoundé (Centre) | 1.00× | Baseline — capital city |
| Maroua (Far North) | 2.90× | Most remote, worst infrastructure |
| Garoua (North) | 2.10× | Northern connectivity gap |

**ISP multipliers** also apply on top:
- MTN Cameroon: 0.90× latency (best performing mobile)
- Camtel: 1.30× latency (state ISP, older infrastructure)

**2c. Persist to DB:**
All 10 `Measurement` objects are added to the SQLAlchemy session and committed in one transaction.

**2d. Alert checking:**
Only measurements breaching significant thresholds trigger `check_and_raise_alerts()`:
```
latency > 300ms → check alert thresholds
packet_loss > 10% → check alert thresholds
uptime < 90% → check alert thresholds
```

Inside `alert_checker.py → check_and_raise_alerts()`:
| Metric | Warning | Critical |
|---|---|---|
| Latency | ≥ 150ms | ≥ 250ms |
| Packet Loss | ≥ 3% | ≥ 8% |
| Uptime | ≤ 95% | ≤ 90% |

New `Alert` objects are created and committed. Note: thresholds in `probe_agent.py` are deliberately set higher (>300ms, >10%) to filter noise and only pass truly bad measurements to `alert_checker.py`.

**2e. Emit WebSocket events:**
```python
socketio.emit('kpi_update',    { avg_latency, avg_uptime, avg_packet_loss, active_alerts, timestamp })
socketio.emit('region_update', [ { name, isp, latency, packet_loss, uptime, status }, ... ])
socketio.emit('probe_status',  { status, last_run, base_latency, regions_probed, new_alerts })
```
If new alerts were raised:
```python
for alert in new_alerts:
    socketio.emit('new_alert', { type, severity, region, message, timestamp })
```

All connected browser clients receive these events **instantly** — no 30-second polling cycle on the client side.

---

### Step 3 — API Layer (`routes/api.py`)

These are pure JSON endpoints, called by Chart.js and the Socket.IO client for data that needs filtering:

| Endpoint | What It Returns |
|---|---|
| `GET /dashboard-data` | 24h national averages + per-region summary + 12-hour hourly latency/uptime buckets for the charts |
| `GET /api/region-data?region=&hours=` | Raw measurements for one region, filtered by time window |
| `GET /api/alerts-data?region=&severity=&resolved=` | Alert list with optional filters |
| `GET /api/regions-list` | Distinct region names from DB |
| `GET /api/traceroutes?source=&destination=` | Recent traceroute records |
| `GET /api/isp-comparison` | Per-ISP averages (latency, uptime, loss) for last 24h |
| `POST /submit/ping` | Ingest a measurement from an **external probe agent** (designed for future distributed probes deployed to actual Cameroon cities) |
| `POST /submit/traceroute` | Ingest a traceroute from external agent |

The `/submit/*` endpoints have no authentication — they're designed for probe agents to POST data. In a production deployment these would be secured with an API key.

---

### Step 4 — WebSocket Layer (`routes/socket_events.py`)

On browser connect:
1. `handle_connect()` fires, logs the connection
2. Client emits `request_latest` immediately after connecting
3. `handle_request_latest()` queries the DB for the last 24h of measurements and emits a `kpi_update` event back to that specific client only — so the dashboard isn't blank while waiting for the next 30-second probe cycle

The Socket.IO server runs on **eventlet** (async I/O) — this means a single server thread can handle many simultaneous WebSocket connections without blocking.

---

### Step 5 — Dashboard Rendering (`routes/dashboard.py` + Jinja2 Templates)

The dashboard is a **traditional Multi-Page Application** — each page is a Jinja2 template rendered server-side:

**`GET /` (Home/Overview)**
```python
active_alerts = Alert.query.filter_by(is_resolved=False).count()
region_stats  = _region_summary(hours=24)   # avg latency/uptime/loss per region from DB
render_template('index.html', region_stats=region_stats, active_alerts=active_alerts)
```
Jinja2 renders the KPI cards with actual data. The page also has:
- A Chart.js line chart for latency trends (data fetched from `/dashboard-data` via JS on load)
- A Socket.IO client that updates the KPI values in real time as probe cycles arrive

**`GET /regions?region=&hours=`**
- Queries measurements for the selected region and time window
- Computes per-ISP stats (latency, uptime, loss, status)
- Passes `measurements` as JSON to the template for Chart.js rendering
- Client-side Chart.js draws an area chart of latency over time

**`GET /historical`**
- Template only — all data is fetched client-side from `/api/region-data` via `fetch()`
- Chart.js renders historical trends per region and ISP

**`GET /alerts?page=&severity=&region=&resolved=`**
- SQLAlchemy pagination: `q.paginate(page=page, per_page=20)`
- Summary counts (critical/warning/info) shown in badge chips

**`GET /traceroute`**
- Fetches recent traceroutes from DB, renders hop table
- Each hop has: IP, hostname, AS number, location, latency, status

---

### Step 6 — Authentication & Downloads

**Authentication** (`routes/auth.py`):
- Register: form POST → validate email/password → `bcrypt.generate_password_hash()` → save `User` to DB → redirect to login
- Login: `User.query.filter_by(email=...).first()` → `bcrypt.check_password_hash()` → `login_user(user, remember=...)` → redirect to dashboard
- Session stored in Flask's signed cookie (`SECRET_KEY` from env)
- `@login_required` on download routes — Flask-Login redirects unauthorized users to `/auth/login`

**CSV Download** (`routes/download.py` + `utils/csv_generator.py`):
1. User clicks download (must be logged in)
2. `generate_csv(region, hours)` queries measurements, writes a CSV file to `downloads/` directory
3. A `Download` record is saved to DB with file path, size, user
4. `send_file(file_path, as_attachment=True)` streams the file to the browser
5. User can see their download history at `/my-downloads` and re-download files

**PDF Download** (`utils/pdf_generator.py`):
- Uses **ReportLab** to build an A4 PDF with:
  1. Branded header ("🌐 National Internet Health Dashboard")
  2. Report metadata (region, time period, generation timestamp)
  3. Executive Summary table (avg/min/max for latency, uptime, packet loss)
  4. Regional Performance Breakdown table (one row per region)
  5. Recent Measurements table (last 50 rows, timestamped)
  6. Active Alerts table (if any)
  7. Footer disclaimer
- Colors match the brand: `BRAND_BLUE = #1a73e8`, alternating `LIGHT_BLUE` and white row backgrounds

---

## 🚀 Deployment Architecture

```
Railway or Render (cloud)
  └─ Gunicorn + eventlet worker  (Procfile: web: gunicorn app:app)
       └─ Flask app (create_app())
            ├─ SQLite (local dev) or PostgreSQL (production via DATABASE_URL)
            ├─ Jinja2 HTML pages  → served by Flask
            ├─ /api/*             → JSON REST API
            ├─ WebSocket (/)      → Flask-SocketIO (eventlet async)
            └─ APScheduler thread → probe_cycle every 30s
                  └─ app.app_context() ensures SQLAlchemy session is available
                     inside the background thread
```

**Environment variables** (set on Railway/Render):
- `SECRET_KEY` — Flask session signing key
- `DATABASE_URL` — PostgreSQL connection string (auto-injected by Railway when you add a Postgres plugin)
- `FLASK_ENV` — set to `production` to disable debug mode

---

## 🔑 Key Design Decisions

### 1. Single-process architecture
APScheduler runs as a background thread inside the same Gunicorn process. No separate Celery worker, Redis, or message broker needed. Works on free-tier hosting because it's just one dyno.

### 2. Public dashboard, gated downloads
Anyone can view the internet data — that's intentional, it's a public research tool. Registration is only required to download CSV/PDF reports. This maximizes utility while giving you user tracking for the download feature.

### 3. Real ping + derived regional values
The probe actually pings `8.8.8.8`, `1.1.1.1`, and `208.67.222.222` from wherever the server is running. These real measurements are then scaled by region-specific multipliers to simulate what probes deployed across Cameroon would actually observe. This is the key methodological choice: one real machine producing realistic simulated multi-region data.

### 4. Gaussian noise on all derived values
`random.gauss(0, base * 0.08)` is added to every derived measurement. This makes time-series charts look like real network data (slight variation every 30s) rather than perfectly flat lines.

### 5. Seeded historical data
Without seed data, the dashboard would show empty charts for 30 days. The seed generates 30 days of realistic data so the historical view is meaningful from day one.

### 6. Traceroutes stored as JSON text
The `hops` column is `TEXT` containing a JSON array. This avoids a separate `TracerouteHop` table and a complex join. `to_dict()` deserializes it inline with `json.loads(self.hops)`.

### 7. `is_provisional` distinction
Seeded alerts are all `is_resolved=True` — they represent historical events. Only the live probe creates `is_resolved=False` alerts. This keeps the live alerts panel clean and meaningful.
