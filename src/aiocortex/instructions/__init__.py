"""AI instruction document loader."""

from __future__ import annotations

from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"


def load_instruction_file(filename: str) -> str:
    """Load a single instruction markdown file."""
    file_path = DOCS_DIR / filename
    if file_path.exists():
        return file_path.read_text(encoding="utf-8")
    return f"<!-- {filename} not found -->\n"


def load_all_instructions(version: str = "1.0.0") -> str:
    """Load and combine all instruction markdown files into one document.

    The files are loaded in sorted order; a ``{VERSION}`` placeholder in
    ``00_overview.md`` is replaced with *version*.
    """
    instruction_files = [
        "00_overview.md",
        "01_explain_before_executing.md",
        "02_output_formatting.md",
        "03_critical_safety.md",
        "04_dashboard_generation.md",
        "06_conditional_cards.md",
        "05_api_summary.md",
        "99_final_reminder.md",
    ]

    instructions: list[str] = []

    for filename in instruction_files:
        content = load_instruction_file(filename)
        if filename == "00_overview.md":
            content = content.replace("{VERSION}", version)
        instructions.append(content)

    return "\n\n---\n\n".join(instructions)


def get_instruction_files() -> list[str]:
    """Return sorted list of available instruction file names."""
    if not DOCS_DIR.exists():
        return []
    return sorted(f.name for f in DOCS_DIR.glob("*.md"))
