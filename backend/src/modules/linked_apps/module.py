"""LinkedAppsModule — constructor-injection factory satisfying HasAPIRoutes
(D-08). No requires/provides — linked_apps has zero dependency on any other
module's capability (D-23).
"""

from fastapi import APIRouter

from src.modules.linked_apps import routes


class LinkedAppsModule:
    def get_router(self) -> APIRouter:
        return routes.router


def create(deps: dict[type, object]) -> LinkedAppsModule:
    """Constructor-injection factory (D-08) — linked_apps requires nothing,
    so `deps` is always empty for this module."""
    return LinkedAppsModule()
