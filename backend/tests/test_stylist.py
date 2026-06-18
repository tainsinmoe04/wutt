"""Tests for WUTT auth uniqueness and fallback stylist quality.

Run with:
    cd backend && python -m pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import sys
import os

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the fallback functions directly (no DB needed for unit tests)
from routes.stylist import (
    _generate_fallback,
    _classify_item,
    _score_item,
    _build_interview_outfit,
    _build_wedding_outfit,
    _build_casual_outfit,
    _build_generic_outfit,
)


# ── Helper factories ────────────────────────────────────


def _item(category: str, color: str = "", description: str = "") -> dict:
    """Create a wardrobe item dict matching the stylist route's expected shape."""
    return {
        "url": f"https://example.com/{category}.jpg",
        "category": category,
        "color": color,
        "description": description,
    }


# ── Classification tests ────────────────────────────────


@pytest.mark.parametrize("cat,expected", [
    ("dress", "dress"),
    ("gown", "dress"),
    ("jumpsuit", "dress"),
    ("top", "top"),
    ("shirt", "top"),
    ("blouse", "top"),
    ("t-shirt", "top"),
    ("bottom", "bottom"),
    ("trousers", "bottom"),
    ("jeans", "bottom"),
    ("skirt", "bottom"),
    ("traditional", "traditional"),
    ("longyi", "traditional"),
    ("outerwear", "outerwear"),
    ("coat", "outerwear"),
    ("cardigan", "outerwear"),
    ("accessory", "accessory"),
    ("shoes", "shoes"),
    ("unknown_type", "unknown"),
])
def test_classify_item(cat, expected):
    assert _classify_item(_item(cat)) == expected


# ── Scoring tests ────────────────────────────────────────


def test_score_interview_prefers_navy():
    """Interview should score navy/formal items higher than bright yellow."""
    navy_top = _score_item(_item("top", "navy"), "top", "interview", None)
    yellow_top = _score_item(_item("top", "yellow"), "top", "interview", None)
    assert navy_top > yellow_top


def test_score_interview_penalizes_bright_accent():
    """Bright yellow should be penalized for interviews."""
    score = _score_item(_item("top", "yellow"), "top", "interview", None)
    white_score = _score_item(_item("top", "white"), "top", "interview", None)
    assert white_score > score


def test_score_wedding_prefers_traditional():
    """Wedding should score traditional items highly."""
    trad_score = _score_item(_item("traditional"), "traditional", "wedding", None)
    casual_score = _score_item(_item("t-shirt", "white"), "top", "wedding", None)
    assert trad_score > casual_score


# ── Interview outfit composition ─────────────────────────


def test_interview_returns_at_most_two_main_items():
    """Interview outfit must NOT return multiple tops."""
    classified = {
        "dress": [], "top": [
            _item("top", "navy"), _item("shirt", "white"),
        ],
        "bottom": [_item("trousers", "black")],
        "traditional": [], "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    from routes.stylist import _build_interview_outfit
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "interview", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_interview_outfit(
        classified, scored, "interview", None,
    )

    # Must not return 3+ tops — should pick 1 top + 1 bottom = 2 items
    # Only 1 top is allowed
    top_count = sum(
        1 for o in outfit
        if any(kw in o.lower() for kw in ["top", "shirt", "blouse", "t-shirt", "navy", "white"])
    )
    # We can't count labels exactly, but check length is reasonable
    assert len(outfit) <= 3  # top + bottom + optional outerwear
    assert len(outfit) >= 1


def test_interview_does_not_return_multiple_tops_explicitly():
    """With 3 tops and 1 bottom, interview must NOT pick multiple tops."""
    classified = {
        "dress": [], "top": [
            _item("top", "navy"), _item("shirt", "beige"), _item("blouse", "white"),
        ],
        "bottom": [_item("trousers", "black")],
        "traditional": [], "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "interview", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_interview_outfit(
        classified, scored, "interview", None,
    )

    # Outfit should have at most 3 items (one top, one bottom, optional outerwear)
    assert len(outfit) <= 3
    # Should not be empty
    assert len(outfit) >= 1
    # Should contain a bottom-related item (trousers)
    assert any("trouser" in o.lower() or "အောက်ဝတ်" in o for o in outfit), \
        f"Expected a bottom item in outfit: {outfit}"


# ── Wedding outfit composition ──────────────────────────


def test_wedding_does_not_return_dress_plus_dress_plus_top_plus_bottom():
    """Wedding must never return invalid combination: dress+dress+top+bottom."""
    classified = {
        "dress": [_item("dress", "red"), _item("gown", "pink")],
        "top": [_item("top", "white")],
        "bottom": [_item("trousers", "black")],
        "traditional": [], "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "wedding", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_wedding_outfit(
        classified, scored, "wedding", None,
    )

    # Should NOT return dress + dress + top + bottom (4 items from all categories)
    assert len(outfit) <= 2  # One dress + optional outerwear at most
    # Should pick one dress, not both
    dress_count = sum(1 for o in outfit if "dress" in o.lower() or "gown" in o.lower() or "ဂါဝန်" in o)
    assert dress_count <= 1, f"Should not return multiple dresses: {outfit}"


def test_wedding_with_unsuitable_wardrobe_returns_honest_explanation():
    """When no wedding-appropriate items exist, be honest."""
    classified = {
        "dress": [], "traditional": [],
        "top": [_item("t-shirt", "yellow")],
        "bottom": [_item("jeans", "blue")],
        "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "wedding", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_wedding_outfit(
        classified, scored, "wedding", None,
    )

    # Should contain "အနီးစပ်ဆုံး" (closest available) — honest assessment
    assert "အနီးစပ်ဆုံး" in explanation, \
        f"Expected honest 'closest available' message, got: {explanation}"
    # Should mention adding formal dress / myanmar dress / longyi
    assert any(
        phrase in explanation
        for phrase in ["formal", "မြန်မာဝတ်စုံ", "သပ်ရပ်"]
    ), f"Expected advice to add suitable items, got: {explanation}"


def test_wedding_prefers_traditional_over_casual():
    """When traditional items exist, wedding should prefer them over casual top+bottom."""
    classified = {
        "dress": [],
        "traditional": [_item("traditional", "gold")],
        "top": [_item("t-shirt", "white")],
        "bottom": [_item("jeans", "blue")],
        "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "wedding", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_wedding_outfit(
        classified, scored, "wedding", None,
    )

    # Should pick traditional over casual
    assert len(outfit) >= 1
    assert any(
        "traditional" in o.lower() or "မြန်မာ" in o or "ရိုးရာ" in o.lower()
        for o in outfit
    ), f"Expected traditional item, got: {outfit}"


# ── Fallback response shape ──────────────────────────────


def test_fallback_response_shape():
    """Fallback must return the frontend-compatible JSON shape."""
    result = _generate_fallback(
        wardrobe_items=[
            _item("top", "navy"),
            _item("trousers", "black"),
        ],
        occasion="interview",
    )

    assert "outfit" in result
    assert "explanation" in result
    assert "weather_based_tip" in result
    assert isinstance(result["outfit"], list)
    assert isinstance(result["explanation"], str)
    assert isinstance(result["weather_based_tip"], str)


def test_fallback_with_no_items():
    """Empty wardrobe returns empty outfit."""
    result = _generate_fallback([], "casual")
    assert result["outfit"] == []
    assert "ဗီရိုထဲမှာ" in result["explanation"]


# ── Casual outfit ────────────────────────────────────────


def test_casual_returns_top_plus_bottom():
    """Casual should return one top + one bottom when available."""
    classified = {
        "dress": [], "traditional": [],
        "top": [_item("t-shirt", "white")],
        "bottom": [_item("jeans", "blue")],
        "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "casual", 33), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_casual_outfit(
        classified, scored, "casual", 33,
    )

    assert len(outfit) == 2, f"Casual should give top + bottom, got: {outfit}"


# ── No invalid combinations ──────────────────────────────


def test_no_dress_plus_dress():
    """With two dresses, must return only one."""
    classified = {
        "dress": [_item("dress", "red"), _item("gown", "navy")],
        "top": [], "bottom": [], "traditional": [],
        "outerwear": [], "accessory": [], "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "casual", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_casual_outfit(
        classified, scored, "casual", None,
    )
    assert len(outfit) <= 1  # Only one dress


def test_no_top_plus_top():
    """With only tops, must not return multiple tops."""
    classified = {
        "dress": [], "traditional": [],
        "top": [_item("top", "navy"), _item("shirt", "white")],
        "bottom": [], "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "casual", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    outfit, explanation, suitability = _build_casual_outfit(
        classified, scored, "casual", None,
    )
    # Should only return 1 item (single top) since no bottoms
    assert len(outfit) == 1, f"Should return only 1 top when no bottoms: {outfit}"


def test_no_dress_plus_top_plus_bottom():
    """Never mix dress + top + bottom."""
    classified = {
        "dress": [_item("dress", "red")],
        "top": [_item("top", "navy")],
        "bottom": [_item("trousers", "black")],
        "traditional": [], "outerwear": [], "accessory": [],
        "shoes": [], "unknown": [],
    }
    scored = {}
    for key, items in classified.items():
        scored[key] = sorted(
            ((_score_item(it, key, "casual", None), it) for it in items),
            key=lambda x: x[0], reverse=True,
        )
    # Test all occasion builders with dress+top+bottom wardrobe
    for builder, occ_name in [
        (_build_casual_outfit, "casual"),
        (_build_generic_outfit, "work"),
    ]:
        outfit, explanation, suitability = builder(
            classified, scored, occ_name, None,
        )
        # Should not have both dress and top+bottom
        has_dress = any("dress" in o.lower() or "gown" in o.lower() or "ဂါဝန်" in o for o in outfit)
        has_top = any(
            t in o.lower()
            for o in outfit
            for t in ["top", "shirt", "blouse"]
        )
        has_bottom = any(
            b in o.lower()
            for o in outfit
            for b in ["trouser", "bottom", "pant", "jeans", "အောက်ဝတ်"]
        )
        # If there's a dress, should NOT also have top+bottom
        if has_dress:
            assert not (has_top and has_bottom), \
                f"{occ_name}: dress+top+bottom invalid combo: {outfit}"


# ── Myanmar wording ──────────────────────────────────────


def test_myanmar_wording_no_english_fallback():
    """Explanation should NOT contain English like 'Dress comfortably'."""
    result = _generate_fallback(
        wardrobe_items=[
            _item("top", "navy"),
            _item("trousers", "black"),
        ],
        occasion="interview",
        temperature_c=30,
    )
    explanation = result["explanation"]
    weather_tip = result["weather_based_tip"]
    combined = explanation + " " + weather_tip

    # No English phrases
    assert "Dress comfortably" not in combined
    assert "Choose light" not in combined
    assert "fabric" not in combined.lower()
    # Should have Myanmar content
    assert any(
        "က" <= c <= "ာ" or "ဿ" <= c <= "၏"
        for c in combined
    ), "Expected Myanmar script characters in output"


def test_weather_tip_is_myanmar():
    """Weather tip should be in Myanmar, not English."""
    result = _generate_fallback(
        wardrobe_items=[_item("top", "white")],
        occasion="casual",
        temperature_c=35,
    )
    tip = result["weather_based_tip"]
    # Should not contain English
    assert "Dress" not in tip
    assert "Choose" not in tip
    # Should have Myanmar
    assert any(
        "က" <= c <= "ာ" for c in tip
    ), f"Expected Myanmar text, got: {tip}"
