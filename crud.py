from typing import List, Optional

from sqlalchemy.orm import Session

import models
import schemas


def create_or_update_channel(db: Session, channel: schemas.ChannelCreate):
    db_channel = (
        db.query(models.Channel).filter(models.Channel.name == channel.name).first()
    )
    if db_channel:
        return db_channel
    new_channel = models.Channel(name=channel.name)
    db.add(new_channel)
    db.commit()
    db.refresh(new_channel)
    return new_channel


def delete_channel(db: Session, channel_id: int):
    db_channel = (
        db.query(models.Channel).filter(models.Channel.id == channel_id).first()
    )
    if db_channel:
        db.delete(db_channel)
        db.commit()


def create_or_update_exchange(db: Session, exchange: schemas.ExchangeCreate):
    db_exchange = (
        db.query(models.Exchange).filter(models.Exchange.name == exchange.name).first()
    )
    if db_exchange:
        return db_exchange
    new_exchange = models.Exchange(name=exchange.name)
    db.add(new_exchange)
    db.commit()
    db.refresh(new_exchange)
    return new_exchange


def delete_exchange(db: Session, exchange_id: int):
    db_exchange = (
        db.query(models.Exchange).filter(models.Exchange.id == exchange_id).first()
    )
    if db_exchange:
        db.delete(db_exchange)
        db.commit()


def get_all_channels(db: Session) -> List[models.Channel]:
    """Get all channels from database"""
    return db.query(models.Channel).all()


def get_channel_by_id(db: Session, channel_id: int) -> Optional[models.Channel]:
    """Get specific channel by ID"""
    return db.query(models.Channel).filter(models.Channel.id == channel_id).first()


def get_all_exchanges(db: Session) -> List[models.Exchange]:
    """Get all exchanges from database"""
    return db.query(models.Exchange).all()


def get_exchange_by_id(db: Session, exchange_id: int) -> Optional[models.Exchange]:
    """Get specific exchange by ID"""
    return db.query(models.Exchange).filter(models.Exchange.id == exchange_id).first()


def create_token(db: Session, token: schemas.TokenCreate):
    """Create new token listing entry"""
    db_token = models.Token(
        token=token.token,
        exchange=token.exchange,
        market=token.market,
        timestamp=token.timestamp,
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_all_tokens(db: Session) -> List[models.Token]:
    """Get all tokens from database"""
    return db.query(models.Token).order_by(models.Token.timestamp.desc()).all()


def get_token_by_id(db: Session, token_id: int) -> Optional[models.Token]:
    """Get specific token by ID"""
    return db.query(models.Token).filter(models.Token.id == token_id).first()


def get_tokens_by_exchange(db: Session, exchange: str) -> List[models.Token]:
    """Get all tokens for a specific exchange"""
    return (
        db.query(models.Token)
        .filter(models.Token.exchange == exchange)
        .order_by(models.Token.timestamp.desc())
        .all()
    )


def get_latest_tokens(db: Session, limit: int = 10) -> List[models.Token]:
    """Get the most recent tokens"""
    return (
        db.query(models.Token)
        .order_by(models.Token.timestamp.desc())
        .limit(limit)
        .all()
    )
