import os
import logging
import logging.handlers
from dotenv import load_dotenv

load_dotenv()

class CustomConsoleFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: '\x1b[40;1m',
        logging.INFO: '\x1b[34;1m',
        logging.WARNING: '\x1b[33;1m',
        logging.ERROR: '\x1b[31m',
        logging.CRITICAL: '\x1b[41m',
    }

    def format(self, record):
        levelno = record.levelno
        color = self.LEVEL_COLORS.get(levelno, '')
        formatter = logging.Formatter(
            f'\x1b[30;1m%(asctime)s\x1b[0m {color}%(levelname)-8s\x1b[0m \x1b[35m%(name)s\x1b[0m -> %(message)s',
            '%Y-%m-%d %H:%M:%S'
        )

        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f'\x1b[31m{text}\x1b[0m'

        output = formatter.format(record)
        record.exc_text = None
        return output

class CustomFileFormatter(logging.Formatter):
    FORMAT = logging.Formatter(
        '%(asctime)s %(levelname)-8s %(name)s -> %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )

def setup_logger(module_name: str, logging_enabled: str = None) -> logging.Logger:
    library, _, _ = module_name.partition('.py')
    logger = logging.getLogger(library)
    logger.setLevel(logging.INFO)

    log_level = "INFO"
    level = logging.getLevelName(log_level.upper())

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(CustomConsoleFormatter())
    logger.addHandler(console_handler)

    if logging_enabled == "True":
        grandparent_dir = os.path.abspath(f"{__file__}/../../")
        log_name = 'chatgpt_discord_bot.log'
        log_path = os.path.join(grandparent_dir, log_name)
        log_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            encoding='utf-8',
            mode='a',
            maxBytes=32 * 1024 * 1024,
            backupCount=2,
        )
        log_handler.setFormatter(CustomFileFormatter())
        log_handler.setLevel(level)
        logger.addHandler(log_handler)

    return logger

logger = setup_logger(__name__, os.getenv("LOGGING"))