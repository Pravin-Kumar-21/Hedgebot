import logging
import os

def get_logger(name="hedgebot" , log_file="logs/hedgebot.log"):
    """Initialize and return a logger with specified name and log file."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    
    os.makedirs("logs", exist_ok=True)
    log_file = os.path.join("logs", f"{name}.log")

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console Handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
    ch.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(ch)

    return logger
