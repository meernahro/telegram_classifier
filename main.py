import asyncio
import logging
import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import SessionLocal, engine
from telegram_listener import TelegramListener
from logging_config import setup_logging

load_dotenv()

# Initialize FastAPI and create database tables
app = FastAPI(title="Telegram Token Tracker")
models.Base.metadata.create_all(bind=engine)

# Setup logging
logger = setup_logging()

# Store telegram_listener instance globally
telegram_listener = None


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
async def startup_event():
    """Start the Telegram listener when the FastAPI app starts"""
    global telegram_listener
    try:
        telegram_listener = TelegramListener()
        # Create a background task for the Telegram listener
        asyncio.create_task(telegram_listener.start())
        logging.info("Telegram listener started in background")
    except Exception as e:
        logging.error(f"Failed to start Telegram listener: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the Telegram listener when the FastAPI app stops"""
    global telegram_listener
    try:
        if telegram_listener:
            await telegram_listener.stop()
            logging.info("Telegram listener stopped")
    except Exception as e:
        logging.error(f"Failed to stop Telegram listener: {e}")


# Error handling middleware
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logging.error(f"Unhandled error: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy"}


# Endpoint to add or update a Telegram channel
@app.post("/config/channel/")
async def add_channel(channel: schemas.ChannelCreate, db: Session = Depends(get_db)):
    try:
        result = crud.create_or_update_channel(db, channel)
        if telegram_listener and telegram_listener.is_running:
            await telegram_listener.update_monitored_channels()
        return result
    except Exception as e:
        logging.error(f"Error adding channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add channel",
        )


# Endpoint to delete a Telegram channel
@app.delete("/config/channel/{channel_id}")
async def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    crud.delete_channel(db, channel_id)
    if telegram_listener and telegram_listener.is_running:
        await telegram_listener.update_monitored_channels()
    return {"message": "Channel deleted successfully."}


# Endpoint to add or update an exchange name
@app.post("/config/exchange/")
def add_exchange(exchange: schemas.ExchangeCreate, db: Session = Depends(get_db)):
    return crud.create_or_update_exchange(db, exchange)


# Endpoint to delete an exchange name
@app.delete("/config/exchange/{exchange_id}")
def delete_exchange(exchange_id: int, db: Session = Depends(get_db)):
    crud.delete_exchange(db, exchange_id)
    return {"message": "Exchange deleted successfully."}


# Read endpoints for Channels
@app.get("/config/channels/", response_model=List[schemas.ChannelResponse])
def get_all_channels(db: Session = Depends(get_db)):
    """Get all configured Telegram channels"""
    try:
        return crud.get_all_channels(db)
    except Exception as e:
        logging.error(f"Error fetching channels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch channels",
        )


@app.get("/config/channel/{channel_id}", response_model=schemas.ChannelResponse)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    """Get a specific channel by ID"""
    channel = crud.get_channel_by_id(db, channel_id)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found"
        )
    return channel


# Read endpoints for Exchanges
@app.get("/config/exchanges/", response_model=List[schemas.ExchangeResponse])
def get_all_exchanges(db: Session = Depends(get_db)):
    """Get all configured exchanges"""
    try:
        return crud.get_all_exchanges(db)
    except Exception as e:
        logging.error(f"Error fetching exchanges: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch exchanges",
        )


@app.get("/config/exchange/{exchange_id}", response_model=schemas.ExchangeResponse)
def get_exchange(exchange_id: int, db: Session = Depends(get_db)):
    """Get a specific exchange by ID"""
    exchange = crud.get_exchange_by_id(db, exchange_id)
    if not exchange:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exchange not found"
        )
    return exchange


@app.get("/tokens/", response_model=List[schemas.TokenResponse])
def get_tokens(
    exchange: Optional[str] = Query(None, description="Filter by exchange name"),
    limit: Optional[int] = Query(
        10, description="Limit the number of results", ge=1, le=100
    ),
    db: Session = Depends(get_db),
):
    """
    Get saved tokens with optional filtering
    - If exchange is provided, returns tokens for that exchange
    - If no exchange is provided, returns the most recent tokens
    - Limit parameter controls how many results to return
    """
    try:
        if exchange:
            tokens = crud.get_tokens_by_exchange(db, exchange)
            return tokens[:limit]  # Apply limit after filtering
        else:
            return crud.get_latest_tokens(db, limit)
    except Exception as e:
        logging.error(f"Error fetching tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch tokens",
        )


@app.get("/tokens/{token_id}", response_model=schemas.TokenResponse)
def get_token(token_id: int, db: Session = Depends(get_db)):
    """Get a specific token by ID"""
    token = crud.get_token_by_id(db, token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found"
        )
    return token


@app.get("/tokens/latest/", response_model=List[schemas.TokenResponse])
def get_latest_tokens(
    limit: int = Query(
        10, description="Number of latest tokens to return", ge=1, le=100
    ),
    db: Session = Depends(get_db),
):
    """Get the most recent tokens"""
    try:
        return crud.get_latest_tokens(db, limit)
    except Exception as e:
        logging.error(f"Error fetching latest tokens: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch latest tokens",
        )
