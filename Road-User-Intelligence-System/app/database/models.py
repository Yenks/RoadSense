"""
Database models — Week 8.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.orm import declarative_base
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_name = Column(String, nullable=False)
    track_id = Column(Integer, nullable=False)
    vehicle_class = Column(String, nullable=False)
    is_rider = Column(Integer, default=0)
    entry_time_sec = Column(Float, nullable=False)
    exit_time_sec = Column(Float, nullable=False)
    max_speed_kmh = Column(Float, nullable=True)
    avg_speed_kmh = Column(Float, nullable=True)


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_name = Column(String, nullable=False)
    track_id = Column(Integer, nullable=False)
    vehicle_class = Column(String, nullable=False)
    violation_type = Column(String, nullable=False)
    timestamp_sec = Column(Float, nullable=False)
    speed_kmh = Column(Float, nullable=False)
    threshold_kmh = Column(Float, nullable=False)
    snapshot_path = Column(String, nullable=True)


class SessionSummary(Base):
    __tablename__ = "session_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_name = Column(String, nullable=False, unique=True)
    duration_sec = Column(Float, nullable=False)
    total_vehicles = Column(Integer, nullable=False)
    avg_speed_kmh = Column(Float, nullable=True)
    peak_speed_kmh = Column(Float, nullable=True)
    total_violations = Column(Integer, nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)