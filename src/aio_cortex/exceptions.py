"""Exception hierarchy for aio-cortex."""


class CortexError(Exception):
    """Base exception for all aio-cortex errors."""


class GitError(CortexError):
    """Error during a git operation."""


class GitNotInitializedError(GitError):
    """The shadow git repository has not been initialized."""


class FileError(CortexError):
    """Error during a file operation."""


class PathSecurityError(FileError):
    """A requested path resolved outside the allowed config directory."""


class YAMLParseError(FileError):
    """Failed to parse a YAML file."""
