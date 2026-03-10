from __future__ import annotations

from .queries import router as queries_router
from .commands import router as commands_router


ROUTERS = [commands_router, queries_router]
