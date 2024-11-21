import logging
import os
import sys

logger = None

def setup_logging():
    global logger
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/app.log")
        ],
    )
    
    logger = logging.getLogger("telegram_classifier")
    return logger
