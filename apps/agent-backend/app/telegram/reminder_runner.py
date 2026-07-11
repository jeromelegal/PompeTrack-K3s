from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.reminders import send_due_reminders

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    result = send_due_reminders()
    logger.info("reminder runner completed", extra=result)


if __name__ == "__main__":
    main()
