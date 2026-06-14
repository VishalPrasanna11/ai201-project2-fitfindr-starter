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
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): ...
- `size` (str): ...
- `max_price` (float): ...

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): ...
- `wardrobe` (dict): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (...): ...

**What it returns:**
<!-- Describe the return value -->

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | |
| suggest_outfit | Wardrobe is empty | |
| create_fit_card | Outfit input is missing or incomplete | |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Milestone 4 — Planning loop and state management:**

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

The agent picks the top result: lst_006.

**Step 2:**
Agent calls `suggest_outfit(new_item=lst_006, wardrobe=get_example_wardrobe())`. The example wardrobe contains baggy dark-wash jeans (w_001) and chunky white sneakers (w_007) — matching the user's described style. The tool returns: "Wear the boxy bootleg tee untucked over your baggy dark-wash jeans — the oversized fit plays well with the wide leg. Finish with your chunky white sneakers and black crossbody to keep it clean. Roll the sleeves once to break the silhouette."

**Step 3:**
Agent calls `create_fit_card(outfit=<suggestion above>, new_item=lst_006)`. Returns: "thrifted this faded bootleg tee off depop for $24 and it was made for my baggy jeans 🖤 chunky sneakers doing all the heavy lifting, whole fit under $30"

**Error path:**
If `search_listings` returns zero results, the agent responds: "No vintage graphic tees under $30 right now — try searching 'band tee' or 'graphic top', or bump your budget a few dollars. Dropping the size filter can also open up more results." No further tools are called.

**Final output to user:**
The user sees: the top matching listing (title, price, platform, condition), the outfit suggestion describing exactly how to style it with their existing pieces, and the ready-to-post fit card caption.
