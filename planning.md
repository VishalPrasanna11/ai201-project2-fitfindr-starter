# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for items matching a user's description, optional size, and optional price cap. Scores each listing by counting how many query keywords appear in its title, description, and style_tags fields, then returns the top matches sorted by relevance score.

**Input parameters:**
- `description` (str, required): Free-text keyword or phrase describing what to search for (e.g. "vintage graphic tee", "denim jacket"). Matched case-insensitively against each listing's `title`, `description`, and `style_tags` fields.
- `size` (str, optional, default `None`): Size string to filter by (e.g. `"M"`, `"S"`, `"L"`). Applied as a case-insensitive substring check against the listing's `size` field, so `"M"` matches `"S/M"`, `"M/L"`, and `"XL (fits oversized M)"`.
- `max_price` (float, optional, default `None`): Upper price bound, inclusive. Listings with `price > max_price` are excluded before scoring.

**What it returns:**
A list of up to 5 listing dicts sorted by relevance score (descending). Each dict contains all original listing fields:
- `id` (str) — unique identifier, e.g. `"lst_006"`
- `title` (str) — item name, e.g. `"Graphic Tee — 2003 Tour Bootleg Style"`
- `description` (str) — narrative description
- `category` (str) — one of: `tops`, `bottoms`, `outerwear`, `shoes`, `accessories`
- `style_tags` (list[str]) — descriptors, e.g. `["vintage", "grunge", "graphic tee"]`
- `size` (str) — size string, e.g. `"L"`, `"W30 L30"`, `"S/M"`
- `condition` (str) — one of: `excellent`, `good`, `fair`
- `price` (float) — dollar amount, e.g. `24.0`
- `colors` (list[str]) — e.g. `["black"]`
- `brand` (str or `None`) — brand name or null
- `platform` (str) — one of: `depop`, `thredUp`, `poshmark`

Returns `[]` if no listings pass the filters.

**What happens if it fails or returns nothing:**
If the returned list is empty, the agent does NOT call `suggest_outfit` or `create_fit_card`. Instead it returns this message to the user: "I couldn't find any [description] matching your filters. Try broadening your search — remove the size filter, raise your price limit, or use different keywords like 'band tee' instead of 'graphic tee'."

---

### Tool 2: suggest_outfit

**What it does:**
Calls the Claude API with a prompt that includes the new listing's fields and the user's wardrobe items, asking it to suggest a specific 2–4 sentence outfit combining the new item with pieces already in the wardrobe. References wardrobe items by their `name` field and includes actionable styling tips (tucking, layering, rolling sleeves, etc.).

**Input parameters:**
- `new_item` (dict, required): A single listing dict as returned by `search_listings` — must include at minimum `title`, `category`, `colors`, `style_tags`, `price`, and `platform`.
- `wardrobe` (dict, required): A wardrobe object with an `"items"` key holding a list of wardrobe item dicts. Each item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str or None). May be an empty wardrobe (`{"items": []}`).

**What it returns:**
A single string containing a 2–4 sentence outfit suggestion. The string names specific wardrobe items by their `name` field, describes how to combine them with the new item, and includes at least one specific styling tip. Example: `"Pair this boxy bootleg tee with your baggy dark-wash straight-legs — the oversized silhouette plays well with the wide leg. Finish with your chunky white sneakers and black crossbody to keep it clean. Roll the sleeves once to break up the shape."`

**What happens if it fails or returns nothing:**
If the wardrobe is empty (`items` list has length 0), the agent still calls `suggest_outfit` but the prompt instructs Claude to give general styling advice for the new item without referencing specific wardrobe pieces (e.g. "Here's how to build around this piece: pair it with high-waisted wide-leg jeans and chunky sneakers for a classic streetwear look."). If the Claude API call fails, the agent skips `create_fit_card` and returns the listing details plus this fallback: "I found a great match but couldn't generate outfit suggestions right now — try again in a moment."

---

### Tool 3: create_fit_card

**What it does:**
Calls the Claude API to generate a short, casual social-media caption in a first-person thrift-poster voice. The caption references the item's price and source platform and optionally nods to the outfit. Intended to be copy-paste ready for Instagram or TikTok captions.

**Input parameters:**
- `outfit` (str, required): The outfit suggestion string returned by `suggest_outfit`. Used to inform the tone and content of the caption.
- `new_item` (dict, required): The listing dict for the purchased item — must include `title` (str), `price` (float), and `platform` (str) so the caption can mention where it was found and what it cost.

**What it returns:**
A single string: a 1–2 sentence caption in a casual, lowercase thrift-culture voice. Includes the `platform` name and `price`. Contains 1–2 emoji at the end. Example: `"thrifted this faded bootleg tee off depop for $24 and it was made for my baggy jeans 🖤 chunky sneakers doing all the heavy lifting"`

**What happens if it fails or returns nothing:**
If `outfit` is an empty string or `new_item` is missing `price` or `platform`, the agent generates the caption using only available fields and omits the missing detail rather than failing entirely. If the Claude API call fails, the agent returns the listing details and outfit suggestion without the fit card, and appends: "Fit card couldn't be generated this time — but your outfit suggestion is above."

---

### Additional Tools (if any)

None for the core milestone.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent runs a fixed sequential loop — not a free-form ReAct loop. The planning logic is:

1. **Parse user input.** Extract `description` (required), `size` (optional), and `max_price` (optional) from the user's message. These become the arguments for the first tool call.

2. **Call `search_listings(description, size, max_price)`.** Store the returned list in `session["search_results"]`.

3. **Check if results are empty.** If `len(session["search_results"]) == 0`: set `session["error"] = "no_results"`, assemble the no-results message (see Error Handling), and return to user — stop here, do not call any more tools.

4. **Select the top result.** If results are non-empty: set `session["selected_item"] = session["search_results"][0]` (the highest-relevance listing).

5. **Call `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`.** Store the returned string in `session["outfit_suggestion"]`.

6. **Check if suggestion is empty.** If `session["outfit_suggestion"]` is an empty string or None: set `session["error"] = "outfit_failed"`, return listing details + fallback message, stop here.

7. **Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.** Store the returned string in `session["fit_card"]`.

8. **Assemble and return final response.** Build the output string from: (a) listing summary (title, price, platform, condition, size), (b) outfit suggestion, (c) fit card caption. Return to user — the agent is done.

The agent knows it's done when it either hits an error-exit in step 3 or 6, or completes step 8. It never loops back to re-call a tool within a single user turn.

---

## State Management

**How does information from one tool get passed to the next?**

All state is stored in a `session` dict that is initialized at the start of each user turn and passed through the planning loop. The session holds:

- `session["wardrobe"]` (dict): Loaded once at startup (via `get_example_wardrobe()` for the demo, or passed in by the user if they provide their own). Persists across tool calls within a turn. Passed directly to `suggest_outfit` as the `wardrobe` argument.
- `session["search_results"]` (list[dict]): Set after `search_listings` returns. Used to check for empty results and to select the top item.
- `session["selected_item"]` (dict | None): Set to `session["search_results"][0]` after a successful search. Passed to both `suggest_outfit` (as `new_item`) and `create_fit_card` (as `new_item`).
- `session["outfit_suggestion"]` (str | None): Set after `suggest_outfit` returns. Passed to `create_fit_card` as the `outfit` argument.
- `session["fit_card"]` (str | None): Set after `create_fit_card` returns. Used in the final assembled response.
- `session["error"]` (str | None): Set to a short error code (`"no_results"`, `"outfit_failed"`) if an early-exit condition is triggered. The planning loop checks this before each tool call.

No tool receives the raw `session` dict — each tool only receives the specific fields it needs. State is not persisted across separate user turns (each new query starts a fresh session).

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query (returns `[]`) | "I couldn't find any [description] matching your filters. Try broadening your search — remove the size filter, raise your price limit, or use different keywords like 'band tee' instead of 'graphic tee'." Agent stops here; does not call suggest_outfit or create_fit_card. |
| suggest_outfit | Wardrobe is empty (`items` list is `[]`) | Agent still calls suggest_outfit but the prompt tells Claude to give general styling advice without referencing specific wardrobe pieces. Returns a generic "build this look from scratch" suggestion rather than failing. |
| create_fit_card | Outfit input is missing or incomplete | If `outfit` is empty/None, agent generates caption from `new_item` fields only. If `new_item` is missing `price` or `platform`, those details are omitted from the caption. No hard failure — always returns something. |

---

## Architecture

```
User query (description, size, max_price, wardrobe)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Planning Loop                          │
│                                                             │
│  1. Parse user input → description, size, max_price         │
│                                                             │
│  2. call search_listings(description, size, max_price)      │
│         │                                                   │
│         ├─ results == []                                    │
│         │       │                                           │
│         │       ▼                                           │
│         │  session["error"] = "no_results"                  │
│         │  return: "No listings found — try [suggestions]"  │ ◄── EARLY EXIT
│         │                                                   │
│         └─ results = [item, ...]                            │
│                 │                                           │
│                 ▼                                           │
│         session["selected_item"] = results[0]              │
│         session["search_results"] = results                 │
│                 │                                           │
│  3. call suggest_outfit(selected_item, wardrobe)            │
│         │                                                   │
│         ├─ wardrobe.items == []                             │
│         │       │                                           │
│         │       ▼                                           │
│         │  Claude generates generic styling advice          │
│         │  (no wardrobe references)                         │
│         │       │                                           │
│         ├─ API error / empty string                         │
│         │       │                                           │
│         │       ▼                                           │
│         │  session["error"] = "outfit_failed"               │
│         │  return: listing details + fallback message       │ ◄── EARLY EXIT
│         │                                                   │
│         └─ suggestion = "Pair this with..."                 │
│                 │                                           │
│                 ▼                                           │
│         session["outfit_suggestion"] = suggestion           │
│                 │                                           │
│  4. call create_fit_card(outfit_suggestion, selected_item)  │
│                 │                                           │
│                 ▼                                           │
│         session["fit_card"] = caption string                │
│                 │                                           │
│  5. Assemble final response:                                │
│     - Listing: title, $price, platform, condition, size     │
│     - Outfit suggestion                                     │
│     - Fit card caption                                      │
│                 │                                           │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
          Response to user


Session State (dict, initialized per turn):
┌──────────────────────────────────────────┐
│ wardrobe          ← loaded at startup    │
│ search_results    ← set after step 2     │
│ selected_item     ← set after step 2     │
│ outfit_suggestion ← set after step 3     │
│ fit_card          ← set after step 4     │
│ error             ← set on early exit    │
└──────────────────────────────────────────┘
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

**search_listings:**
Give Claude the Tool 1 spec block from planning.md (inputs with types, return value field list, empty-results failure mode) plus the `load_listings()` function signature from `utils/data_loader.py`. Ask it to implement `search_listings(description, size=None, max_price=None)` that: calls `load_listings()`, tokenizes the query description into lowercase keywords, scores each listing by counting keyword hits across `title`, `description`, and `style_tags`, filters by size (substring match) and max_price before scoring, and returns the top 5 by score as a list of full listing dicts (returns `[]` on no matches).
Verify before using: confirm the function filters on all 3 parameters; test with 3 queries: `"graphic tee"` (should return lst_006, lst_033), `"denim jacket size S"` (should return lst_007), `"shoes under $30"` (should return lst_035). Check that an impossible query like `"neon jumpsuit"` returns `[]`.

**suggest_outfit:**
Give Claude the Tool 2 spec block (inputs, return value, empty-wardrobe failure mode) plus the wardrobe schema from `data/wardrobe_schema.json`. Ask it to implement `suggest_outfit(new_item, wardrobe)` that: builds a Claude API prompt including the new item's title/category/colors/style_tags and a formatted list of wardrobe items (name, category, colors, style_tags, notes); if wardrobe is empty, uses a modified prompt asking for general styling advice; calls the Claude API and returns the text response as a string.
Verify: run with lst_006 + example_wardrobe and check the response references at least one wardrobe item by name. Run with lst_006 + empty wardrobe and check a non-empty string is returned. Check the response is 2–4 sentences.

**create_fit_card:**
Give Claude the Tool 3 spec block (inputs, return value, missing-data fallback). Ask it to implement `create_fit_card(outfit, new_item)` that: builds a Claude API prompt asking for a 1–2 sentence casual social caption in lowercase thrift-culture voice, including the platform name, price, and a nod to the outfit; handles missing `price` or `platform` by omitting them from the prompt; calls the Claude API and returns the caption string.
Verify: run with lst_006 suggestion and check the output mentions "depop" and "$24"; check it is 1–2 sentences; check it ends with 1–2 emoji; run with a `new_item` missing `price` and confirm it still returns a string.

**Milestone 4 — Planning loop and state management:**
Give Claude the Architecture diagram (the full ASCII diagram from this file) plus the Planning Loop section and State Management section. Ask it to implement `run_agent(user_query, wardrobe)` that: initializes the session dict with the wardrobe and None values for all other fields; parses `user_query` to extract description/size/max_price (using a Claude API call or regex); calls `search_listings`, checks for empty results and returns early if so; sets `selected_item = results[0]`; calls `suggest_outfit`, checks for empty string and returns early if so; calls `create_fit_card`; assembles the final multi-part response string.
Verify: run the full example query "I'm looking for a vintage graphic tee under $30, size M" and confirm: (1) `selected_item` is one of lst_006/lst_033, (2) an impossible query like "neon jumpsuit size XXS under $5" exits after search with the no-results message, (3) the final output contains all three sections (listing, outfit, fit card).

---

## A Complete Interaction (Step by Step)

FitFindr is a thrift-shopping assistant that takes a user's search request and personal style, finds matching secondhand listings, then builds a complete outfit around the new find using the user's existing wardrobe. `search_listings` is triggered first by any user query describing an item to buy; if it returns results, `suggest_outfit` is called with the top listing and the user's wardrobe to generate styling advice; `create_fit_card` is called last to produce a shareable social caption. If `search_listings` returns nothing, FitFindr tells the user to adjust their criteria and stops — it never calls the downstream tools with empty inputs.

---

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
Agent calls `search_listings("vintage graphic tee", max_price=30.0)`. The tool scans all listings, matching on title, description, and style_tags. Three results come back sorted by relevance:
1. lst_006 — "Graphic Tee — 2003 Tour Bootleg Style", $24, size L, tags: `["graphic tee", "vintage", "grunge", "streetwear", "band tee"]`
2. lst_033 — "Vintage Band Tee — Faded Grey", $19, size L, tags: `["vintage", "grunge", "band tee", "graphic tee", "streetwear"]`
3. lst_002 — "Y2K Baby Tee — Butterfly Print", $18, size S/M, tags: `["y2k", "vintage", "graphic tee"]`

The agent picks the top result: lst_006. Sets `session["selected_item"] = lst_006`.

**Step 2:**
Agent calls `suggest_outfit(new_item=lst_006, wardrobe=get_example_wardrobe())`. The example wardrobe contains baggy dark-wash jeans (w_001) and chunky white sneakers (w_007) — matching the user's described style. The tool returns: "Wear the boxy bootleg tee untucked over your baggy dark-wash straight-legs — the oversized fit plays well with the wide leg. Finish with your chunky white sneakers and black crossbody to keep it clean. Roll the sleeves once to break the silhouette."

Sets `session["outfit_suggestion"]` to that string.

**Step 3:**
Agent calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=lst_006)`. Returns: "thrifted this faded bootleg tee off depop for $24 and it was made for my baggy jeans 🖤 chunky sneakers doing all the heavy lifting, whole fit under $30"

Sets `session["fit_card"]` to that string.

**Error path:**
If `search_listings` returns zero results, the agent responds: "No vintage graphic tees under $30 right now — try searching 'band tee' or 'graphic top', or bump your budget a few dollars. Dropping the size filter can also open up more results." No further tools are called.

**Final output to user:**
The user sees: the top matching listing (title, price, platform, condition), the outfit suggestion describing exactly how to style it with their existing pieces, and the ready-to-post fit card caption.
