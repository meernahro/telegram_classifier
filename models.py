from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from database import Base


class Channel(Base):
    __tablename__ = "channels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


class Exchange(Base):
    __tablename__ = "exchanges"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)


class Token(Base):
    __tablename__ = "tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, index=True)
    exchange = Column(String, index=True)
    market = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
