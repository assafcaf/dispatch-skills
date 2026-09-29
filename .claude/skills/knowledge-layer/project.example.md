<!-- A worked example of .claude/workflow/project.md, for a fictional order-management
     service. Shows the shape and the level of detail. Not installed into a project:
     /knowledge-layer writes the real one from a scan plus the operator's answers. -->

# Acme Orders: working notes

Mode: on   ·   Last scanned: 2026-09-18

## What this repo is

The order lifecycle for Acme's storefront: intake, state transitions, and the events other
services consume. It owns no payment logic and no stock levels; Billing and Inventory own
those and are reached only through events.

## Module map

| Path | Owns |
|---|---|
| `src/ordering/` | Intake and the state machine from submitted to fulfilled or cancelled |
| `src/ordering/events/` | The published event contracts. Changing one is a breaking change |
| `src/projections/` | Read models rebuilt from the event log. Never written to directly |
| `src/adapters/` | One module per external service. The only place HTTP clients live |
| `tests/contract/` | Consumer-driven contract tests. Run against recorded fixtures, not live |

## Commands

Gates are in `config.md`'s Commands table. Only what that table cannot express:

- `tests/contract/` needs recorded fixtures: `make fixtures` once per checkout, and again
  after any change under `src/ordering/events/`.
- The full suite takes about 4 minutes; `-m "not contract"` cuts it to 40 seconds while
  iterating.

## Invariants

- **Every state change goes through `Order.transition()`.** Direct assignment to `status`
  skips the event emission, so the projections silently drift and nothing fails until a
  read model is rebuilt days later.
- **An event contract is append-only.** Adding a field is fine; renaming or removing one
  breaks consumers that are deployed independently and cannot be migrated with us.
- **No adapter is called inside a transaction.** A slow partner API holds a row lock and the
  whole intake path queues behind it.

## Standing overlaps

Files most tasks touch. `/tickets` and `task-planner` check two tasks that both touch one for
a real conflict (both rewriting the same code); separate additions merge on their own.

| Path | Recent commits touching it |
|---|---|
| `src/ordering/state_machine.py` | 22 of the last 60 |
| `db/migrations/` | 17 of the last 60 |
| `src/ordering/events/schema.json` | 11 of the last 60 |

## Pitfalls

- **The dev server caches the event schema at boot.** A schema change needs a restart, not a
  reload, and the symptom is a validation error naming a field you just added.
- **`make fixtures` is not idempotent across branches.** Switching branches without re-running
  it gives contract failures that look like real regressions.
- **Cancellation is not a state, it is a terminal transition.** New contributors add a
  `cancelled` branch to filters and get double-counting; the query helpers already exclude it.
