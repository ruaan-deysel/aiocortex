"""aio-cortex — Async Python library for Home Assistant configuration management."""

from ._version import __version__
from .exceptions import (
    CortexError,
    FileError,
    GitError,
    GitNotInitializedError,
    PathSecurityError,
    YAMLParseError,
)
from .files import AsyncFileManager, YAMLEditor
from .instructions import get_instruction_files, load_all_instructions
from .models import (
    AutomationConfig,
    CommitInfo,
    CortexResponse,
    FileInfo,
    FileWriteResult,
    HelperSpec,
    PendingChanges,
    PendingChangesSummary,
    ScriptConfig,
    ServiceCallSpec,
)

__all__ = [
    "__version__",
    # Exceptions
    "CortexError",
    "FileError",
    "GitError",
    "GitNotInitializedError",
    "PathSecurityError",
    "YAMLParseError",
    # Files
    "AsyncFileManager",
    "YAMLEditor",
    # Instructions
    "get_instruction_files",
    "load_all_instructions",
    # Models
    "AutomationConfig",
    "CommitInfo",
    "CortexResponse",
    "FileInfo",
    "FileWriteResult",
    "HelperSpec",
    "PendingChanges",
    "PendingChangesSummary",
    "ScriptConfig",
    "ServiceCallSpec",
]
