"""Utility functions — logging and config loading."""

import logging
import yaml
from pathlib import Path
import coloredlogs


def load_config(config_path: str) -> dict:
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)


def setup_logging(log_level=logging.INFO) -> logging.Logger:
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger()
    logger.setLevel(log_level)

    file_handler = logging.FileHandler('logs/gmail_reminders.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)

    coloredlogs.install(
        level=log_level,
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        logger=logger,
    )

    return logger
