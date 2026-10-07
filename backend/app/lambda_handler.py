"""AWS Lambda entry point: FastAPI app behind Lambda Function URL and migrations.

Two kinds of event arrive here:
- Direct invoke: {"action": "migrate"} to run Alembic migrations head.
- HTTP requests from Lambda Function URL (payload format 2.0), handled via Mangum.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from mangum import Mangum

from app.main import app

logger = logging.getLogger(__name__)

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"

# Mangum lifespan is set to "off" because app.main does not define any lifespan
# context manager or startup/shutdown event handlers. Setting lifespan="off"
# avoids cold-start latency and lifespan event overhead in AWS Lambda.
_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
_asgi = Mangum(app, lifespan="off")


def _migrate() -> dict[str, str]:
    from alembic import command
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.set_main_option(
        "script_location", str(ALEMBIC_INI.parent / "migrations")
    )
    command.upgrade(config, "head")
    logger.info("migrations applied")
    return {"status": "migrated"}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if isinstance(event, dict) and event.get("action") == "migrate":
        return _migrate()
    asyncio.set_event_loop(_loop)
    return _asgi(event, context)
