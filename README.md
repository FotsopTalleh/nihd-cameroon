# National Internet Health Dashboard (NIHD)
## Republic of Cameroon

A production-ready, public-facing internet performance monitoring platform.

---

## Features

- **Public Dashboard** – No login required to view real-time metrics
- **10 Regions** – Monitors all major regions in Cameroon
- **4 ISPs** – Camtel, MTN Cameroon, Orange Cameroon, Nexttel
- **Authentication** – Registration/login for data downloads
- **PDF Reports** – Formatted reports via ReportLab
- **CSV Exports** – Raw data downloads
- **Download History** – Re-download past reports
- **REST API** – Endpoints for probe data submission

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- pip

### 2. Clone / Navigate to project

```bash
cd C:\Users\FP\Desktop\btech
```

### 3. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the application

```bash
python app.py
```

The app will start at: **http://localhost:5000**

The database is **auto-created** and **auto-seeded** with 30 days of realistic sample data on first run.

---

## Project Structure

```
btech/
├── app.py                  # Flask application factory + entrypoint
├── config.py               # Configuration (secret key, DB URI, etc.)
├── extensions.py           # SQLAlchemy, LoginManager, Bcrypt instances
├── models.py               # Database models (User, Measurement, Traceroute, Alert, Download)
├── requirements.txt        # Python dependencies
├── README.md
│
├── routes/
│   ├── auth.py             # POST /auth/register, /auth/login, GET /auth/logout
│   ├── dashboard.py        # Public page routes
│   ├── api.py              # REST API endpoints
│   └── download.py         # GET /download/csv, /download/pdf, /my-downloads
│
├── utils/
│   ├── pdf_generator.py    # ReportLab PDF generation
│   ├── csv_generator.py    # CSV export
│   └── seed_data.py        # Sample data seeder
│
├── templates/
│   ├── base.html           # Base layout (navbar, footer, flash messages)
│   ├── index.html          # Home dashboard (KPIs, charts, region status)
│   ├── regional.html       # Per-region detail page
│   ├── traceroute.html     # Traceroute path visualization
│   ├── historical.html     # Historical trends charts
│   ├── alerts.html         # Alerts & events table
│   ├── sources.html        # Data sources & methodology
│   ├── about.html          # About the project
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   └── downloads/
│       └── my_downloads.html
│
├── static/
│   ├── css/style.css       # Custom CSS
│   └── js/main.js          # Global JS utilities
│
├── instance/               # Auto-created — contains dashboard.db
└── downloads/              # Auto-created — stores generated PDF/CSV files
```

---

## API Endpoints

| Method | Endpoint              | Auth | Description                     |
|--------|-----------------------|------|---------------------------------|
| GET    | `/`                   | No   | Home dashboard                  |
| GET    | `/regions`            | No   | Regional dashboard              |
| GET    | `/traceroute`         | No   | Traceroute analysis             |
| GET    | `/historical`         | No   | Historical trends               |
| GET    | `/alerts`             | No   | Alerts & events                 |
| GET    | `/sources`            | No   | Data sources & methodology      |
| GET    | `/about`              | No   | About page                      |
| POST   | `/auth/register`      | No   | Create account                  |
| POST   | `/auth/login`         | No   | Login                           |
| GET    | `/auth/logout`        | Yes  | Logout                          |
| GET    | `/download/csv`       | Yes  | Download CSV data               |
| GET    | `/download/pdf`       | Yes  | Download PDF report             |
| GET    | `/my-downloads`       | Yes  | View download history           |
| POST   | `/submit/ping`        | No   | Submit measurement from probe   |
| POST   | `/submit/traceroute`  | No   | Submit traceroute result        |
| GET    | `/dashboard-data`     | No   | JSON: national stats (last 24h) |
| GET    | `/api/region-data`    | No   | JSON: per-region measurements   |
| GET    | `/api/alerts-data`    | No   | JSON: alert events              |
| GET    | `/api/traceroutes`    | No   | JSON: traceroute data           |
| GET    | `/api/isp-comparison` | No   | JSON: ISP comparison stats      |

---

## Download Endpoints — Query Parameters

```
/download/csv?region=Douala (Littoral)&hours=24
/download/pdf?region=Yaoundé (Centre)&hours=72
```

Both parameters are optional. Defaults: all regions, last 24 hours.

---

## Submitting Probe Data (API)

```bash
# Submit a ping measurement
curl -X POST http://localhost:5000/submit/ping \
  -H "Content-Type: application/json" \
  -d '{
    "region": "Douala (Littoral)",
    "isp": "MTN Cameroon",
    "latency": 42.5,
    "packet_loss": 0.3,
    "uptime": 99.8,
    "download_speed": 25.4,
    "upload_speed": 8.2,
    "jitter": 3.1
  }'
```

---

## Environment Variables

For production, set:

```
SECRET_KEY=your-very-secret-key-here
DATABASE_URL=sqlite:///path/to/dashboard.db
```

---

## Default Regions

| Region                 | City          | Profile |
|------------------------|---------------|---------|
| Yaoundé (Centre)       | Yaoundé       | Good    |
| Douala (Littoral)      | Douala        | Good    |
| Bafoussam (West)       | Bafoussam     | Fair    |
| Garoua (North)         | Garoua        | Fair    |
| Maroua (Far North)     | Maroua        | Poor    |
| Ngaoundéré (Adamawa)   | Ngaoundéré    | Fair    |
| Bertoua (East)         | Bertoua       | Fair    |
| Bamenda (Northwest)    | Bamenda       | Good    |
| Buea (Southwest)       | Buea          | Good    |
| Ebolowa (South)        | Ebolowa       | Fair    |

---

## License

This project is for educational and research purposes. Data provided is not intended for operational use.
