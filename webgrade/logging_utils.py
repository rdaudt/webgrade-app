from __future__ import annotations

import logging
from pathlib import Path


class ContextDefaultsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for attr in ("batch_id", "run_id", "site_slug", "stage"):
            if not hasattr(record, attr):
                setattr(record, attr, "-")
        return True


def configure_logging(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("webgrade")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.filters.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s batch=%(batch_id)s run=%(run_id)s site=%(site_slug)s stage=%(stage)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    logger.addFilter(ContextDefaultsFilter())

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def close_logging(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)
    logger.filters.clear()


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    batch_id: int | str = "-",
    run_id: int | str = "-",
    site_slug: str = "-",
    stage: str = "-",
) -> None:
    logger.log(
        level,
        message,
        extra={
            "batch_id": batch_id,
            "run_id": run_id,
            "site_slug": site_slug,
            "stage": stage,
        },
    )
