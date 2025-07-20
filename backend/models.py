from pydantic import BaseModel
from datetime import datetime

class ReportIn(BaseModel):
    machine_id: str
    timestamp: datetime
    platform: str
    disk_encrypted: bool
    os_updates_pending: bool
    antivirus_active: bool
    sleep_timeout_min: int

class ReportOut(ReportIn):
    id: int
