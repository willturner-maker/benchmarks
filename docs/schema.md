# Leaderboard results.json schema

Machine-readable source of truth for standings. Human view is
[`docs/leaderboard.md`](leaderboard.md). Schema version is the top-level `"schema"` integer.

## Top-level keys

| Key | Meaning |
|-----|---------|
| `schema` | Integer schema version (currently 1). |
| `updated` | Free-text note of the last change. |
| `read_this_first` | Array of short rules that must be understood before comparing rows. |
| `host_reference` | The fixed reference host used for all published class-A / Splash rows. |
| `suites` | Object containing the four suite arrays (see below). |
| `withdrawn` | Optional array of rows that were published then removed (with reason). |

## Suite arrays

- `suites.resolve_mcp` — Resolve MCP rows (class A unless noted).
- `suites.splash_engine` — Splash engine rows (width-ladder + agentic summary).
- `suites.visual_venv` — OpenCV / visual venv rows.
- `suites.community_runs` — rows from other hosts/media classes that accompany the reference tables (reserved; no rows yet).

Each row is an object. Common fields:

- `date` — ISO date or wave label.
- `media_class` — `"A"` or `"B"` (Resolve only).
- Timing and outcome fields specific to the suite (see existing rows for the exact keys used).

## Comparability rules (enforced by convention)

1. Only compare rows that share the same `media_class` and the same tenant conditions.
2. Render milliseconds are single-tenant unless explicitly footnoted.
3. Every numeric value must come from an independent read-back, never from an agent self-report.

When adding a community row, prefer the issue form; if you generate JSON directly, keep the same field names and include a clear note for any deviation.
