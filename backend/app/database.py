"""
Database layer.

Uses SQLite by default (zero-config, runs anywhere) via SQLAlchemy.
Swap DATABASE_URL in .env to a Postgres/Supabase connection string to
move to production — the schema and ORM code do not need to change.
"""
import os
import json
import datetime as dt
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./scholarai.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class StudentRecord(Base):
    __tablename__ = "students"
    id = Column(String, primary_key=True)
    profile_json = Column(Text)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class ScholarshipRecord(Base):
    __tablename__ = "scholarships"
    id = Column(String, primary_key=True)
    name = Column(String)
    provider = Column(String)
    data_json = Column(Text)  # full record, since schema is rich/nested


class EligibilityRuleLog(Base):
    __tablename__ = "eligibility_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"))
    scholarship_id = Column(String, ForeignKey("scholarships.id"))
    result_json = Column(Text)


class DocumentRecord(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"))
    document_name = Column(String)
    status = Column(String, default="Missing")


class ApplicationRecord(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.id"))
    scholarship_id = Column(String, ForeignKey("scholarships.id"))
    status = Column(String, default="Not Started")


class DeadlineRecord(Base):
    __tablename__ = "deadlines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scholarship_id = Column(String, ForeignKey("scholarships.id"))
    deadline = Column(String)
    priority = Column(String)


class AgentLogRecord(Base):
    __tablename__ = "agent_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String)
    agent = Column(String)
    message = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    _seed_scholarships_if_empty()


def _seed_scholarships_if_empty():
    db = SessionLocal()
    try:
        count = db.query(ScholarshipRecord).count()
        if count == 0:
            data_path = os.path.join(os.path.dirname(__file__), "data", "scholarships.json")
            with open(data_path, "r", encoding="utf-8") as f:
                scholarships = json.load(f)
            for s in scholarships:
                db.add(ScholarshipRecord(
                    id=s["id"], name=s["name"], provider=s["provider"],
                    data_json=json.dumps(s)
                ))
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upsert_live_scholarships(records: list) -> dict:
    """
    Persists discovered/converted scholarship records (internal schema)
    into the scholarships table. Returns which ids were newly added vs.
    updated vs. left unchanged, for the Discovery Agent's final report.
    """
    db = SessionLocal()
    newly_added, updated, unchanged = [], [], []
    try:
        for rec in records:
            data_str = json.dumps(rec, sort_keys=True)
            existing = db.query(ScholarshipRecord).filter(ScholarshipRecord.id == rec["id"]).first()
            if existing is None:
                db.add(ScholarshipRecord(
                    id=rec["id"], name=rec["name"], provider=rec["provider"], data_json=data_str
                ))
                newly_added.append(rec["id"])
            elif existing.data_json != data_str:
                existing.name = rec["name"]
                existing.provider = rec["provider"]
                existing.data_json = data_str
                updated.append(rec["id"])
            else:
                unchanged.append(rec["id"])
        db.commit()
    finally:
        db.close()
    return {"newly_added": newly_added, "updated": updated, "unchanged": unchanged}


def mark_expired_scholarships() -> int:
    """
    Sweeps stored live scholarships (id starting with 'LIVE-') whose
    deadline has passed and flips their verification_status to EXPIRED
    if it isn't already -- the cheap half of "continuous update"
    (detecting expiry) that needs no re-fetching of the source page.
    Returns how many records were newly marked expired.
    """
    import datetime as dt
    db = SessionLocal()
    count = 0
    try:
        rows = db.query(ScholarshipRecord).filter(ScholarshipRecord.id.like("LIVE-%")).all()
        today = dt.date.today()
        for row in rows:
            rec = json.loads(row.data_json)
            deadline = rec.get("application_deadline")
            if not deadline or rec.get("verification_status") == "EXPIRED":
                continue
            try:
                deadline_date = dt.datetime.strptime(deadline, "%Y-%m-%d").date()
            except Exception:
                continue
            if deadline_date < today:
                rec["verification_status"] = "EXPIRED"
                rec["source_type"] = "EXPIRED"
                row.data_json = json.dumps(rec, sort_keys=True)
                count += 1
        db.commit()
    finally:
        db.close()
    return count
