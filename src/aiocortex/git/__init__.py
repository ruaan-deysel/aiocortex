"""Git versioning with dulwich (no git binary required)."""

from .filters import should_include_path
from .manager import GitManager
from .sync import sync_config_to_shadow, sync_shadow_to_config

__all__ = [
    "GitManager",
    "should_include_path",
    "sync_config_to_shadow",
    "sync_shadow_to_config",
]
