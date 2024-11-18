import models
from database import SessionLocal


def is_message_related_to_exchanges(message: str) -> bool:
    db = SessionLocal()
    try:
        db_exchanges = db.query(models.Exchange).all()
        exchange_names = [exchange.name.lower() for exchange in db_exchanges]
        return any(exchange in message.lower() for exchange in exchange_names)
    finally:
        db.close()
