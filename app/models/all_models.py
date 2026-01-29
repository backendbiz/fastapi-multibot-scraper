"""
SQLAlchemy models.
Currently empty as the main bot functionality uses external APIs.
Add models here as needed for storing bot transactions, logs, etc.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


# Example model for future use - Bot Transaction Log
# Uncomment and modify as needed
#
# class BotTransaction(Base):
#     __tablename__ = "bot_transactions"
#
#     id: Mapped[str] = mapped_column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
#     game_name: Mapped[str] = mapped_column(String, index=True)
#     action_type: Mapped[str] = mapped_column(String)  # deposit, redeem, signup, balance
#     username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
#     amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
#     status: Mapped[str] = mapped_column(String)  # success, error
#     message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
#     
#     created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
