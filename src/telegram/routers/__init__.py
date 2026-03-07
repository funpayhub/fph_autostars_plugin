from __future__ import annotations

from .commands import router as commands_router
from .queries import router as queries_router


ROUTERS = [commands_router, queries_router]
