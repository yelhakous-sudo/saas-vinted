import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    credits = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)

    scans = relationship("Scan", back_populates="user", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    category = Column(String(100))
    brands = Column(String(500))
    model = Column(String(200), default="")
    min_price = Column(Float, default=0)
    max_price = Column(Float, default=500)
    sizes = Column(String(200), default="")
    conditions = Column(String(200), default="")
    total_items = Column(Integer, default=0)
    opportunities_found = Column(Integer, default=0)
    avg_margin = Column(Float, default=0)
    avg_profit = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="scans")
    opportunities = relationship("Opportunity", back_populates="scan", cascade="all, delete-orphan")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False)
    vinted_item_id = Column(Integer)
    title = Column(String(500))
    brand = Column(String(200))
    product = Column(String(300))
    price = Column(Float)
    avg_price = Column(Float)
    resale_estimation = Column(Float)
    profit_estimation = Column(Float)
    margin_percentage = Column(Float)
    size = Column(String(100))
    condition = Column(String(100))
    url = Column(String(500))
    photo = Column(Text)
    favourites = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    scan = relationship("Scan", back_populates="opportunities")
