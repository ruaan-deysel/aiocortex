# aiocortex

Async Python library for Home Assistant configuration management. Provides git versioning (via dulwich), file management, YAML editing, Pydantic models, and AI instruction documents — all independent of Home Assistant internals.

This library is the core engine behind the [Cortex](https://github.com/ruaan-deysel/cortex) HACS integration.

## Installation

```bash
pip install aiocortex
```

## Features

- **Git versioning** — Shadow git repository for HA config backups using [dulwich](https://www.dulwich.io/) (pure Python, no git binary required)
- **File management** — Async file operations with path security (directory traversal prevention)
- **YAML editing** — Safe YAML read/write/parse utilities
- **Pydantic models** — Typed data models for automations, scripts, helpers, files, git commits
- **AI instructions** — Markdown guidance documents for AI assistants interacting with Home Assistant

## Quick Start

```python
from aiocortex import AsyncFileManager, GitManager, YAMLEditor

# File operations
file_mgr = AsyncFileManager(config_path=Path("/config"))
files = await file_mgr.list_files("", "*.yaml")
content = await file_mgr.read_file("automations.yaml")

# Git versioning
git_mgr = GitManager(config_path=Path("/config"), max_backups=30)
await git_mgr.init_repo()
await git_mgr.commit_changes("Add automation: motion sensor light")
history = await git_mgr.get_history(limit=10)

# YAML editing
editor = YAMLEditor()
result = editor.remove_yaml_entry(content, "- id: 'old_automation'")

# AI instructions
from aiocortex import load_all_instructions
docs = load_all_instructions(version="1.0.0")
```

## Architecture

```
aiocortex/
├── git/           # GitManager, sync, filters, cleanup (dulwich-based)
├── files/         # AsyncFileManager, YAMLEditor
├── models/        # Pydantic v2 models (common, config, files, git)
├── instructions/  # AI instruction markdown documents
└── exceptions.py  # CortexError hierarchy
```

### Design Principle

If it imports `homeassistant.*`, it does **not** belong here. This library contains only HA-independent logic. The Cortex integration handles all HA-specific concerns (states, services, registries, auth, HTTP routing).

## Models

```python
from aiocortex.models import (
    AutomationConfig,   # Automation definition
    ScriptConfig,       # Script definition
    HelperSpec,         # Input helper specification
    ServiceCallSpec,    # Service call parameters
    FileInfo,           # File metadata
    FileWriteResult,    # Write operation result
    CommitInfo,         # Git commit metadata
    PendingChanges,     # Uncommitted changes
    CortexResponse,     # Standard API response
)
```

## Dependencies

- `pydantic>=2.0` — Data validation and models
- `pyyaml>=6.0` — YAML parsing
- `aiofiles>=23.0` — Async file I/O
- `dulwich>=0.22.0` — Pure Python git implementation

## Development

```bash
git clone https://github.com/ruaan-deysel/aiocortex.git
cd aiocortex
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest --cov=aiocortex
```

## License

MIT
