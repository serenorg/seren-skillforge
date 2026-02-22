from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_GATEWAY_URL = "https://api.serendb.com"
_RPC_GUESS_PATTERN = re.compile(r"^rpc-([a-z0-9-]+)$")
_TOKEN_SPLIT_PATTERN = re.compile(r"[^a-z0-9]+")
_CHAIN_HINTS: dict[str, tuple[str, ...]] = {
    "ethereum": ("ethereum",),
    "arbitrum": ("arbitrum",),
    "base": ("base",),
    "optimism": ("optimism",),
    "polygon": ("polygon", "matic"),
    "avalanche": ("avalanche", "avax"),
    "bsc": ("bsc", "bnb", "binance"),
    "gnosis": ("gnosis", "xdai"),
    "zksync": ("zksync",),
    "scroll": ("scroll",),
}


class PublisherCatalogError(Exception):
    """Raised when publisher catalog discovery fails."""


@dataclass(frozen=True)
class PublisherRecord:
    slug: str
    name: str
    description: str
    categories: tuple[str, ...]
    is_active: bool

    def to_search_text(self) -> str:
        return " ".join((self.slug, self.name, self.description, " ".join(self.categories)))


@dataclass(frozen=True)
class SlugResolution:
    requested: str
    resolved: str | None
    source: str
    reason: str
    suggestions: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.resolved is not None


def normalize_gateway_url(url: str) -> str:
    normalized = url.rstrip("/")
    for suffix in ("/v1/publishers", "/publishers"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized.rstrip("/")


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_SPLIT_PATTERN.split(text.lower()) if token}


def _request_json(
    *,
    gateway_url: str,
    path: str,
    api_key: str | None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    normalized_path = path if path.startswith("/") else f"/{path}"
    request = Request(
        url=f"{normalize_gateway_url(gateway_url)}{normalized_path}",
        method="GET",
        headers={
            "Accept": "application/json",
            **(
                {"Authorization": f"Bearer {api_key.strip()}"}
                if api_key and api_key.strip()
                else {}
            ),
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise PublisherCatalogError(
            f"Publisher catalog request failed HTTP {exc.code} on {normalized_path}: {details}"
        ) from exc
    except URLError as exc:
        raise PublisherCatalogError(
            f"Publisher catalog request failed on {normalized_path}: {exc}"
        ) from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PublisherCatalogError(
            f"Publisher catalog returned invalid JSON on {normalized_path}: {raw[:200]}"
        ) from exc

    if not isinstance(parsed, dict):
        raise PublisherCatalogError(
            f"Publisher catalog returned non-object response on {normalized_path}."
        )
    return parsed


def list_publishers(
    *,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    api_key: str | None = None,
    limit: int = 100,
    max_pages: int = 5,
) -> list[PublisherRecord]:
    if limit < 1 or limit > 100:
        raise PublisherCatalogError("Publisher catalog limit must be between 1 and 100.")

    publishers: list[PublisherRecord] = []
    offset = 0
    for _ in range(max_pages):
        query = urlencode({"limit": limit, "offset": offset})
        payload = _request_json(
            gateway_url=gateway_url,
            path=f"/publishers?{query}",
            api_key=api_key,
        )
        data = payload.get("data")
        if not isinstance(data, list):
            raise PublisherCatalogError(
                "Publisher catalog response is missing a list-valued 'data' field."
            )

        page_items: list[PublisherRecord] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug", "")).strip()
            if not slug:
                continue
            name = str(item.get("name", "")).strip()
            description = str(item.get("description", "")).strip()
            categories_raw = item.get("categories", [])
            categories = tuple(
                str(category)
                for category in categories_raw
                if isinstance(category, str) and category.strip()
            )
            is_active_raw = item.get("is_active", True)
            is_active = bool(is_active_raw)
            page_items.append(
                PublisherRecord(
                    slug=slug,
                    name=name,
                    description=description,
                    categories=categories,
                    is_active=is_active,
                )
            )
        publishers.extend(page_items)

        pagination = payload.get("pagination", {})
        has_more = bool(pagination.get("has_more")) if isinstance(pagination, dict) else False
        if not has_more or not page_items:
            break
        page_count = pagination.get("count") if isinstance(pagination, dict) else None
        if isinstance(page_count, int) and page_count > 0:
            offset += page_count
        else:
            offset += len(page_items)

    return publishers


def publisher_index(
    *,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    api_key: str | None = None,
    include_inactive: bool = True,
) -> dict[str, PublisherRecord]:
    records = list_publishers(gateway_url=gateway_url, api_key=api_key)
    index: dict[str, PublisherRecord] = {}
    for record in records:
        if not include_inactive and not record.is_active:
            continue
        index[record.slug] = record
    return index


def _is_rpc_like(record: PublisherRecord) -> bool:
    categories_tokens = _tokenize(" ".join(record.categories))
    slug_tokens = _tokenize(record.slug)
    name_tokens = _tokenize(record.name)
    if "rpc" in categories_tokens or "rpc" in slug_tokens or "rpc" in name_tokens:
        return True
    description = record.description.lower()
    return "json-rpc" in description or "json rpc" in description


def _rpc_guess_resolution(
    requested_slug: str,
    index: dict[str, PublisherRecord],
) -> SlugResolution | None:
    matched = _RPC_GUESS_PATTERN.fullmatch(requested_slug.lower())
    if not matched:
        return None

    chain_hint = matched.group(1)
    terms = _CHAIN_HINTS.get(chain_hint, (chain_hint,))
    candidates: list[tuple[int, PublisherRecord]] = []
    for record in index.values():
        if not record.is_active or not _is_rpc_like(record):
            continue
        tokens = _tokenize(record.to_search_text())
        if not any(term in tokens for term in terms):
            continue
        score = 0
        if record.slug.startswith("seren-"):
            score += 20
        if any(term in _tokenize(record.slug) for term in terms):
            score += 12
        if any(term in _tokenize(" ".join(record.categories)) for term in terms):
            score += 8
        if any(term in _tokenize(record.name) for term in terms):
            score += 6
        if "json-rpc" in record.description.lower():
            score += 4
        candidates.append((score, record))

    if not candidates:
        return SlugResolution(
            requested=requested_slug,
            resolved=None,
            source="rpc_guess",
            reason=f"No RPC publisher found for guessed slug '{requested_slug}'.",
        )

    candidates.sort(key=lambda pair: (-pair[0], pair[1].slug))
    best_score, best_record = candidates[0]
    top = [record for score, record in candidates if score == best_score]
    if len(top) > 1:
        suggestions = tuple(record.slug for record in top[:5])
        return SlugResolution(
            requested=requested_slug,
            resolved=None,
            source="rpc_guess",
            reason=f"Ambiguous RPC slug '{requested_slug}'.",
            suggestions=suggestions,
        )
    return SlugResolution(
        requested=requested_slug,
        resolved=best_record.slug,
        source="rpc_guess",
        reason=f"Resolved guessed RPC slug '{requested_slug}' to '{best_record.slug}'.",
    )


def resolve_publisher_slug(
    *,
    requested_slug: str,
    index: dict[str, PublisherRecord],
) -> SlugResolution:
    slug = requested_slug.strip()
    if not slug:
        return SlugResolution(
            requested=requested_slug,
            resolved=None,
            source="empty",
            reason="Publisher slug is empty.",
        )

    if slug in index:
        return SlugResolution(
            requested=requested_slug,
            resolved=slug,
            source="exact",
            reason="Publisher slug matched catalog exactly.",
        )

    lower_lookup: dict[str, str] = {}
    for catalog_slug in index:
        lower_lookup[catalog_slug.lower()] = catalog_slug

    lowered = slug.lower()
    if lowered in lower_lookup:
        canonical = lower_lookup[lowered]
        return SlugResolution(
            requested=requested_slug,
            resolved=canonical,
            source="case_insensitive",
            reason=f"Normalized slug casing from '{requested_slug}' to '{canonical}'.",
        )

    rpc_resolution = _rpc_guess_resolution(slug, index)
    if rpc_resolution is not None:
        return rpc_resolution

    similar = [
        record.slug
        for record in index.values()
        if lowered in record.slug.lower() or record.slug.lower() in lowered
    ]
    suggestions = tuple(sorted(similar)[:5])
    return SlugResolution(
        requested=requested_slug,
        resolved=None,
        source="not_found",
        reason=f"Publisher slug '{requested_slug}' was not found in gateway catalog.",
        suggestions=suggestions,
    )
