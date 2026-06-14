"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform
    """
    listings = load_listings()

    # Filter by max_price (inclusive)
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    # Filter by size — case-insensitive substring match
    if size is not None:
        size_lower = size.lower()
        listings = [l for l in listings if size_lower in l["size"].lower()]

    # Score each listing by counting keyword hits in title, description, style_tags
    keywords = [kw.lower() for kw in description.split() if kw]

    def score(listing: dict) -> int:
        haystack = (
            listing["title"].lower()
            + " "
            + listing["description"].lower()
            + " "
            + " ".join(listing["style_tags"]).lower()
        )
        return sum(1 for kw in keywords if kw in haystack)

    scored = [(score(l), l) for l in listings]

    # Drop listings with no keyword overlap
    scored = [(s, l) for s, l in scored if s > 0]

    # Sort by score descending, return top 5 listing dicts
    scored.sort(key=lambda x: x[0], reverse=True)
    return [l for _, l in scored[:5]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.
    """
    client = _get_groq_client()

    item_desc = (
        f"{new_item['title']} (${new_item['price']}, {new_item['platform']}) — "
        f"{', '.join(new_item['colors'])} {new_item['category']}, "
        f"style: {', '.join(new_item['style_tags'])}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"A user is considering buying this thrifted item:\n{item_desc}\n\n"
            "They haven't shared their wardrobe. Give 2–3 sentences of general "
            "styling advice: what kinds of pieces pair well with this item, what "
            "aesthetic it suits, and one specific tip for wearing it."
        )
    else:
        lines = []
        for item in wardrobe_items:
            notes = f" ({item['notes']})" if item.get("notes") else ""
            lines.append(
                f"- {item['name']}: {', '.join(item['colors'])}, "
                f"{', '.join(item['style_tags'])}{notes}"
            )
        wardrobe_str = "\n".join(lines)

        prompt = (
            f"A user is considering buying this thrifted item:\n{item_desc}\n\n"
            f"Their current wardrobe includes:\n{wardrobe_str}\n\n"
            "Suggest a specific 2–4 sentence outfit combining the new item with "
            "named pieces from their wardrobe. Reference wardrobe items by name. "
            "Include at least one specific styling tip (tucking, layering, rolling "
            "sleeves, etc.)."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 1–2 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)
    """
    if not outfit or not outfit.strip():
        return (
            "Error: no outfit suggestion provided — call suggest_outfit first "
            "before generating a fit card."
        )

    client = _get_groq_client()

    title = new_item.get("title", "thrifted item")
    price = new_item.get("price")
    platform = new_item.get("platform")

    source_parts = []
    if platform:
        source_parts.append(f"from {platform}")
    if price is not None:
        source_parts.append(f"for ${price}")
    source_line = " ".join(source_parts)

    prompt = (
        f"Write a 1–2 sentence Instagram/TikTok caption for someone who just "
        f"thrifted this item:\n\n"
        f"Item: {title}\n"
        f"{f'Source: {source_line}' if source_line else ''}\n"
        f"Outfit: {outfit}\n\n"
        "Rules:\n"
        "- Casual, first-person, lowercase (like a real OOTD post, not an ad)\n"
        f"- Mention the item{', ' + source_line if source_line else ''} and the outfit vibe\n"
        "- End with 1–2 emoji\n"
        "- 1–2 sentences only, no hashtags"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=1.1,
    )
    return response.choices[0].message.content.strip()
