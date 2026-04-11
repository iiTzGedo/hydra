"""Shared icon descriptor models."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IconDescriptor(BaseModel):
    """Resolved icon metadata shared across Hydra entities."""

    model_config = ConfigDict(populate_by_name=True)

    source: Literal["hydra", "selfh-st", "simple-icons", "fallback"]
    slug: str = Field(description="Normalized icon slug or key")
    label: str | None = Field(default=None, description="Human-friendly icon label")
    url: str | None = Field(default=None, description="Resolved icon asset URL")
    url_dark: str | None = Field(
        default=None,
        alias="urlDark",
        description="Dark-theme variant URL, when a theme-specific asset is available",
    )
    url_light: str | None = Field(
        default=None,
        alias="urlLight",
        description="Light-theme variant URL, when a theme-specific asset is available",
    )
    color: str | None = Field(default=None, description="Recommended accent or brand color")
    fallback: str | None = Field(default=None, description="Fallback icon key when the main icon cannot render")
