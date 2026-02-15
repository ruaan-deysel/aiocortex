"""Configuration models for HA entities managed through the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AutomationConfig(BaseModel):
    """Automation definition."""

    id: str | None = None
    alias: str
    description: str | None = None
    trigger: list[dict[str, Any]]
    condition: list[dict[str, Any]] = []
    action: list[dict[str, Any]]
    mode: str = "single"


class ScriptConfig(BaseModel):
    """Script definition."""

    alias: str
    sequence: list[dict[str, Any]]
    mode: str = "single"
    icon: str | None = None
    description: str | None = None


class HelperSpec(BaseModel):
    """Input-helper specification (input_boolean, input_text, etc.)."""

    type: str
    config: dict[str, Any]


class ServiceCallSpec(BaseModel):
    """Home Assistant service-call parameters."""

    domain: str
    service: str
    data: dict[str, Any] = {}
    target: dict[str, Any] | None = None
