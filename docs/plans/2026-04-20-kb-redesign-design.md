# Knowledge Base Redesign — Design Document

**Date:** 2026-04-20
**Status:** Approved, ready for implementation plan
**Author:** Soaham + Claude

## Context

The Capacity Chatbot's current knowledge base lives in `capacity_chatbot/knowledge/knowledge_store.py` as a 1,142-line Python module containing 59 Q&A entries, a keyword-scoring algorithm, synonym expansion, and phrase-match heuristics. The agent accesses it through a `get_knowledge_answer` tool that runs multi-factor scoring and returns the top 3 matches.

Analysis of 346 Zendesk Scheduler tickets (documented in `docs/chatbot-deflection-analysis.html`) showed:

- The KB can deflect ~31% of tickets in its current form
- Gaps exist around appointment dashboard UX, reminders, authority/permissions, and myKaarma-only dealer setup options (DSOs)
- Users fall into three operational tiers: base dealership users, managers with settings-tab access, and myKaarma-internal support staff
- Different tiers need different answers to the same question (e.g., "enable Appointments tab" for a base user → "ask your manager"; for a manager → actual steps; for internal → backend DSO option key)

We measured the current KB at **~9k tokens** (Claude tokenizer). Projected scale even after expansion to ~150-250 entries is under 40k tokens — comfortably within Claude Sonnet 4.5's 200k context window.

## Goals

1. **Replace retrieval with long-context injection.** Drop the scoring algorithm; include the tier-filtered KB directly in the system prompt. Simpler code, better accuracy, cheap with prompt caching.
2. **Enable three-tier content gating** so base users don't see internal-only instructions and internal staff see full DSO context.
3. **Decouple content from code.** Move KB to per-topic JSON files so content changes don't require Python edits or code review.
4. **Preserve all existing content** during migration. Zero regressions.

Non-goals:
- Vector search, embeddings, or RAG (overengineered at this scale)
- Hot-reload of KB without restart (deploys are cheap enough)
- Auto-generating KB from the production DB (out of scope; DB is a content-research tool only)

## Decisions

### 1. Long-context injection, not retrieval

The agent no longer calls a knowledge tool. The tier-filtered KB is rendered directly into the system prompt on every request. Anthropic prompt caching (5-minute ephemeral) amortizes cost across all users on the same tier — cache hit rate approaches 100% during active periods.

Removed:
- `tools/knowledge.py` — the `get_knowledge_answer` tool
- `tools/__init__.py` — `KNOWLEDGE_TOOLS` export
- `knowledge/knowledge_store.py` — COMMON_QUESTIONS, SYNONYMS, HOW_TO_PHRASES, all `_calculate_*_score()` helpers, `_expand_query_with_synonyms()`, `_is_how_to_query()`, `get_relevant_knowledge()`, scoring constants
- References to `get_knowledge_answer` in `prompts.py`

### 2. Storage: per-topic JSON files

```
capacity_chatbot/knowledge/
├── kb/
│   ├── capacity.json
│   ├── assignment.json
│   ├── schedule.json
│   ├── transport.json
│   ├── holiday.json
│   ├── online-scheduler.json
│   ├── concept.json
│   ├── troubleshooting.json
│   ├── dashboard.json          # new
│   ├── communication.json      # new
│   ├── authority.json          # new
│   └── ui.json                 # new
├── loader.py
└── prompt_builder.py
```

One JSON file per topic. Each file is a plain JSON array of entries. Rationale: scoped code review, parallel editing without merge conflicts, clear ownership boundaries.

### 3. Entry schema (5 fields, all required)

```json
{
  "id": "authority.enable-appointments-tab",
  "question": "How do I enable the Appointments tab for a user?",
  "answer": "Go to Settings → Users → [user] → ...",
  "tier": "manager",
  "topic": "authority"
}
```

**No `keywords`, no `category`, no `priority_keywords`, no `last_updated`.** The model handles retrieval; we don't need pre-computed matching hints. Add metadata only when a concrete need surfaces.

**ID convention:** `<topic>.<slug>` where topic is singular kebab-case and slug is kebab-case derived from the question. Must be unique across the whole KB.

**Topics** (free-form strings for grouping and analytics, not used in retrieval): `capacity`, `assignment`, `schedule`, `transport`, `holiday`, `online-scheduler`, `concept`, `troubleshooting`, `dashboard`, `communication`, `authority`, `ui`.

### 4. Tier model: hierarchical

```python
TIER_VISIBILITY = {
    "base":     {"base"},
    "manager":  {"base", "manager"},
    "internal": {"base", "manager", "internal"},
}
```

A user on tier X sees all entries tagged with a tier in `TIER_VISIBILITY[X]`. Higher tiers see everything from lower tiers.

Tier semantics:
- **base** — any dealership user. Pure how-to and conceptual content.
- **manager** — settings-tab holders. Adds configuration-change guidance (rules, schedules, transport).
- **internal** — myKaarma staff. Adds DSO option keys, permission-grant flows, backend triage.

### 5. Tier source: explicit in API request

The API request body gains a `user_tier` field. The frontend computes the tier from the authenticated user's session and sends it:

```python
class RunRequest(BaseModel):
    messages: list[Message]
    department_uuid: str
    dealer_uuid: str | None = None
    user_tier: Literal["base", "manager", "internal"] = "base"
```

Missing field → default to `"base"` (least-privilege fail-safe). Unknown value → Pydantic rejects with 422.

**Frontend tier computation** (in `appointment-ui-client`):

```typescript
const MANAGER_AUTHORITIES = [
  Authority.APPOINTMENTS_DEALERAPP_RULES_WRITE,              // "appointments.dealerapp.rules.write"
  Authority.APPOINTMENTS_DEALERAPP_USER_APPT_EDIT_ACCESS,    // "appointments.dealerapp.userappteditaccess"
  Authority.APPOINTMENTS_CAPACITYPLANNING_LIMITS_OVERRIDE,   // "appointments.capacityplanning.limits.override.enable"
  Authority.APPOINTMENTS_OPCODES_MENUS_LIMITS_OVERRIDE,      // "appointments.opcodes.menus.limits.override.enable"
  Authority.APPOINTMENTS_TRANSPORT_FULL_ALLOW,               // "appointments.transport.override.allow"
];

function computeUserTier(mkSession): "base" | "manager" | "internal" {
  if (mkSession.user.email?.endsWith("@mykaarma.com")) return "internal";
  const userAuths = new Set(mkSession.authorities.map(a => a.authority));
  if (MANAGER_AUTHORITIES.some(a => userAuths.has(a))) return "manager";
  return "base";
}
```

**Authority shortlist derivation:** The shortlist was chosen from scheduler authorities with `InSelfAdmin=1` in the `Authority` table (21 candidates) — filtered to the ones that imply configuration power (write, edit, override). Read-only authorities do not promote tier.

### 6. Database as content-research tool only

The chatbot runtime never reads from the Aurora DB for KB content. However, while writing KB entries, we use the DB as a reference:

- `Authority` table — contains `InSelfAdmin` and `IsMyKaarmaAdmin` flags that define tier membership for each authority. When we write an entry that references an authority, we use its real `Description` from this table.
- `OptionKeyPrompt` table — contains `VisibleInSelfAdmin` and `VisibleInAdminTool` flags and authoritative `OptionDescription`, `PossibleValues`, `DefaultValue` for every DSO. When a KB entry needs to explain a DSO (mostly internal-tier content), we use the canonical description from this table.

A helper script, `scripts/lookup_dsos.py`, is an exploration CLI for content authors. It queries the DB (read-only), filters by topic keyword, and prints DSO/authority metadata. Not runtime code, not deployed — just a tool.

### 7. KB injection and caching

The agent node assembles system messages as a list of blocks:

```python
from capacity_chatbot.knowledge.prompt_builder import build_system_messages

async def capacity_agent(state: CapacityChatbotState, config: RunnableConfig):
    system_messages = build_system_messages(state["user_tier"])
    llm = get_llm().bind_tools(CAPACITY_TOOLS)
    response = await llm.ainvoke(
        [SystemMessage(content=system_messages)] + state["messages"],
        config=config,
    )
    return {"messages": [response]}


# prompt_builder.py
def build_system_messages(tier: str) -> list[dict]:
    return [
        {"type": "text", "text": BEHAVIORAL_PROMPT},
        {
            "type": "text",
            "text": format_kb_for_tier(tier),
            "cache_control": {"type": "ephemeral"},
        },
    ]
```

Two separate blocks so behavioral-prompt tweaks don't bust the KB cache and vice versa. Entries are rendered in sorted-by-id order for deterministic prompt bytes (cache key stability).

**Rendered format (per entry):**

```
## authority.enable-appointments-tab
**Q:** How do I enable the Appointments tab for a user?
**A:** Go to Settings → Users → [user] → ...
```

The `id` stays in the rendered output so the model can cite entries and so we can trace responses in logs.

### 8. Loader contract and validation

```python
def load_kb() -> list[Entry]:
    entries = []
    for path in sorted(Path("capacity_chatbot/knowledge/kb").glob("*.json")):
        entries.extend(json.loads(path.read_text()))
    _validate(entries)
    return entries
```

Load once at module init. Validation enforces:
- All 5 fields present
- `tier` in `{"base", "manager", "internal"}`
- `id` matches pattern `^[a-z0-9-]+\.[a-z0-9-]+$`
- `id` unique across all files
- `question` and `answer` non-empty

Startup fails loudly on invalid content.

## Migration

A script, `scripts/migrate_kb_to_json.py`, reads the current `knowledge_store.py:COMMON_QUESTIONS` and produces per-topic JSON files:

- Preserves `question` and `answer` verbatim
- Maps `category` → `topic` (with keyword inference when category is generic like `how-to`)
- Generates `id` as `<topic>.<kebab-slugified-question>`; adds numeric suffix on collision
- Hardcodes `tier = "base"` for all 59 existing entries
- Drops `keywords` entirely
- Groups output by topic, writes one file per topic
- Idempotent: re-runnable, overwrites target directory only if validation passes

After migration, the 59 entries are the new baseline. New content is additive.

## Token / cost analysis

| KB size | Tokens | % of 200k context | Cache write (one-time) | Cache read per request |
|---|---|---|---|---|
| Today (59 entries) | ~9k | 4.5% | ~$0.034 | ~$0.003 |
| After expansion (~150 entries) | ~22k | 11% | ~$0.083 | ~$0.007 |
| Hypothetical ceiling (250 entries) | ~37k | 19% | ~$0.14 | ~$0.011 |

The KB prefix is identical across users on the same tier, so cache hit rate approaches 100% during active periods. Every request on a given tier resets the 5-minute TTL. Steady-state cost is essentially zero.

## Testing

**1. Load-time validation test** — `test_kb_loads.py` calls `load_kb()` and asserts no exception. Catches malformed JSON, schema drift, duplicate IDs. Runs in CI on every commit that touches `knowledge/`.

**2. Tier filtering unit tests** — `test_prompt_builder.py`:
- `format_kb_for_tier("base")` includes only `tier=base` entries
- `format_kb_for_tier("manager")` includes `base` + `manager`
- `format_kb_for_tier("internal")` includes all three
- Output is sorted by `id` (regression test for cache stability)
- Unknown tier raises `ValueError`

**3. End-to-end golden tests** — A small fixture of `(tier, question, expected_kb_id)` tuples. Runs a real LLM call; asserts the expected entry ID appears in the response. ~10 cases total. Catches content reorganization regressions.

We do not test exact wording of model answers or content quality — those are human-reviewed at content-writing time.

## Rollout

**Phase 1 — Infrastructure (day 1)**
1. Add `knowledge/kb/` directory, `loader.py`, `prompt_builder.py`
2. Run migration script → 59 entries in per-topic JSON files, all `tier="base"`
3. Add `user_tier` to API request model + `InputState`
4. Rewire agent node to call `build_system_messages()`
5. Delete `get_knowledge_answer` tool and all scoring code
6. Update `prompts.py` to reference the injected KB instead of the tool
7. All three test layers pass

At end of Phase 1, behavior is functionally identical to today for every user — everyone defaults to `base` tier, all content is `base`. Safe to ship.

**Phase 2 — Content expansion (weeks 2–4)**
Write content for the four gap areas, ordered by ticket volume:
1. `authority.json` — ~15 entries spanning tiers (low effort, high value for the tier story)
2. `dashboard.json` — ~30-40 entries (biggest ticket volume)
3. `communication.json` — ~15-20 entries (templates, reminders)
4. `ui.json` — ~10 entries (view/print customization)

Each topic is one PR. Content PRs don't touch code — only JSON. Use `scripts/lookup_dsos.py` to source canonical DSO/authority descriptions when entries need to reference them.

**Phase 3 — Tier activation (week 4+)**
Frontend ships the `computeUserTier()` helper and starts sending `user_tier` in every chatbot request. Monitor deflection metrics per tier. Iterate on content based on what the chatbot actually answers wrong.

## Rollback

- **Phase 1**: The risky moment is deleting the `get_knowledge_answer` tool. If something breaks, revert the PR. Migration is idempotent — rerunning the script produces the same JSON.
- **Phase 2**: Content PRs are reversible by deleting files or entries. No schema changes.
- **Phase 3**: Frontend can revert to always sending `"base"`; backend still works.

## Observability

- Log `user_tier` and rendered KB token estimate on each request (one line in the agent node)
- No per-entry access tracking in Phase 1. If needed later, add a `kb_entries_referenced` field to response metadata.

## Open questions / deferred decisions

- **Entry analytics.** Should we track which entries are most referenced to prioritize content improvements? Deferred — add if deflection metrics plateau.
- **Hot-reload.** Currently KB is loaded at module init. If content-edit velocity becomes high, consider watching the kb/ directory. Deferred — deploys are cheap.
- **Per-user content personalization.** Beyond tier, could we personalize by dealer features/products? Deferred — YAGNI until a concrete need.

## Appendix: Topic ownership (proposed)

| Topic file | Primary owner | Notes |
|---|---|---|
| `capacity.json` | Product | Capacity rules logic |
| `assignment.json` | Product | Assignment rules logic |
| `schedule.json` | Support | Day-to-day schedule management |
| `transport.json` | Product | Transport options config |
| `holiday.json` | Support | Date-blocking patterns |
| `online-scheduler.json` | Product | Online scheduler config |
| `concept.json` | Product | Definitions |
| `troubleshooting.json` | Support | Why-not-working guides |
| `dashboard.json` | Support | Appointment Dashboard UX |
| `communication.json` | Product | Reminder/notification flows |
| `authority.json` | Support | Permission-grant workflows |
| `ui.json` | Support | View/print customization |
