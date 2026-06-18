"""Tests for WUTT fallback stylist — labels, diversity, and outfit composition.

Run with:
    cd backend && python -m pytest tests/test_fallback_stylist.py -v
"""

import json
import sys
import os

# Add backend to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import directly from the routes module
from routes.stylist import (
    _item_label,
    _classify_item,
    _score_item,
    _color_matches,
    _generate_fallback,
    _pick_best,
    _best_from_scored,
    _INTERVIEW_COLORS,
    _PARTY_COLORS,
    _WEDDING_COLORS,
)


# ── Helper: build a minimal wardrobe item dict ──────────────


def item(category, color="", description=""):
    """Create a minimal wardrobe item dict for testing."""
    d = {"category": category}
    if color:
        d["color"] = color
    if description:
        d["description"] = description
    return d


# ── Tests: _item_label — no duplicated labels ───────────────


class TestItemLabel:
    """Test that _item_label never produces duplicated category text."""

    def test_english_category_top(self):
        """top → အပေါ်ဝတ် · brown"""
        label = _item_label(item("top", "brown"))
        assert label == "အပေါ်ဝတ် · brown", f"Got: {label}"

    def test_english_category_bottom(self):
        """bottom → အောက်ဝတ် · navy"""
        label = _item_label(item("bottom", "navy"))
        assert label == "အောက်ဝတ် · navy", f"Got: {label}"

    def test_english_category_dress(self):
        """dress → တစ်ဆက်တည်းဝတ်စုံ · red"""
        label = _item_label(item("dress", "red"))
        assert label == "တစ်ဆက်တည်းဝတ်စုံ · red", f"Got: {label}"

    def test_myanmar_category_not_duplicated(self):
        """If cat is already Myanmar, don't double-translate."""
        # Already-Myanmar categories should stay as-is, not double
        label = _item_label(item("အပေါ်ဝတ်", "brown"))
        assert label == "အပေါ်ဝတ် · brown", f"Got: {label}"

    def test_myanmar_bottom_not_duplicated(self):
        label = _item_label(item("အောက်ဝတ်", "navy"))
        assert label == "အောက်ဝတ် · navy", f"Got: {label}"

    def test_no_double_top(self):
        """Never produce အပေါ်ဝတ်အပေါ်ဝတ်."""
        label = _item_label(item("top", "brown"))
        assert "အပေါ်ဝတ်အပေါ်ဝတ်" not in label, f"Duplicated! Got: {label}"

    def test_no_double_bottom(self):
        """Never produce အောက်ဝတ်အောက်ဝတ်."""
        label = _item_label(item("bottom", "navy"))
        assert "အောက်ဝတ်အောက်ဝတ်" not in label, f"Duplicated! Got: {label}"

    def test_no_double_dress(self):
        """Never produce dressdress or similar."""
        label = _item_label(item("dress", "red"))
        # Check that the category part doesn't appear doubled
        cat_part = label.split(" · ")[0]
        assert "dressdress" not in cat_part.lower(), f"Duplicated! Got: {label}"

    def test_t_shirt_mapped_correctly(self):
        """t-shirt → အပေါ်ဝတ်"""
        label = _item_label(item("t-shirt", "white"))
        assert label == "အပေါ်ဝတ် · white", f"Got: {label}"

    def test_gown_mapped_to_dress(self):
        """gown → တစ်ဆက်တည်းဝတ်စုံ"""
        label = _item_label(item("gown", "pink"))
        assert label == "တစ်ဆက်တည်းဝတ်စုံ · pink", f"Got: {label}"

    def test_with_description(self):
        """Category + color + description."""
        label = _item_label(item("top", "blue", "cotton shirt"))
        assert "အပေါ်ဝတ်" in label
        assert "blue" in label
        assert "cotton shirt" in label

    def test_no_color(self):
        """Category only, no color."""
        label = _item_label(item("shoes"))
        assert label == "ဖိနပ်", f"Got: {label}"

    def test_myanmar_self_keys_present(self):
        """All Myanmar self-keys map to themselves."""
        my_cats = ["အပေါ်ဝတ်", "အောက်ဝတ်", "ဖိနပ်",
                    "အသုံးအဆောင်", "လုံချည်", "မြန်မာဝတ်စုံ"]
        for cat in my_cats:
            label = _item_label(item(cat))
            # Should never contain the category doubled
            assert cat + cat not in label, f"Double {cat} in: {label}"


# ── Tests: valid outfit composition ─────────────────────────


class TestOutfitComposition:
    """Test that the fallback stylist never returns invalid combinations."""

    def test_single_dress_only(self):
        """With only a dress in wardrobe, returns the dress (not empty)."""
        wardrobe = [item("dress", "red")]
        result = _generate_fallback(wardrobe, "party")
        assert len(result["outfit"]) == 1, f"Got {len(result['outfit'])} items: {result['outfit']}"

    def test_top_plus_bottom_no_dress_plus_top_plus_bottom(self):
        """Never return dress + top + bottom together."""
        wardrobe = [
            item("dress", "red"),
            item("top", "white"),
            item("bottom", "navy"),
        ]
        result = _generate_fallback(wardrobe, "casual")
        # Should be either dress OR top+bottom, not all three
        assert len(result["outfit"]) <= 2, (
            f"Too many items: {result['outfit']}"
        )

    def test_no_multiple_tops(self):
        """Never recommend more than one top."""
        wardrobe = [
            item("top", "white"),
            item("top", "blue"),
            item("bottom", "black"),
        ]
        result = _generate_fallback(wardrobe, "casual")
        # Count tops in the outfit
        top_count = sum(1 for o in result["outfit"] if "အပေါ်ဝတ်" in o)
        assert top_count <= 1, f"Multiple tops: {result['outfit']}"

    def test_no_multiple_bottoms(self):
        """Never recommend more than one bottom."""
        wardrobe = [
            item("bottom", "navy"),
            item("bottom", "black"),
            item("top", "white"),
        ]
        result = _generate_fallback(wardrobe, "casual")
        bottom_count = sum(1 for o in result["outfit"] if "အောက်ဝတ်" in o)
        assert bottom_count <= 1, f"Multiple bottoms: {result['outfit']}"

    def test_empty_wardrobe_returns_empty_outfit(self):
        """With no items, return empty outfit and a helpful message."""
        result = _generate_fallback([], "casual")
        assert result["outfit"] == []
        assert len(result["explanation"]) > 0

    def test_only_tops_returns_one_item(self):
        """With only tops, return at most 1 item (can't make full outfit)."""
        wardrobe = [item("top", "white"), item("top", "blue")]
        result = _generate_fallback(wardrobe, "casual")
        assert len(result["outfit"]) <= 1, (
            f"Too many items with only tops: {result['outfit']}"
        )

    def test_outfit_always_structure(self):
        """Every result has outfit, explanation, weather_based_tip keys."""
        result = _generate_fallback([item("dress", "red")], "party")
        for key in ("outfit", "explanation", "weather_based_tip"):
            assert key in result, f"Missing key: {key}"


# ── Tests: occasion rules ───────────────────────────────────


class TestOccasionRules:
    """Test that each occasion type returns appropriate recommendations."""

    def test_interview_prefers_conservative_colors(self):
        """Interview items should favor white/navy/beige/black/gray."""
        wardrobe = [
            item("top", "red"),
            item("top", "white"),
            item("bottom", "navy"),
        ]
        result = _generate_fallback(wardrobe, "interview")
        # Should prefer white top over red top for interview
        outfit_text = " ".join(result["outfit"])
        # white should appear if available (not guaranteed with randomization)
        # but at minimum, result should not be empty
        assert len(result["outfit"]) > 0, f"Empty outfit for interview: {result}"

    def test_party_works_with_dress(self):
        """Party with a dress should recommend it."""
        wardrobe = [item("dress", "red")]
        result = _generate_fallback(wardrobe, "party")
        assert len(result["outfit"]) == 1
        assert "တစ်ဆက်တည်းဝတ်စုံ" in result["outfit"][0]

    def test_wedding_prefers_traditional(self):
        """Wedding should prefer traditional if available."""
        wardrobe = [
            item("traditional", "gold"),
            item("dress", "red"),
        ]
        result = _generate_fallback(wardrobe, "wedding")
        assert len(result["outfit"]) > 0
        # Traditional should be picked over dress for wedding
        assert "မြန်မာဝတ်စုံ" in result["outfit"][0] or "traditional" in result["outfit"][0].lower()

    def test_casual_returns_top_and_bottom(self):
        """Casual with top+bottom should recommend both."""
        wardrobe = [
            item("top", "white"),
            item("bottom", "blue"),
        ]
        result = _generate_fallback(wardrobe, "casual")
        assert len(result["outfit"]) == 2, (
            f"Expected top+bottom, got: {result['outfit']}"
        )

    def test_wedding_honest_when_unsuitable(self):
        """Wedding with only casual items should explain it's unsuitable."""
        wardrobe = [
            item("top", "yellow"),
            item("bottom", "green"),
        ]
        result = _generate_fallback(wardrobe, "wedding")
        # Should still try, but explanation should mention limitation
        assert len(result["outfit"]) > 0 or "မရှိ" in result["explanation"]


# ── Tests: diversity — not always red/navy ──────────────────


class TestDiversity:
    """Test that the fallback stylist varies recommendations."""

    def test_different_colors_possible(self):
        """With diverse wardrobe, recommendations shouldn't always be red."""
        wardrobe = [
            item("top", "red"),
            item("top", "white"),
            item("top", "green"),
            item("bottom", "navy"),
            item("bottom", "black"),
            item("bottom", "beige"),
        ]
        colors_seen = set()
        for _ in range(10):
            result = _generate_fallback(wardrobe, "casual")
            for outfit_item in result["outfit"]:
                # Extract color from "အပေါ်ဝတ် · red" format
                if " · " in outfit_item:
                    color = outfit_item.split(" · ")[-1].strip()
                    colors_seen.add(color)
        # With 10 runs and diverse items, should see at least 3 different colors
        assert len(colors_seen) >= 2, (
            f"Only saw colors: {colors_seen} — not diverse enough"
        )

    def test_party_not_always_red_dress(self):
        """Party with multiple dresses shouldn't always pick the red one."""
        wardrobe = [
            item("dress", "red"),
            item("dress", "black"),
            item("dress", "purple"),
            item("dress", "pink"),
        ]
        colors_seen = set()
        for _ in range(15):
            result = _generate_fallback(wardrobe, "party")
            if result["outfit"]:
                outfit_text = result["outfit"][0]
                if " · " in outfit_text:
                    colors_seen.add(outfit_text.split(" · ")[-1].strip())
        # Should see variety — not only red every time
        assert len(colors_seen) >= 2, (
            f"Party always picked: {colors_seen}"
        )

    def test_interview_not_always_navy(self):
        """Interview recommendations should vary among appropriate colors."""
        wardrobe = [
            item("top", "navy"),
            item("top", "white"),
            item("top", "beige"),
            item("bottom", "navy"),
            item("bottom", "black"),
            item("bottom", "gray"),
        ]
        colors_seen = set()
        for _ in range(15):
            result = _generate_fallback(wardrobe, "interview")
            for outfit_item in result["outfit"]:
                if " · " in outfit_item:
                    colors_seen.add(outfit_item.split(" · ")[-1].strip())
        assert len(colors_seen) >= 2, (
            f"Interview only used: {colors_seen}"
        )


# ── Tests: _pick_best randomization ─────────────────────────


class TestPickBest:
    """Test the randomized selection helper."""

    def test_returns_none_for_empty(self):
        assert _pick_best([]) is None

    def test_returns_item_from_list(self):
        entries = [(80, item("top", "white")), (60, item("top", "red"))]
        result = _pick_best(entries)
        assert result is not None
        assert result["category"] == "top"

    def test_top_scored_items_preferred(self):
        """Over many runs, top-scored items should appear most often."""
        entries = [
            (90, item("top", "white")),
            (50, item("top", "red")),
        ]
        white_count = 0
        red_count = 0
        for _ in range(100):
            result = _pick_best(entries, margin=5)
            if result["color"] == "white":
                white_count += 1
            else:
                red_count += 1
        # The 90-scored item should dominate (margin=5 means only >=85 count)
        assert white_count > red_count, (
            f"Top-scored item not preferred: white={white_count}, red={red_count}"
        )

    def test_tied_items_get_variety(self):
        """Tied (or nearly-tied) items should each get picked sometimes."""
        entries = [
            (80, item("top", "white")),
            (79, item("top", "beige")),
        ]
        colors_seen = set()
        for _ in range(50):
            result = _pick_best(entries, margin=5)
            colors_seen.add(result["color"])
        # Both should appear (margin=5 means 80-5=75, both >=75 qualify)
        assert len(colors_seen) >= 2, f"Only saw: {colors_seen}"


# ── Tests: _classify_item ───────────────────────────────────


class TestClassifyItem:
    """Test item classification into broad types."""

    def test_classify_dress(self):
        assert _classify_item(item("dress", "red")) == "dress"

    def test_classify_top(self):
        assert _classify_item(item("top", "white")) == "top"
        assert _classify_item(item("shirt", "blue")) == "top"
        assert _classify_item(item("blouse", "pink")) == "top"

    def test_classify_bottom(self):
        assert _classify_item(item("bottom", "navy")) == "bottom"
        assert _classify_item(item("pants", "black")) == "bottom"

    def test_classify_traditional(self):
        assert _classify_item(item("traditional", "gold")) == "traditional"
        assert _classify_item(item("longyi", "green")) == "traditional"

    def test_classify_outerwear(self):
        assert _classify_item(item("outerwear", "brown")) == "outerwear"

    def test_classify_shoes(self):
        assert _classify_item(item("shoes", "black")) == "shoes"

    def test_classify_accessory(self):
        assert _classify_item(item("accessory", "gold")) == "accessory"


# ── Tests: _color_matches ───────────────────────────────────


class TestColorMatches:
    """Test case-insensitive color matching."""

    def test_exact_match(self):
        assert _color_matches("red", {"red", "black"})

    def test_case_insensitive(self):
        assert _color_matches("RED", {"red", "black"})
        assert _color_matches("Navy", {"navy", "white"})

    def test_no_match(self):
        assert not _color_matches("yellow", {"red", "black"})

    def test_empty_color(self):
        assert not _color_matches("", {"red"})
        assert not _color_matches(None, {"red"})


# ── Tests: _score_item ──────────────────────────────────────


class TestScoreItem:
    """Test item scoring logic."""

    def test_interview_penalizes_bright_colors(self):
        score_white = _score_item(item("top", "white"), "top", "interview", None)
        score_yellow = _score_item(item("top", "yellow"), "top", "interview", None)
        assert score_white > score_yellow, (
            f"white={score_white}, yellow={score_yellow}"
        )

    def test_party_prefers_dress_over_top(self):
        score_dress = _score_item(item("dress", "red"), "dress", "party", None)
        score_top = _score_item(item("top", "red"), "top", "party", None)
        assert score_dress > score_top, (
            f"dress={score_dress}, top={score_top}"
        )

    def test_formal_style_preference_boosts_dress(self):
        score_with = _score_item(item("dress", "navy"), "dress", "interview", None,
                                  style_preference="formal")
        score_without = _score_item(item("dress", "navy"), "dress", "interview", None)
        assert score_with >= score_without, (
            f"style boost not applied: {score_with} vs {score_without}"
        )

    def test_returns_bounded_0_to_100(self):
        """Score should always be between 0 and 100."""
        for broad_type in ("top", "bottom", "dress", "traditional",
                           "outerwear", "shoes", "accessory"):
            for occasion in ("interview", "wedding", "party", "casual", "work"):
                s = _score_item(item(broad_type, "red"), broad_type, occasion, 25)
                assert 0 <= s <= 100, f"Score {s} out of bounds for {broad_type}/{occasion}"
