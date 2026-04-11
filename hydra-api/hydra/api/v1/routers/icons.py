"""Icon asset proxy endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import StringConstraints

from hydra.api.v1.core.deps import RedisDep
from hydra.api.v1.services.icons import (
    ICON_CACHE_TTL_SECONDS,
    IconAssetError,
    IconAssetInvalidError,
    IconAssetNotFoundError,
    get_icon_asset_svg,
)

router = APIRouter(tags=["Icons"])

IconSlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]*$")]
IconSource = Literal["selfh-st", "simple-icons"]


@router.get(
    "/icons/{source}/{slug}.svg",
    include_in_schema=False,
    summary="Serve proxied icon assets",
)
async def get_icon_asset(
    source: IconSource,
    slug: IconSlug,
    redis: RedisDep,
) -> Response:
    """Serve a cached icon asset from Hydra's allow-listed providers."""
    try:
        svg_text = await get_icon_asset_svg(source, slug, redis)
    except IconAssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IconAssetInvalidError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except IconAssetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(
        content=svg_text,
        media_type="image/svg+xml",
        headers={"Cache-Control": f"public, max-age={ICON_CACHE_TTL_SECONDS}"},
    )
