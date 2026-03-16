from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, 
    Text, ForeignKey, Enum, BigInteger, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

from database import Base
from config import (
    REQUEST_STATUS_NEW, REQUEST_STATUS_IN_PROGRESS,
    REQUEST_STATUS_COMPLETED, REQUEST_STATUS_CANCELLED,
    ROLE_CUSTOMER, ROLE_INSTALLER
)

# Enums для SQLAlchemy
class RequestStatus(enum.Enum):
    NEW = REQUEST_STATUS_NEW
    IN_PROGRESS = REQUEST_STATUS_IN_PROGRESS
    COMPLETED = REQUEST_STATUS_COMPLETED
    CANCELLED = REQUEST_STATUS_CANCELLED

class UserRole(enum.Enum):
    CUSTOMER = ROLE_CUSTOMER
    INSTALLER = ROLE_INSTALLER

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer_requests = relationship("Request", foreign_keys="Request.customer_id", back_populates="customer")
    installer_requests = relationship("Request", foreign_keys="Request.installer_id", back_populates="installer")
    refusals = relationship("Refusal", back_populates="installer")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, role={self.role})>"

class District(Base):
    __tablename__ = 'districts'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    requests = relationship("Request", back_populates="district")
    
    def __repr__(self):
        return f"<District(id={self.id}, name={self.name})>"

class Request(Base):
    __tablename__ = 'requests'
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    installer_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    district_id = Column(Integer, ForeignKey('districts.id'), nullable=False)
    
    description = Column(Text, nullable=False)
    photos = Column(Text, nullable=True)  # JSON строка с file_id фото
    address = Column(String(500), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    phone = Column(String(20), nullable=False)
    
    status = Column(Enum(RequestStatus), default=RequestStatus.NEW, nullable=False)
    taken_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    customer = relationship("User", foreign_keys=[customer_id], back_populates="customer_requests")
    installer = relationship("User", foreign_keys=[installer_id], back_populates="installer_requests")
    district = relationship("District", back_populates="requests")
    group_messages = relationship("GroupMessage", back_populates="request")
    refusals = relationship("Refusal", back_populates="request")
    
    # Indexes
    __table_args__ = (
        Index('idx_requests_status', 'status'),
        Index('idx_requests_customer', 'customer_id'),
        Index('idx_requests_installer', 'installer_id'),
        Index('idx_requests_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Request(id={self.id}, status={self.status}, customer_id={self.customer_id})>"

class GroupMessage(Base):
    __tablename__ = 'group_messages'
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey('requests.id'), nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    request = relationship("Request", back_populates="group_messages")
    
    __table_args__ = (
        Index('idx_group_messages_request', 'request_id'),
    )
    
    def __repr__(self):
        return f"<GroupMessage(request_id={self.request_id}, message_id={self.message_id})>"

class Refusal(Base):
    __tablename__ = 'refusals'
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey('requests.id'), nullable=False)
    installer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    request = relationship("Request", back_populates="refusals")
    installer = relationship("User", foreign_keys=[installer_id], back_populates="refusals")
    
    def __repr__(self):
        return f"<Refusal(request_id={self.request_id}, installer_id={self.installer_id})>"

class GeocodeCache(Base):
    __tablename__ = 'geocode_cache'
    
    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        Index('idx_geocode_coords', 'latitude', 'longitude', unique=True),
    )
    
    def __repr__(self):
        return f"<GeocodeCache(lat={self.latitude}, lon={self.longitude})>"