from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float
from .database import Base


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)

    user_email = Column(String, index=True)

    lab_name = Column(String, nullable=True)
    project_name = Column(String, nullable=True)
    molecule_name = Column(String, nullable=True)
    experiment_type = Column(String, nullable=True)
    instrument = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    p0_phase = Column(Float, nullable=True, default=74.0)
    p1_phase = Column(Float, nullable=True, default=0.0)

    original_filename = Column(String)
    stored_filename = Column(String)
    file_hash = Column(String)

    status = Column(String, default="Uploaded")
    analysis_summary = Column(Text, nullable=True)

    figure_filename = Column(String, nullable=True)
    report_filename = Column(String, nullable=True)

    certificate_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    title = Column(String, nullable=True)
    department = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    organization = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    policy_accepted = Column(String, nullable=False, default="false")
    approved = Column(String, nullable=False, default="false")
    status = Column(String, nullable=False, default="pending")
    registered_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
