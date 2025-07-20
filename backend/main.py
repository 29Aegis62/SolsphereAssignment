import io
import csv
from fastapi import FastAPI,  Depends, Response, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from database import SessionLocal, MachineReport
from models import ReportIn, ReportOut

app = FastAPI(title="System Health Backend")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("Validation error:", exc.errors())
    print("Request body:", exc.body)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Accept report from agent
@app.post("/api/report", status_code=201)
def submit_report(report: ReportIn, db: Session = Depends(get_db)):
    record = MachineReport(**report.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}

# List latest status per machine
@app.get("/api/machines", response_model=List[ReportOut])
def list_latest(db: Session = Depends(get_db)):
    subq = db.query(
        MachineReport.machine_id,
        func.max(MachineReport.timestamp).label("max_ts")
    ).group_by(MachineReport.machine_id).subquery()

    q = db.query(MachineReport).join(
        subq,
        (MachineReport.machine_id == subq.c.machine_id) & 
        (MachineReport.timestamp == subq.c.max_ts)
    )
    return q.all()

# Filter API
@app.get("/api/machines/filter", response_model=List[ReportOut])
def filter_machines(
        platform: Optional[str] = None,
        os_updates_pending: Optional[bool] = None,
        disk_encrypted: Optional[bool] = None,
        antivirus_active: Optional[bool] = None,
        db: Session = Depends(get_db)
    ):
    subq = db.query(
        MachineReport.machine_id,
        func.max(MachineReport.timestamp).label("max_ts")
    ).group_by(MachineReport.machine_id).subquery()

    q = db.query(MachineReport).join(
        subq,
        (MachineReport.machine_id == subq.c.machine_id) &
        (MachineReport.timestamp == subq.c.max_ts)
    )
    # Add filters
    if platform is not None:
        q = q.filter(MachineReport.platform == platform)
    if os_updates_pending is not None:
        q = q.filter(MachineReport.os_updates_pending == os_updates_pending)
    if disk_encrypted is not None:
        q = q.filter(MachineReport.disk_encrypted == disk_encrypted)
    if antivirus_active is not None:
        q = q.filter(MachineReport.antivirus_active == antivirus_active)
    return q.all()

# CSV export endpoint
@app.get("/api/export")
def export_csv(db: Session = Depends(get_db)):
    reports = db.query(MachineReport).all()
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow([
        "machine_id", "timestamp", "platform", 
        "disk_encrypted", "os_updates_pending", 
        "antivirus_active", "sleep_timeout_min"
    ])
    for r in reports:
        writer.writerow([
            r.machine_id, r.timestamp, r.platform, 
            r.disk_encrypted, r.os_updates_pending,
            r.antivirus_active, r.sleep_timeout_min
        ])
    response = Response(content=stream.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=reports.csv"
    return response
