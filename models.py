from sqlalchemy import Column, Integer, String, Float, BigInteger, Boolean, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    role = Column(String(20), nullable=False)  # customer / installer
    name = Column(String(100))
    username = Column(String(100))
    is_admin = Column(Boolean, default=False)

    requests = relationship("Request", back_populates="customer", foreign_keys="Request.customer_id")
    assigned_requests = relationship("Request", back_populates="installer", foreign_keys="Request.installer_id")
    refusals = relationship("Refusal", back_populates="installer")

class District(Base):
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    requests = relationship("Request", back_populates="district")

class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(Text, nullable=False)
    photos = Column(Text)  # JSON-строка с file_id через запятую или список
    address = Column(String(200))
    latitude = Column(Float)
    longitude = Column(Float)
    phone = Column(String(20))
    district_id = Column(Integer, ForeignKey("districts.id"))
    status = Column(String(20), default="new")  # new, in_progress, completed
    installer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    taken_at = Column(DateTime)
    completed_at = Column(DateTime)

    customer = relationship("User", foreign_keys=[customer_id], back_populates="requests")
    installer = relationship("User", foreign_keys=[installer_id], back_populates="assigned_requests")
    district = relationship("District", back_populates="requests")
    group_messages = relationship("GroupMessage", back_populates="request")
    refusals = relationship("Refusal", back_populates="request")

class Refusal(Base):
    __tablename__ = "refusals"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    installer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    request = relationship("Request", back_populates="refusals")
    installer = relationship("User", back_populates="refusals")

class GroupMessage(Base):
    __tablename__ = "group_messages"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    message_id = Column(Integer, nullable=False)

    request = relationship("Request", back_populates="group_messages")

class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    id = Column(Integer, primary_key=True)
    lat = Column(Float)
    lon = Column(Float)
    address = Column(String(200))
    created_at = Column(DateTime, server_default=func.now())