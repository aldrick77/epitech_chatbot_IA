import logging
import os
import sys


LEVEL_COLORS = {
    "DEBUG": "\x1b[36m",
    "INFO": "\x1b[32m",
    "WARNING": "\x1b[33m",
    "ERROR": "\x1b[31m",
    "CRITICAL": "\x1b[41m",
}
RESET = "\x1b[0m"


def _supports_color() -> bool:
    return sys.stderr.isatty() and os.getenv("EPITECH_LOG_COLOR", "1") != "0"


class PrettyFormatter(logging.Formatter):
    def __init__(self, use_color: bool) -> None:
        super().__init__(datefmt="%H:%M:%S")
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        record_message = record.getMessage()
        record_time = self.formatTime(record, self.datefmt)
        level = record.levelname
        name = record.name

        if self.use_color:
            level_color = LEVEL_COLORS.get(level, "")
            level_label = f"{level_color}{level:<7}{RESET}"
            name_label = f"\x1b[2m{name}{RESET}"
        else:
            level_label = f"{level:<7}"
            name_label = name

        line = f"{record_time} | {level_label} | {name_label} | {record_message}"
        if record.exc_info:
            line = line + "\n" + self.formatException(record.exc_info)
        return line


def setup_logging() -> None:
    level_name = os.getenv("EPITECH_LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(level_name)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(PrettyFormatter(use_color=_supports_color()))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]
    logging.captureWarnings(True)
