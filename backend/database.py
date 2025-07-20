from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

DATABASE_URL = "sqlite:///./health.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class MachineReport(Base):
    __tablename__ = "machine_reports"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    platform = Column(String)
    disk_encrypted = Column(Boolean)
    os_updates_pending = Column(Boolean)
    antivirus_active = Column(Boolean)
    sleep_timeout_min = Column(Integer)

Base.metadata.create_all(bind=engine)
