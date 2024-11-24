import models
from sqlalchemy.orm import Session


def is_message_related_to_exchanges(db: Session, message: str) -> bool:
    db_exchanges = db.query(models.Exchange).all()
    exchange_names = [exchange.name.lower() for exchange in db_exchanges]
    return any(exchange in message.lower() for exchange in exchange_names)
