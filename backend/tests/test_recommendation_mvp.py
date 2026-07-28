"""Tests for the OpenRouter-first stylist recommendation MVP."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import settings
from database import Base
from models import Profile, StyleSession, User, Wardrobe
from routes import stylist
from services.gemini_svc import _parse_response as parse_gemini_response
from services.openai_svc import _parse_ai_response as parse_openai_response
from services.openrouter_svc import _parse_recommendation_response
from services.stylist_prompt import (
    WUTT_PERSONALITY_PROMPT,
    WUTT_RECOMMENDATION_PROMPT,
    accessory_selection_type,
    classify_occasion_context,
    is_shopping_intent,
    is_visual_comparison_request,
    occasion_context_prompt,
    recommendation_mode_prompt,
)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """Return an isolated database containing production metadata."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_openrouter_receives_wardrobe_and_profile_context(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="stylist@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Profile(
        user_id=user.id,
        gender="woman",
        height_cm=165,
        top_size="M",
        bottom_size="M",
        skin_tone="warm",
        style_preference="minimal",
        fit_preference="relaxed",
        outfit_vibe="polished",
        preferred_colors="navy, cream",
    ))
    db.add(Wardrobe(
        user_id=user.id,
        cloudinary_url="https://images.example/shirt.jpg",
        cloudinary_public_id="shirt-id",
        category="Top",
        subtype="Linen shirt",
        color="Cream",
        description="Relaxed fit",
        style_tags="minimal, casual",
        material_tags="linen",
        occasion_tags="work, weekend",
        brand="WUTT Studio",
        formality_level="Smart casual",
        season_suitability="Hot season",
    ))
    db.add(StyleSession(
        user_id=user.id,
        occasion="work",
        ai_response='{"outfit":["Cream linen shirt","Black trousers"]}',
    ))
    db.commit()

    captured: dict = {}

    def fake_openrouter(**kwargs):
        captured.update(kwargs)
        return {
            "outfit": ["Cream linen shirt"],
            "explanation": "A polished minimal choice for work.",
            "weather_based_tip": "Roll the sleeves if it feels warm.",
        }

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(stylist, "openrouter_recommend", fake_openrouter)

    response = stylist.recommend_outfit(
        stylist.RecommendRequest(occasion="work"),
        db,
        user,
    )

    assert response["data"]["source"] == "openrouter"
    assert response["data"]["outfit"][0] == (
        "Linen Shirt — Top, Cream (id 1)"
    )
    assert any("shoes" in item.casefold() for item in response["data"]["outfit"])
    assert any("bag" in item.casefold() for item in response["data"]["outfit"])
    assert captured["occasion"] == "work"
    assert captured["style_preference"] == "minimal"
    assert captured["profile_data"]["fit_preference"] == "relaxed"
    assert captured["profile_data"]["preferred_colors"] == "navy, cream"
    item = captured["wardrobe_items"][0]
    assert item["category"] == "Top"
    assert item["subtype"] == "Linen shirt"
    assert item["style_tags"] == "minimal, casual"
    assert item["material_tags"] == "linen"
    assert item["occasion_tags"] == "work, weekend"
    assert item["brand"] == "WUTT Studio"
    assert item["formality_level"] == "Smart casual"
    assert item["season_suitability"] == "Hot season"
    assert item["recent_recommendation_count"] == 1


def test_wardrobe_context_ignores_empty_optional_metadata(
    db: Session,
) -> None:
    user = User(email="legacy-wardrobe@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    item = Wardrobe(
        user_id=user.id,
        cloudinary_url="https://images.example/watch.jpg",
        cloudinary_public_id="watch-id",
        category="Accessory",
        subtype="Watch",
        color="Gold",
        style_tags="luxury",
        occasion_tags="formal",
        material_tags=None,
        brand=" ",
        formality_level=None,
        season_suitability="",
        description=None,
    )

    context = stylist._wardrobe_context_item(item)

    assert context["category"] == "Accessory"
    assert context["subtype"] == "Watch"
    assert context["color"] == "Gold"
    assert context["style_tags"] == "luxury"
    assert context["occasion_tags"] == "formal"
    assert "material_tags" not in context
    assert "brand" not in context
    assert "formality_level" not in context
    assert "season_suitability" not in context
    assert "description" not in context


def test_openrouter_response_parser_handles_fenced_json() -> None:
    parsed = _parse_recommendation_response(
        """```json
        {
          "outfit": ["Navy overshirt", "Cream trousers"],
          "explanation": "The colors feel polished and balanced.",
          "weather_tip": "Carry a light rain layer."
        }
        ```"""
    )

    assert parsed == {
        "outfit": ["Navy overshirt", "Cream trousers"],
        "explanation": "The colors feel polished and balanced.",
        "weather_based_tip": "Carry a light rain layer.",
    }


def test_openrouter_response_parser_rejects_invalid_content() -> None:
    assert _parse_recommendation_response("not structured output") is None


def test_normal_occasion_request_is_accepted_and_normalized() -> None:
    request = stylist.RecommendRequest(occasion="  dinner   date  ")
    assert request.occasion == "dinner date"


def test_long_burmese_mixed_language_shopping_request_is_accepted() -> None:
    query = (
        "မနက်ဖြန် သူငယ်ချင်းတွေနဲ့ dinner date သွားဖို့ရှိလို့ "
        "ကျွန်မ wardrobe ထဲက cream top နဲ့လိုက်မယ့် skirt အသစ်တစ်ထည် "
        "ဝယ်ချင်ပါတယ်၊ casual ဖြစ်ပေမယ့် နည်းနည်း polished လည်းဖြစ်ချင်တယ်"
    )
    assert len(query) > 100
    request = stylist.RecommendRequest(occasion=query)
    assert request.occasion == query
    assert is_shopping_intent(request.occasion)


def test_long_request_reaches_recommendation_flow_without_422(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="long-query@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    query = (
        "မနက်ဖြန် dinner date အတွက် ကျွန်မရဲ့ minimal style နဲ့လိုက်ပြီး "
        "cream top ကိုလည်းတွဲဝတ်လို့ရမယ့် skirt အသစ်တစ်ထည် ဝယ်ချင်ပါတယ်၊ "
        "အရမ်း formal မဖြစ်ဘဲ သပ်သပ်ရပ်ရပ်လေး ဖြစ်ချင်တယ်"
    )
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    response = stylist.recommend_outfit(
        stylist.RecommendRequest(occasion=query),
        db,
        user,
    )

    assert response["status"] == "success"
    assert set(response["data"]) >= {
        "outfit", "explanation", "weather_based_tip",
    }
    saved = db.query(StyleSession).filter(StyleSession.user_id == user.id).one()
    assert len(saved.occasion) <= 100


def test_shopping_advice_request_uses_purchase_mode() -> None:
    query = "I want to buy a skirt for a dinner date"
    request = stylist.RecommendRequest(occasion=query)
    mode = recommendation_mode_prompt(request.occasion)
    assert is_shopping_intent(request.occasion)
    assert "shopping advice" in mode
    assert "existing wardrobe" in mode


def test_all_provider_parsers_keep_structured_recommendation_contract() -> None:
    raw = json.dumps({
        "outfit": ["Black A-line skirt", "Cream top"],
        "explanation": "I'd go with this pairing for dinner.",
        "weather_based_tip": "Bring a light layer if it gets cool.",
    })
    for parsed in (
        _parse_recommendation_response(raw),
        parse_openai_response(raw),
        parse_gemini_response(raw),
    ):
        assert parsed is not None
        assert set(parsed) == {"outfit", "explanation", "weather_based_tip"}


def test_recommendation_ids_map_back_to_wardrobe_metadata() -> None:
    wardrobe = [
        {"id": 22, "category": "Dress", "subtype": "Myanmar dress"},
        {"id": 31, "category": "Shoes", "subtype": "black sandals"},
    ]

    normalized = stylist._normalize_outfit_labels(
        ["Myanmar dress (id22)", "Black sandals (id=31)"],
        wardrobe,
    )

    assert normalized == [
        "Myanmar Dress — Dress, Unspecified color (id 22)",
        "Black Sandals — Shoes, Unspecified color (id 31)",
    ]
    assert all("id" in item.casefold() for item in normalized)
    explanation = stylist._remove_technical_ids(
        "The Myanmar dress (id22) works well with id31.",
        wardrobe,
    )
    assert explanation == "The Myanmar dress works well with Black Sandals."


def test_myanmar_weather_notes_are_practical() -> None:
    rainy = stylist._myanmar_weather_tip(
        "light rain",
        29,
        82,
        "Consider meteorological conditions.",
    )
    humid = stylist._myanmar_weather_tip("clear", 33, 78, "")

    assert "umbrella" in rainy
    assert "wet streets" in rainy
    assert "breathable" in humid
    assert "hot and humid" in humid
    yangon = stylist._myanmar_weather_tip("light rain", 29, 82, "", "Yangon")
    assert "Yangon" in yangon
    no_weather = stylist._myanmar_weather_tip(
        None,
        None,
        None,
        "Choose clothes suitable for the weather.",
        query="coffee date",
    )
    assert "cardigan" in no_weather
    assert "cafés" in no_weather


def test_shared_stylist_prompt_enforces_personal_concise_tone() -> None:
    assert "Start with the recommendation" in WUTT_PERSONALITY_PROMPT
    assert "Shopping:" in WUTT_PERSONALITY_PROMPT
    assert "Body and fit:" in WUTT_PERSONALITY_PROMPT
    assert "Never say" in WUTT_PERSONALITY_PROMPT
    assert "2-3 short, friendly sentences" in WUTT_RECOMMENDATION_PROMPT
    assert "technical errors" in WUTT_RECOMMENDATION_PROMPT
    assert "main clothing, shoes, a bag, accessories" in WUTT_RECOMMENDATION_PROMPT
    assert "do not put status prefixes in labels" in WUTT_RECOMMENDATION_PROMPT
    assert "first outfit entry must be that exact" in WUTT_RECOMMENDATION_PROMPT
    assert "never substitute another item" in WUTT_RECOMMENDATION_PROMPT
    assert "Do not default to purple, linen, or black" in WUTT_RECOMMENDATION_PROMPT
    assert "never copy the user's sentence" in WUTT_PERSONALITY_PROMPT
    assert "Never open with" in WUTT_PERSONALITY_PROMPT


@pytest.mark.parametrize(
    ("query", "expected_type"),
    [
        ("Which watch should I choose?", "watch"),
        ("What bag matches this outfit?", "bag"),
        ("Which shoes should I wear?", "shoes"),
        ("Which accessory works best?", "accessory"),
    ],
)
def test_accessory_questions_use_selection_only_mode(
    query: str,
    expected_type: str,
) -> None:
    assert accessory_selection_type(query) == expected_type
    mode = recommendation_mode_prompt(query)
    assert "selection only" in mode
    assert "Do not generate or repeat a complete outfit" in mode


def test_visual_comparison_mode_never_claims_to_inspect_photos() -> None:
    query = "Which watch looks better in these photos?"

    assert is_visual_comparison_request(query)
    mode = recommendation_mode_prompt(query)
    assert "Do not claim to inspect or compare images" in mode
    assert "WUTT AI Vision" in mode


def test_visual_comparison_without_metadata_does_not_invent_choice() -> None:
    result = stylist._visual_comparison_fallback(
        [
            {"id": 1, "category": "Accessory", "subtype": "Watch A"},
            {"id": 2, "category": "Accessory", "subtype": "Watch B"},
        ],
        "Which watch looks better in these photos?",
    )

    assert result["outfit"] == []
    assert "WUTT AI Vision" in result["explanation"]
    assert "Add color, style, and occasion details" in result["explanation"]


def test_visual_comparison_can_use_sufficient_saved_metadata() -> None:
    result = stylist._visual_comparison_fallback(
        [
            {
                "id": 1,
                "category": "Accessory",
                "subtype": "Minimal watch",
                "color": "Silver",
                "style_tags": "minimal, work",
            },
            {
                "id": 2,
                "category": "Accessory",
                "subtype": "Gold watch",
                "color": "Gold",
                "occasion_tags": "wedding, formal",
            },
        ],
        "Which watch should I choose from these photos?",
    )

    assert result["outfit"] == ["Minimal Watch — Accessory, Silver (id 1)"]
    assert "Based only on the saved metadata" in result["explanation"]
    assert "Alternative: Gold Watch — Accessory, Gold (id 2)" in result["explanation"]


def test_user_specified_item_and_color_stay_as_outfit_base() -> None:
    wardrobe = [
        {
            "id": 10,
            "category": "Top",
            "subtype": "Myanmar top",
            "color": "Purple",
        },
        {
            "id": 11,
            "category": "Top",
            "subtype": "Linen blouse",
            "color": "White",
        },
    ]

    preserved = stylist._preserve_requested_base(
        ["White Linen Blouse", "Black Longyi", "Comfortable Sandals"],
        "purple Myanmar top, what should I wear?",
        wardrobe,
    )

    assert preserved[0] == "Myanmar Top — Top, Purple (id 10)"
    assert preserved[1:] == [
        "Black Longyi",
        "Comfortable Sandals",
    ]


def test_user_specified_base_is_moved_to_first_position() -> None:
    wardrobe = [{
        "id": 10,
        "category": "Top",
        "subtype": "Myanmar top",
        "color": "Purple",
    }]

    preserved = stylist._preserve_requested_base(
        ["Black Longyi", "Purple Myanmar Top", "Comfortable Sandals"],
        "How do I style my purple Myanmar top?",
        wardrobe,
    )

    assert preserved == [
        "Myanmar Top — Top, Purple (id 10)",
        "Black Longyi",
        "Comfortable Sandals",
    ]


def test_myanmar_pagoda_request_uses_respectful_cultural_context() -> None:
    query = "မနက်ဖြန် ရွှေတိဂုံဘုရား သွားမလို့ ဘာဝတ်ရမလဲ"
    guidance = occasion_context_prompt(query)

    assert classify_occasion_context(query) == "religious_place"
    assert "Myanmar traditional clothing" in guidance
    assert "longyi" in guidance
    assert "covered shoulders and knees" in guidance
    assert "shoes easy to remove" in guidance
    assert "Reject sexy, mini, revealing" in guidance


@pytest.mark.parametrize(
    ("query", "expected_context"),
    [
        ("ကော်ဖီဆိုင်ထိုင်မလို့", "casual_outing"),
        ("ကောင်လေးနဲ့တွေ့မှာ", "date"),
        ("I have a client meeting", "business_meeting"),
        ("ဘုရားသွားမှာ", "religious_place"),
    ],
)
def test_natural_language_occasion_context_is_detected(
    query: str,
    expected_context: str,
) -> None:
    assert classify_occasion_context(query) == expected_context


def test_pagoda_dress_code_overrides_inappropriate_item_tags() -> None:
    wardrobe = [
        {
            "id": 1,
            "category": "Dress",
            "subtype": "Mini dress",
            "color": "Purple",
            "style_tags": "cute, sexy, party",
            "occasion_tags": "religious, party",
            "description": "Revealing party dress",
        },
        {
            "id": 2,
            "category": "Traditional",
            "subtype": "Myanmar blouse",
            "color": "Cream",
            "style_tags": "modest, traditional",
            "occasion_tags": "religious",
            "description": "Covered and comfortable",
        },
    ]

    result = stylist._wardrobe_fallback_outfit(
        wardrobe,
        "ဘုရားသွားမယ်",
        30,
        None,
    )
    combined = " ".join(result["outfit"]).casefold()

    assert "မြန်မာဝတ်စုံ" in combined
    assert "covered and comfortable" in combined
    assert "mini" not in combined
    assert "sexy" not in combined


def test_english_temple_request_is_not_treated_as_generic_western_styling() -> None:
    query = "What should I wear to a temple in Yangon?"
    guidance = occasion_context_prompt(query)

    assert classify_occasion_context(query) == "religious_place"
    assert "Myanmar cultural setting" in guidance
    assert "styling respectful" in guidance


def test_date_outfit_request_gets_date_context_and_complete_look() -> None:
    query = "I need an outfit for a coffee date"
    mode = recommendation_mode_prompt(query)

    assert classify_occasion_context(query) == "date"
    assert "softly polished" in occasion_context_prompt(query)
    assert "shoes, a bag, accessories" in mode
    completed = stylist._complete_outfit_presentation(["Cream linen dress"], query)
    assert "Clean, comfortable shoes" in completed
    assert "Small shoulder bag" in completed
    assert "One simple personal accessory" in completed
    assert "Light layer for later" in completed
    assert all(not item.startswith("Suggested:") for item in completed)


def test_wedding_request_gets_myanmar_appropriate_guidance() -> None:
    query = "What should I wear to a Myanmar wedding?"
    guidance = occasion_context_prompt(query)

    assert classify_occasion_context(query) == "wedding"
    assert "refined traditional clothing" in guidance
    assert "polished longyi pairing" in guidance


def test_client_meeting_raises_formality_and_uses_saved_finishing_pieces() -> None:
    query = "What should I wear for a client meeting?"
    wardrobe = [
        {"id": 1, "category": "Top", "subtype": "White shirt", "color": "White"},
        {"id": 2, "category": "Bottom", "subtype": "Tailored trousers", "color": "Navy"},
        {"id": 3, "category": "Outerwear", "subtype": "Blazer", "color": "Navy"},
        {"id": 4, "category": "Accessory", "subtype": "Minimal watch", "color": "Silver"},
        {"id": 5, "category": "Accessory", "subtype": "Structured bag", "color": "Brown"},
        {"id": 6, "category": "Shoes", "subtype": "Clean loafers", "color": "Brown"},
        {"id": 7, "category": "Top", "subtype": "Hoodie", "color": "Black"},
    ]

    assert classify_occasion_context(query) == "business_meeting"
    guidance = occasion_context_prompt(query)
    assert "formality by one level" in guidance
    assert "Occasion fit outranks profile style preference" in guidance

    result = stylist._wardrobe_fallback_outfit(wardrobe, query, 28, None)
    combined = " ".join(result["outfit"]).casefold()
    assert "blazer" in combined
    assert "watch" in combined
    assert "structured bag" in combined
    assert "loafers" in combined
    assert "hoodie" not in combined


def test_profile_style_is_secondary_and_korean_style_is_opt_in() -> None:
    assert "occasion dress code and cultural respect first" in WUTT_RECOMMENDATION_PROMPT
    assert "profile style preference last" in WUTT_RECOMMENDATION_PROMPT
    assert "Do not mention or favor Korean-casual unless" in WUTT_RECOMMENDATION_PROMPT


def test_pagoda_outfit_completion_uses_respectful_finishing_pieces() -> None:
    completed = stylist._complete_outfit_presentation(
        ["Traditional blouse", "Longyi"],
        "ဘုရားသွားဖို့",
    )

    assert "Easy-to-remove sandals" in completed
    assert "Small, secure shoulder bag" in completed
    assert "Simple watch or understated jewelry" in completed
    assert "Light shawl for extra coverage" in completed
    assert all(not item.startswith("Suggested:") for item in completed)


def test_explanation_names_selected_saved_wardrobe_piece() -> None:
    wardrobe = [{
        "id": 22,
        "category": "dress",
        "subtype": "Myanmar dress",
        "description": "Red linen celebration dress",
    }]

    explanation = stylist._personalize_explanation(
        "It feels polished without being too formal.",
        ["Myanmar Dress", "Comfortable Sandals"],
        wardrobe,
    )

    assert not explanation.startswith("I’d start with")
    assert explanation.endswith("Your Myanmar Dress keeps the outfit grounded.")


def test_explanation_does_not_make_accessory_the_outfit_start() -> None:
    explanation = stylist._personalize_explanation(
        "Keep the accessories simple.",
        ["Gold Watch", "Cream Blouse"],
        [{
            "id": 22,
            "category": "Accessory",
            "subtype": "Watch",
            "color": "Gold",
        }],
    )

    assert explanation == "Keep the accessories simple."
    assert "start with" not in explanation.casefold()


def test_recent_recommendations_are_marked_without_changing_wardrobe_data() -> None:
    items = [
        {"id": 1, "subtype": "Purple linen top", "color": "Purple"},
        {"id": 2, "subtype": "Cream cotton top", "color": "Cream"},
    ]

    annotated = stylist._annotate_recent_recommendations(
        items,
        [
            '{"outfit":["Purple linen top","Black skirt"]}',
            '{"outfit":["Purple linen top","Brown longyi"]}',
        ],
    )

    assert annotated[0]["recent_recommendation_count"] == 2
    assert "recent_recommendation_count" not in annotated[1]


def test_accessory_fallback_selects_only_requested_category() -> None:
    result = stylist._accessory_selection_fallback(
        [
            {
                "id": 1,
                "category": "Accessory",
                "subtype": "Gold watch",
                "recent_recommendation_count": 2,
            },
            {
                "id": 2,
                "category": "Accessory",
                "subtype": "Minimal watch",
            },
            {
                "id": 3,
                "category": "Top",
                "subtype": "Linen shirt",
            },
        ],
        "Which watch should I choose?",
    )

    assert result["outfit"] == [
        "Minimal Watch — Accessory, Unspecified color (id 2)"
    ]
    assert (
        "Alternative: Gold Watch — Accessory, Unspecified color (id 1)"
        in result["explanation"]
    )
    assert "Linen" not in result["explanation"]


def test_wardrobe_ranking_puts_exact_mentioned_item_first() -> None:
    wardrobe = [
        {
            "id": 8,
            "category": "Bottom",
            "subtype": "Pleated skirt",
            "color": "Brown",
            "occasion_tags": "work, date",
            "style_tags": "elegant",
        },
        {
            "id": 15,
            "category": "Bottom",
            "subtype": "A-line skirt",
            "color": "Brown",
            "occasion_tags": "date",
            "style_tags": "minimal",
        },
        {
            "id": 21,
            "category": "Bottom",
            "subtype": "Denim skirt",
            "color": "Navy",
            "occasion_tags": "casual",
            "style_tags": "streetwear",
        },
    ]

    ranked = stylist._rank_wardrobe_context(
        wardrobe,
        "How should I style my brown A-line skirt?",
        None,
    )

    assert ranked[0]["id"] == 15
    anchor = stylist._find_explicit_anchor(
        "How should I style my brown A-line skirt?",
        ranked,
    )
    assert anchor is not None
    assert stylist._wardrobe_identity(anchor) == (
        "A-line Skirt — Bottom, Brown (id 15)"
    )


def test_color_only_provider_output_is_grounded_to_one_ranked_item() -> None:
    wardrobe = [
        {"id": 8, "category": "Bottom", "subtype": "Pleated skirt", "color": "Brown"},
        {"id": 15, "category": "Bottom", "subtype": "A-line skirt", "color": "Brown"},
    ]

    grounded = stylist._normalize_outfit_labels(["Brown"], wardrobe)

    assert grounded == ["Pleated Skirt — Bottom, Brown (id 8)"]


def test_unowned_generic_items_are_not_described_as_yours() -> None:
    cleaned = stylist._remove_unowned_possessives(
        "Pair your linen with your watch and your bag.",
        [{"id": 1, "category": "Top", "subtype": "Cotton shirt"}],
    )

    assert "your linen" not in cleaned.casefold()
    assert "your watch" not in cleaned.casefold()
    assert "your bag" not in cleaned.casefold()


def test_chat_fallback_matches_mentioned_wardrobe_item_before_follow_up(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="mentioned-item-chat@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add_all([
        Wardrobe(
            user_id=user.id,
            cloudinary_url="https://images.example/purple-top.jpg",
            cloudinary_public_id="purple-top",
            category="Top",
            subtype="Myanmar top",
            color="Purple",
        ),
        Wardrobe(
            user_id=user.id,
            cloudinary_url="https://images.example/navy-jeans.jpg",
            cloudinary_public_id="navy-jeans",
            category="Bottom",
            subtype="Straight jeans",
            color="Navy",
        ),
        Wardrobe(
            user_id=user.id,
            cloudinary_url="https://images.example/black-bag.jpg",
            cloudinary_public_id="black-bag",
            category="Accessory",
            subtype="Shoulder bag",
            color="Black",
        ),
        Wardrobe(
            user_id=user.id,
            cloudinary_url="https://images.example/sandals.jpg",
            cloudinary_public_id="sandals",
            category="Shoes",
            subtype="Comfortable sandals",
            color="Brown",
        ),
    ])
    db.commit()
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    response = stylist.chat_with_stylist(
        stylist.ChatRequest(message="purple top လေးနဲ့ဘာနဲ့တွဲဝတ်ရင်ကောင်းမလည်း"),
        db,
        user,
    )
    copy = response["data"]["response"]

    assert "Myanmar Top — Top, Purple" in copy
    assert "Recommended:" in copy
    assert "Straight Jeans — Bottom, Navy" in copy
    assert "Shoulder Bag — Accessory, Black" in copy
    assert "Comfortable Sandals — Shoes, Brown" in copy
    assert "Tell me one piece" not in copy
    assert "Tell me the occasion" not in copy


def test_chat_fallback_only_asks_for_piece_when_context_is_empty(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="empty-chat@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    response = stylist.chat_with_stylist(
        stylist.ChatRequest(message="Can you help me choose an outfit?"),
        db,
        user,
    )

    assert "Tell me one piece you want to wear" in response["data"]["response"]


def test_chat_prompt_receives_existing_profile_context(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="profile-chat@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Profile(
        user_id=user.id,
        height_cm=170,
        style_preference="Korean casual",
        fit_preference="slim",
        preferred_colors="black, cream",
    ))
    db.commit()

    captured: dict = {}

    def fake_chat(**kwargs):
        captured.update(kwargs)
        return "I think a black A-line skirt would be a great next buy for you."

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(stylist, "openrouter_chat", fake_chat)

    response = stylist.chat_with_stylist(
        stylist.ChatRequest(message="I want to buy something"),
        db,
        user,
    )

    prompt = captured["user_message"]
    assert '"height_cm": 170' in prompt
    assert '"style_preference": "Korean casual"' in prompt
    assert '"fit_preference": "slim"' in prompt
    assert response["data"]["response"].startswith("I think")


def test_provider_failure_returns_graceful_structured_result(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="fallback@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Wardrobe(
        user_id=user.id,
        cloudinary_url="https://images.example/top.jpg",
        cloudinary_public_id="top-id",
        category="Top",
        subtype="T-shirt",
    ))
    db.commit()

    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(stylist, "openrouter_recommend", lambda **kwargs: None)

    response = stylist.recommend_outfit(
        stylist.RecommendRequest(occasion="casual"),
        db,
        user,
    )

    assert response["status"] == "success"
    assert response["data"]["source"] == "fallback"
    assert response["data"]["outfit"]
    assert any("T-shirt" in item or "t-shirt" in item for item in response["data"]["outfit"])
    assert "try again" not in response["data"]["explanation"].lower()
    assert "error" not in response["data"]["explanation"].lower()
    assert "tell me one piece" not in response["data"]["explanation"].lower()
    assert response["data"]["weather_based_tip"]


@pytest.mark.parametrize(
    ("query", "expected_piece", "expected_context"),
    [
        ("ဘုရားသွားဖို့ ဘာဝတ်ရမလည်း", "longyi", "modest"),
        ("What should I wear for wedding?", "longyi", "မင်္ဂလာ"),
        ("What should I wear for a date?", "blouse", "date"),
    ],
)
def test_clear_outfit_requests_use_immediate_wardrobe_fallback(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    expected_piece: str,
    expected_context: str,
) -> None:
    user = User(email=f"fallback-{len(query)}@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add_all([
        Wardrobe(
            user_id=user.id,
            cloudinary_url="https://images.example/longyi.jpg",
            cloudinary_public_id=f"longyi-{user.id}",
            category="traditional",
            subtype="longyi",
            color="green",
            description="Myanmar traditional longyi",
            occasion_tags="wedding, temple",
        ),
        Wardrobe(
            user_id=user.id,
            cloudinary_url="https://images.example/blouse.jpg",
            cloudinary_public_id=f"blouse-{user.id}",
            category="top",
            subtype="blouse",
            color="cream",
            description="Soft cream blouse",
            occasion_tags="date, casual",
        ),
        Wardrobe(
            user_id=user.id,
            cloudinary_url="https://images.example/trousers.jpg",
            cloudinary_public_id=f"trousers-{user.id}",
            category="bottom",
            subtype="trousers",
            color="black",
            description="Clean black trousers",
            occasion_tags="date, work",
        ),
    ])
    db.commit()
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "gemini_api_key", "")

    response = stylist.recommend_outfit(
        stylist.RecommendRequest(occasion=query),
        db,
        user,
    )

    data = response["data"]
    assert data["source"] == "fallback"
    assert any(expected_piece.casefold() in item.casefold() for item in data["outfit"])
    assert expected_context.casefold() in data["explanation"].casefold()
    assert any("shoes" in item.casefold() or "sandals" in item.casefold() for item in data["outfit"])
    assert any("bag" in item.casefold() for item in data["outfit"])
    assert "tell me one piece" not in data["explanation"].casefold()


def test_delete_today_history_preserves_older_sessions(db: Session) -> None:
    user = User(email="history@example.com", password_hash="unused")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add_all([
        StyleSession(
            user_id=user.id,
            occasion="chat",
            ai_response='{"message":"today","response":"today"}',
            created_at=datetime.now(timezone.utc),
        ),
        StyleSession(
            user_id=user.id,
            occasion="work",
            ai_response='{"outfit":["Blazer"]}',
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        ),
    ])
    db.commit()

    response = stylist.delete_today_history(user.id, db, user)

    assert response["data"]["deleted"] == 1
    remaining = db.query(StyleSession).filter(StyleSession.user_id == user.id).all()
    assert len(remaining) == 1
    assert remaining[0].occasion == "work"
