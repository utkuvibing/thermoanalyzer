"""Online reference-library providers for live API matching."""

from core.online_providers.base import OnlineProvider, OnlineSearchResult
from core.online_providers.registry import (
    get_online_engine,
    online_search_enabled,
    register_provider,
)

__all__ = [
    "OnlineProvider",
    "OnlineSearchResult",
    "get_online_engine",
    "online_search_enabled",
    "register_provider",
]
