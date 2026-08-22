"""Models module initialization."""

from .router import (
    ModelRouter,
    ModelAlias,
    ModelSelectionResult,
    RoutingStrategy,
    get_model_router,
)

__all__ = [
    "ModelRouter",
    "ModelAlias",
    "ModelSelectionResult",
    "RoutingStrategy",
    "get_model_router",
]
