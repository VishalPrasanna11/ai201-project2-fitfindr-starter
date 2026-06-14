"""
tests/test_tools.py

Unit tests for the three FitFindr tools.
LLM-calling tools (suggest_outfit, create_fit_card) use mocked Groq responses
so tests run without a live API key.
"""

from unittest.mock import MagicMock, patch

import pytest

from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


# ── search_listings ────────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)


def test_search_size_filter_substring():
    # "M" should match listings sized "S/M", "M", "M/L", etc. — not just exact "M"
    results = search_listings("top", size="M", max_price=None)
    for item in results:
        assert "m" in item["size"].lower()


def test_search_returns_at_most_five():
    # "vintage" matches many listings — should still cap at 5
    results = search_listings("vintage", size=None, max_price=None)
    assert len(results) <= 5


def test_search_result_fields():
    results = search_listings("denim", size=None, max_price=None)
    assert len(results) > 0
    required_fields = {"id", "title", "description", "category", "style_tags",
                       "size", "condition", "price", "colors", "brand", "platform"}
    for item in results:
        assert required_fields.issubset(item.keys())


# ── suggest_outfit ─────────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "id": "lst_006",
    "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "description": "Vintage-style bootleg tee with faded graphic.",
    "category": "tops",
    "style_tags": ["graphic tee", "vintage", "grunge", "streetwear"],
    "size": "L",
    "condition": "good",
    "price": 24.0,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}


def _mock_groq_response(text: str):
    """Build a minimal mock that looks like a Groq chat completion response."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


@patch("tools._get_groq_client")
def test_suggest_outfit_with_wardrobe(mock_client):
    mock_client.return_value.chat.completions.create.return_value = (
        _mock_groq_response("Pair this tee with your baggy jeans and chunky sneakers.")
    )
    result = suggest_outfit(SAMPLE_ITEM, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_does_not_crash(mock_client):
    """Failure mode: empty wardrobe should return styling advice, not raise."""
    mock_client.return_value.chat.completions.create.return_value = (
        _mock_groq_response("Great with high-waisted jeans and chunky boots.")
    )
    result = suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_calls_llm(mock_client):
    """Empty wardrobe should still call the LLM (with a different prompt)."""
    mock_create = mock_client.return_value.chat.completions.create
    mock_create.return_value = _mock_groq_response("Style advice here.")
    suggest_outfit(SAMPLE_ITEM, get_empty_wardrobe())
    assert mock_create.called


# ── create_fit_card ────────────────────────────────────────────────────────────

SAMPLE_OUTFIT = (
    "Pair the boxy tee with baggy dark-wash jeans and chunky white sneakers. "
    "Roll the sleeves once for shape."
)


def test_create_fit_card_empty_outfit_returns_error_string():
    """Failure mode: empty outfit string must return an error message, not raise."""
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "error" in result.lower() or "no outfit" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "error" in result.lower() or "no outfit" in result.lower()


@patch("tools._get_groq_client")
def test_create_fit_card_returns_string(mock_client):
    mock_client.return_value.chat.completions.create.return_value = (
        _mock_groq_response("thrifted this off depop for $24 and it slaps 🖤")
    )
    result = create_fit_card(SAMPLE_OUTFIT, SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_create_fit_card_missing_price_does_not_crash(mock_client):
    """new_item missing price should still produce a caption, not raise."""
    mock_client.return_value.chat.completions.create.return_value = (
        _mock_groq_response("found this gem on depop and styled it perfectly 🖤")
    )
    item_no_price = {k: v for k, v in SAMPLE_ITEM.items() if k != "price"}
    result = create_fit_card(SAMPLE_OUTFIT, item_no_price)
    assert isinstance(result, str)
    assert len(result) > 0
