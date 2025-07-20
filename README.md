# System Health Monitoring Solution

This repository contains a backend FastAPI server and a cross-platform agent for collecting and reporting system health metrics.

---

## Folder Structure

```
backend/
  app/
    database.py
    health.db
    main.py
    models.py
    requirements.txt

agent/
  healthutil.py
  agent_cache.json
```

---

## Backend (`backend/app`)

### Description

A FastAPI application that receives, stores, filters, and exports system health reports from agents.

### Features

- **API Endpoints:**
  - `POST /api/report` — Accepts system health reports from agents.
  - `GET /api/machines` — Lists the latest status per machine.
  - `GET /api/machines/filter` — Filter machines by platform, update status, encryption, antivirus, etc.
  - `GET /api/export` — Exports all reports as CSV.

- **Database:** Uses SQLite via SQLAlchemy ORM.

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r ./backend/requirements.txt
   ```

2. **Run the server:**
   ```bash
   uvicorn main:app --reload
   ```

---

## Agent (`agent/`)

### Description

A Python script that collects system health information and sends it to the backend server.

### Features

- Checks disk encryption, OS updates, antivirus status, and sleep timeout.
- Cross-platform: Windows, macOS, Linux.
- Sends data only if system state has changed (uses a hash and cache).
- Configurable reporting interval.

### Setup & Usage

1. **Install dependencies:**
   ```bash
   pip install -r ./agent/requirements.txt
   ```

2. **Run the agent:**
   ```bash
   python ./agent/healthutil.py
   ```

3. **Configuration:**
   - Edit `API_ENDPOINT` and `INTERVAL_MINUTES` at the bottom of `healthutil.py` as needed.

---

## Notes

- Ensure the backend server is running and accessible to the agent.
- For production, use HTTPS for the API endpoint.
- The agent requires appropriate permissions to query system settings.
