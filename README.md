# FitFindr

A thrift-shopping assistant that finds secondhand clothing listings and builds complete outfits around them. Give it a description of what you're looking for (with optional size and price filters), and it returns the top matching listing, a specific outfit suggestion using your wardrobe, and a ready-to-post social caption.

---

## Setup

```bash
pip install -r requirements.txt
```

Add your Groq API key to a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

## Running the App

```bash
python app.py
```

Open the URL shown in your terminal (usually `http://localhost:7860`).

## Running Tests

```bash
pytest tests/
```

---

## Tool Inventory

### `search_listings(description, size=None, max_price=None)`

Searches the 40-listing mock dataset for items matching the user's description, optional size, and optional price ceiling.

| Parameter | Type | Meaning |
|---|---|---|
| `description` | `str` | Keywords to search for (e.g. `"vintage graphic tee"`). Matched against each listing's `title`, `description`, and `style_tags` fields. |
| `size` | `str \| None` | Size string to filter by. Case-insensitive substring match — `"M"` matches `"S/M"`, `"M/L"`, `"XL (fits oversized M)"`. |
| `max_price` | `float \| None` | Upper price bound, inclusive. Listings with `price > max_price` are excluded. |

**Returns:** A list of up to 5 listing dicts sorted by relevance score (keyword hit count), or `[]` if nothing matches. Each dict contains all original listing fields: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`.

**Purpose:** Filters and ranks the dataset so the planning loop has a specific, relevant item to work with.

---

### `suggest_outfit(new_item, wardrobe)`

Calls the Groq LLM (`llama-3.3-70b-versatile`) to suggest a complete outfit combining the new item with pieces from the user's wardrobe.

| Parameter | Type | Meaning |
|---|---|---|
| `new_item` | `dict` | A listing dict from `search_listings` — used for title, category, colors, style_tags, price, platform. |
| `wardrobe` | `dict` | A wardrobe object with an `"items"` key containing a list of wardrobe item dicts (each has `name`, `category`, `colors`, `style_tags`, `notes`). May be empty. |

**Returns:** A non-empty string with a 2–4 sentence outfit suggestion. When the wardrobe has items, the LLM references them by name and includes a specific styling tip. When the wardrobe is empty, it returns general styling advice for the item without crashing.

**Purpose:** Gives the user concrete, personalized styling advice — not just "this item exists."

---

### `create_fit_card(outfit, new_item)`

Calls the Groq LLM at temperature 1.1 to generate a casual, first-person social media caption.

| Parameter | Type | Meaning |
|---|---|---|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit`. |
| `new_item` | `dict` | The listing dict — used for `title`, `price`, and `platform` in the caption. |

**Returns:** A 1–2 sentence caption in lowercase thrift-culture voice with 1–2 emoji, ready to paste into Instagram or TikTok. If `outfit` is empty or whitespace, returns a descriptive error message string without calling the LLM.

**Purpose:** Turns the outfit suggestion into a shareable artifact — the final deliverable the user actually posts.

---

## How the Planning Loop Works

The agent runs a fixed sequential loop — not a free-form ReAct loop. Every query follows the same structure, but the agent branches based on what each tool returns.

**Step 1 — Parse.** `_parse_query()` uses regex to extract a `description`, optional `size`, and optional `max_price` from the user's free-text query. This is deterministic and requires no LLM call.

```
"90s track jacket size M under $50"
→ description="90s track jacket", size="m", max_price=50.0
```

**Step 2 — Search, with early exit.** `search_listings()` is called with the parsed parameters. If it returns an empty list, the agent immediately sets `session["error"]` with a specific message explaining what filters were applied and what the user can try differently. It returns the session right here — `suggest_outfit` and `create_fit_card` are never called.

**Step 3 — Select.** If results are non-empty, `session["selected_item"]` is set to `results[0]` (the highest-relevance listing). This exact dict object is what gets passed to both downstream tools.

**Step 4 — Style.** `suggest_outfit()` receives `session["selected_item"]` and `session["wardrobe"]`. Its string output is stored in `session["outfit_suggestion"]`.

**Step 5 — Caption.** `create_fit_card()` receives `session["outfit_suggestion"]` and `session["selected_item"]`. Its output is stored in `session["fit_card"]`.

**Step 6 — Return.** The completed session dict is returned. The caller checks `session["error"]` first, then reads `selected_item`, `outfit_suggestion`, and `fit_card`.

The agent knows it is done when it either hits the early exit at step 2 or completes step 5. It never loops back or re-calls a tool within a single query.

---

## State Management

All state lives in a single `session` dict, initialized at the start of each query and returned at the end. Nothing is stored between queries — each run is independent.

| Key | Type | When set | How used |
|---|---|---|---|
| `query` | `str` | On init | Preserved for logging/debugging |
| `parsed` | `dict` | After step 1 | Contains `description`, `size`, `max_price` — passed to `search_listings` |
| `search_results` | `list[dict]` | After step 2 | Checked for emptiness; `[0]` becomes `selected_item` |
| `selected_item` | `dict \| None` | After step 3 | Passed to `suggest_outfit` (as `new_item`) and `create_fit_card` (as `new_item`) |
| `wardrobe` | `dict` | On init | Passed to `suggest_outfit` unchanged |
| `outfit_suggestion` | `str \| None` | After step 4 | Passed to `create_fit_card` as `outfit` |
| `fit_card` | `str \| None` | After step 5 | Surfaced to user in the fit card panel |
| `error` | `str \| None` | On early exit | If set, signals the interaction ended early; downstream fields stay `None` |

No tool receives the raw session dict — each receives only the specific keys it needs, passed as named arguments.

---

## Error Handling

### `search_listings` — no results

**Failure mode:** Query is too specific, price cap too low, or keywords don't match any listing.

**Agent response:** Sets `session["error"]` and returns immediately. Example from testing:

```
query: "designer ballgown size XXS under $5"

error: No listings found for "designer ballgown size XXS" matching under $5.
Try broadening your search — remove the size filter, raise your price limit,
or use different keywords (e.g. 'band tee' instead of 'graphic tee').

fit_card: None
outfit_suggestion: None
```

`suggest_outfit` and `create_fit_card` are not called. The user gets a specific explanation of which filters were applied and three concrete things to try.

---

### `suggest_outfit` — empty wardrobe

**Failure mode:** User has no wardrobe items (`wardrobe["items"] == []`).

**Agent response:** Still calls the LLM, but with a modified prompt asking for general styling advice instead of wardrobe-specific outfit building. Returns a non-empty, useful string rather than crashing. Example:

```python
suggest_outfit(results[0], get_empty_wardrobe())
# → "This Y2K-inspired butterfly print tee would pair well with high-waisted jeans,
#    flowy skirts, or distressed denim shorts for a nostalgic and playful look. It
#    suits a vintage or cottagecore aesthetic. Try layering a denim jacket over the
#    tee to add depth while still showcasing the butterfly print."
```

---

### `create_fit_card` — empty outfit string

**Failure mode:** `outfit` argument is empty or whitespace (e.g., `suggest_outfit` was skipped or failed silently).

**Agent response:** Returns a descriptive error string immediately — no LLM call. Example:

```python
create_fit_card("", results[0])
# → "Error: no outfit suggestion provided — call suggest_outfit first
#    before generating a fit card."
```

---

## AI Usage

### search_listings implementation

I gave Claude the Tool 1 spec block from `planning.md` (inputs with types, return value field list, empty-results failure mode) and the `load_listings()` function signature from `utils/data_loader.py`. I asked it to implement `search_listings()` with keyword scoring across title, description, and style_tags.

The generated code scored by checking if any keyword appeared anywhere in the combined text — giving every matching listing the same binary score (matched or not). I changed this to count each keyword hit individually so results with more keyword overlap rank higher. I also added the `[:5]` cap which was missing from the generated version.

### suggest_outfit prompt design

I gave Claude the Tool 2 spec block and the wardrobe schema from `data/wardrobe_schema.json`. I asked it to implement `suggest_outfit()` with two prompt branches (populated wardrobe vs. empty wardrobe).

The generated prompt was generic — "suggest an outfit using these clothes." I rewrote it to explicitly instruct the LLM to reference wardrobe items by their `name` field, include at least one specific styling tip (tucking, rolling sleeves, layering), and limit the response to 2–4 sentences. I also adjusted temperature: 0.7 for outfit suggestions (consistent, actionable advice) and 1.1 for `create_fit_card` (caption variety).

---

## Project Structure

```
fitfindr/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   └── test_tools.py          # 13 pytest tests covering all tools and failure modes
├── tools.py                   # search_listings, suggest_outfit, create_fit_card
├── agent.py                   # run_agent() — planning loop and state management
├── app.py                     # Gradio interface
├── planning.md                # Design spec, agent diagram, AI tool plan
└── .env                       # GROQ_API_KEY (not committed)
```
