"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a free-text user query
    using regex. No LLM call needed — keeps the agent fast and deterministic.

    Examples:
        "vintage graphic tee under $30" → {description: "vintage graphic tee", max_price: 30.0}
        "90s jacket size M under $50"   → {description: "90s jacket", size: "m", max_price: 50.0}
    """
    text = query.lower()

    # Extract max_price — match "under $30", "under 30", "below $40", "max $25"
    max_price = None
    price_match = re.search(
        r'(?:under|below|max|less than|up to)\s*\$?(\d+(?:\.\d+)?)',
        text,
    )
    if not price_match:
        # Also catch "$30 or less" / "$30 max"
        price_match = re.search(r'\$(\d+(?:\.\d+)?)\s*(?:or less|max|or under)', text)
    if price_match:
        max_price = float(price_match.group(1))

    # Extract size — "size M", "size XL", "in size S", "in M"
    size = None
    size_match = re.search(
        r'(?:(?:in\s+)?size\s+|in\s+)(xs|xxl|xl|x[sl]\b|s\b|m\b|l\b|w\d+|us\s*\d+(?:\.\d+)?)',
        text,
    )
    if size_match:
        size = size_match.group(1).strip()

    # Build description: strip price and size fragments from the original query
    description = query
    if price_match:
        description = re.sub(
            r',?\s*(?:under|below|max|less than|up to)\s*\$?\d+(?:\.\d+)?',
            '',
            description,
            flags=re.IGNORECASE,
        )
        description = re.sub(
            r',?\s*\$\d+(?:\.\d+)?\s*(?:or less|max|or under)',
            '',
            description,
            flags=re.IGNORECASE,
        )
    if size_match:
        description = re.sub(
            r',?\s*(?:in\s+)?size\s+\S+',
            '',
            description,
            flags=re.IGNORECASE,
        )
        # Also strip bare "in M/S/L/XL" patterns that remain
        description = re.sub(
            r',?\s*\bin\s+(?:xs|xxl|xl|s|m|l)\b',
            '',
            description,
            flags=re.IGNORECASE,
        )

    description = re.sub(r'\s+', ' ', description).strip().strip(',').strip()

    return {
        "description": description if description else query,
        "size": size,
        "max_price": max_price,
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the user query into structured parameters
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search for listings — early exit if nothing matches
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        desc = parsed["description"]
        filters = []
        if parsed["size"]:
            filters.append(f"size {parsed['size'].upper()}")
        if parsed["max_price"] is not None:
            filters.append(f"under ${parsed['max_price']:.0f}")
        filter_str = " and ".join(filters)
        hint = f" matching {filter_str}" if filter_str else ""
        session["error"] = (
            f"No listings found for \"{desc}\"{hint}. "
            "Try broadening your search — remove the size filter, raise your "
            "price limit, or use different keywords (e.g. 'band tee' instead "
            "of 'graphic tee')."
        )
        return session

    # Step 4: Select the top result
    session["selected_item"] = results[0]

    # Step 5: Generate outfit suggestion using the selected item and wardrobe
    session["outfit_suggestion"] = suggest_outfit(
        new_item=session["selected_item"],
        wardrobe=session["wardrobe"],
    )

    # Step 6: Generate the fit card caption
    session["fit_card"] = create_fit_card(
        outfit=session["outfit_suggestion"],
        new_item=session["selected_item"],
    )

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"  → selected_item id: {session['selected_item']['id']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")
    print(f"outfit_suggestion is None: {session2['outfit_suggestion'] is None}")
