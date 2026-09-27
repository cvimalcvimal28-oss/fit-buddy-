"""
models.py
Database tables: User and WorkoutPlan (original + updated plan, nutrition tip, feedback).
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String(254), unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    weight = Column(Integer, nullable=False)
    fitness_goal = Column(String, nullable=False)
    workout_intensity = Column(String, nullable=False)
    password_hash = Column(String(256), nullable=True)
    mobile_phone = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    plans = relationship("WorkoutPlan", back_populates="user", cascade="all, delete-orphan")
    feedback_entries = relationship("UserFeedback", back_populates="user", cascade="all, delete-orphan")


class WorkoutPlan(Base):
    __tablename__ = "workout_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    original_plan = Column(Text, nullable=False)
    nutrition_tip = Column(Text, nullable=True)

    feedback = Column(Text, nullable=True)
    updated_plan = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="plans")


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    category = Column(String(40), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="feedback_entries")


class DietChatMessage(Base):
    __tablename__ = "diet_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_digest = Column(String(64), unique=True, nullable=False, index=True)
    token_salt = Column(String(32), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(32), unique=True, nullable=False)
    email = Column(String(254), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=False)
    name = Column(String(80), nullable=False)
    age = Column(Integer, nullable=False)
    weight = Column(Integer, nullable=False)
    fitness_goal = Column(String, nullable=False)
    workout_intensity = Column(String, nullable=False)
    password_hash = Column(String(256), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
