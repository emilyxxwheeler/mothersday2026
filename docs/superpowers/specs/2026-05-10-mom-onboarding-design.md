# Mom's Onboarding + Cross-Device Persistence — Design

**Date:** 2026-05-10 (Mother's Day)
**Author:** Emily, with Claude
**Status:** Approved for phased build

## Goal

Onboard Jane (Emily's mom) onto her NYC restaurant guide with a one-time Beli-style ranking session that captures accurate 1.0–10.0 scores for every restaurant she's already visited. After onboarding, she uses the platform normally — adding new restaurants, refining individual rankings, and exploring — with rankings persisted across all her devices.

## Constraints

- Mother's Day is today; Phase 1 must ship today
- Mom is the primary user; this is a Mother's Day gift
- ~101 visited restaurants currently bucketed as: 13 top-pick, 34 loved, 24 mixed, 30 disliked
- 248 wishlist (untouched by onboarding)
- Existing app is pure static HTML on Vercel (project `phoebegoeatly`), localStorage only

## Architecture

```
┌────────────────────┐         ┌──────────────────────────────┐
│  Vercel KV (new)   │         │  Static HTML + new overlays  │
│  Keys:             │ ◄─────► │  + remote-storage adapter    │
│   • jane:overrides │  HTTPS  │  + onboarding flow           │
│   • test:overrides │         │  + sort-by-score             │
└────────────────────┘         │  + reset/wipe                │
                               │  + Rerank section (Phase 2)  │
                               │  + Update Rankings (Phase 2) │
                               │  + view-only Share (Phase 2) │
                               └──────────────────────────────┘

API (no auth — per Emily's call):
  GET  /api/overrides?profile=jane    → returns saved JSON
  POST /api/overrides?profile=jane    → saves JSON body (last-write-wins)

Profile defaults to 'jane'. Test sandbox = ?profile=test.
```

## Data shape

Single payload per profile (additive to existing localStorage shape):

```json
{
  "added": [...],
  "modifications": { "5": { "score": 8.4, "status": "loved" }, ... },
  "deleted": [],
  "onboardingState": {
    "currentBucket": "loved",
    "bucketsCompleted": ["top-pick"],
    "placedIds": [45, 12, 88],
    "deferredIds": [99],
    "remainingIds": [3, 7, 14],
    "inProgressInsertion": {
      "restaurantId": 22,
      "rangeLow": 2,
      "rangeHigh": 6,
      "comparisonsRemaining": 2
    }
  },
  "onboardingCompleted": false,
  "schemaVersion": 1
}
```

## Onboarding algorithm

- **Buckets covered:** Top Pick → Loved → Mixed (excluding Disliked + Wishlist per Emily)
- **Order:** strongest-memory bucket first
- **Within bucket:** binary insertion sort, depth capped at 3 comparisons per restaurant
- **Skip:** swaps the comparison anchor (already-placed opponent) for a different one in the same range. After 3 consecutive skips on the same insertion → defer that restaurant to end of bucket queue
- **Comparison count:** ~175 average + ~20% from skips → ~210 total, ~12–15 min
- **No "tied" option** (Beli-style forces a pick); Mom can hit X to pause anytime
- **Status during onboarding:** locked to bucket (within-bucket sort only)

## Score derivation per bucket (post-onboarding positions)

| Bucket | Range |
|---|---|
| Top Pick | 8.5 – 10.0 |
| Loved | 7.0 – 8.4 |
| Mixed | 4.0 – 6.9 |
| Disliked | 1.0 – 3.9 (default 2.0; not refined in onboarding) |
| Wishlist | no score |

## Status fluidity (post-onboarding)

After onboarding, score is the source of truth. Rerank / Update Rankings can move scores across bucket thresholds, and **status auto-updates** to match. Toast surfaces the change: "Le Bernardin moved Loved → Top Pick ✨"

Comparison opponents in Rerank/Update Rankings are picked by score-proximity (not by status), enabling cross-bucket movement.

## Phased rollout

### Phase 1 (today)
1. Backend: `package.json` + `api/overrides.js` + Vercel KV provisioning (manual step in Vercel dashboard)
2. Client `window.storage` adapter pointing at the API; localStorage as offline cache
3. Sort-by-score option in the dropdown
4. Onboarding flow: welcome screen → binary insertion (3 buckets) → completion
5. Minimal "Wipe Everything" reset for Emily's testing

### Phase 2 (this week)
6. Per-restaurant Rerank: new "Ranking" section above Notes with score + Rerank button; continuous Elo-style flow
7. "Update Rankings" pill in sidebar under Distinctions
8. Full settings drawer (3 reset levels: restart onboarding / reset rankings / wipe everything)
9. View-only mode (`?view=only`) + Share button + copy-link popover
10. Polish: status-change toast, mobile QA

## UI notes

### Welcome screen copy
> "Hi Mom! I made you a guide of every NYC restaurant you've been to and want to try. Before we let you loose, let's capture your most accurate rankings — that way the map can sort everything by how much you actually liked it.
>
> We'll go through your top picks, loved, and mixed restaurants in 3 batches (~71 total). Takes about 12–15 minutes. You can skip any pair you don't remember, and pause anytime."

### Comparison modal (1v1)
- 2 cards side-by-side — pin color, name, "cuisine · neighborhood" per card
- Top-right **X** (closes; commits in-flight; in onboarding shows resume banner)
- "Skip — show me different ones" link

### Resume banner (when paused mid-onboarding)
> "↻ Resume onboarding · 47 of 71 ranked →"

### Sort dropdown — new option
`Sort: Score (highest first)` — descending; unrated/wishlist sort to bottom alphabetically.

## Test/wipe flow

- Emily opens `phoebegoeatly.vercel.app/?profile=test` to test
- Walks through onboarding (use a "Skip remaining" debug button visible only when profile != 'jane')
- When done: hits "Wipe Everything" in settings → POSTs empty payload to `test:overrides`
- Mom opens bare URL → fresh `jane:overrides` → onboarding triggers naturally

## Open trade-offs (acknowledged)

- **No auth on writes:** anyone with the URL can edit Mom's data. Acceptable per Emily; revisit if abuse occurs.
- **Last-write-wins:** simultaneous edits across devices could lose work. Edge case for solo user.
- **Status auto-change can flicker if Mom reranks aggressively near a threshold:** acceptable; she'll see the toast.

## Required manual setup before deploying

Emily needs to:
1. Go to vercel.com → project `phoebegoeatly` → Storage tab
2. Create new KV (Upstash Redis) instance, connect to project
3. Vercel auto-injects env vars (`KV_URL`, `KV_REST_API_URL`, `KV_REST_API_TOKEN`)

After that, deploy normally.
