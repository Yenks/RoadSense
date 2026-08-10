# Design System — School Zone Safety Intelligence Dashboard

## Brief

An evidence-based traffic safety monitoring dashboard for a school zone in
Tamale, Ghana. Displays real drone footage analysis: vehicle speeds,
legal violations (Ghana Road Traffic Regulations 2012, L.I. 2180), and
pedestrian-crossing yield compliance. Audience: the developer, academic
supervisor, and project teammates reviewing evidence and results — not
a public marketing site. Tone: authoritative, calm, precise — a civic
safety instrument, not a startup product.

## Color

| Name            | Hex       | Use                                              |
|------------------|-----------|---------------------------------------------------|
| Asphalt          | `#1C1F22` | Primary dark surface — nav, headers               |
| Marking Yellow   | `#F4B400` | Primary accent — hazard/attention, active states   |
| Alert Red        | `#D8453C` | Violations, danger states, over-limit speeds       |
| Clear Green      | `#2E8B57` | Compliant vehicles, safe/under-limit states        |
| Fog              | `#EDEFF1` | Light background, card surfaces                    |
| Slate            | `#5B6470` | Secondary text, muted labels, borders              |

Semantic rule: **red = violation, green = compliant, yellow = neutral
attention/informational** — consistent everywhere, never decorative.

## Type

- **Display / Headings**: `Space Grotesk` — geometric, technical character,
  used for page titles and key stat numbers. Distinct from default Inter/
  system-ui, fits a telemetry/instrumentation feel.
- **Body**: `IBM Plex Sans` — clean, civic, highly legible at small sizes
  for tables and dense data.
- **Data / Utility** (speeds, timestamps, track IDs, coordinates):
  `IBM Plex Mono` — monospace reinforces "this is a real measurement,"
  distinguishes raw data from UI chrome at a glance.

## Layout Concept

Persistent left sidebar navigation (Dashboard / Violations / Videos /
Logout), not a top nav bar — this is a working tool used repeatedly in
one session, not a page you scroll through once.

```
┌──────────┬────────────────────────────────────┐
│          │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓ (hazard stripe)     │
│  Sidebar │  Overview                            │
│          │  ┌────────┐ ┌────────┐ ┌────────┐   │
│  Dashboard│  │Vehicles│ │Violtns │ │Videos  │   │
│  Violations│ └────────┘ └────────┘ └────────┘   │
│  Videos  │                                       │
│          │  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓ (red stripe)          │
│  Logout  │  Recent Violations                    │
│          │  [table with snapshot thumbnails]     │
└──────────┴────────────────────────────────────┘
```

Each processed video gets its own detail page (vehicles list, violations,
speed distribution chart) rather than one long scrolling page.

## Signature Element

**Hazard-stripe section dividers.** A thin diagonal-striped bar (pulled
directly from real road hazard tape/barrier markings) appears under
every section header. Its color changes with the section's meaning:
amber for general/informational sections, red above violation lists,
green above compliant-vehicle summaries. This is structural, not
decorative — it's the same visual language as the actual physical
safety markings the system is monitoring, and it does real information
work (you can tell a violations section from a summary section at a
glance, even before reading).

## Component Notes

- **Stat cards**: no gradients. Flat `Fog` surface, `Asphalt` border,
  big `Space Grotesk` number, `Slate` label underneath. Quiet, let the
  number and the hazard-stripe divider do the work.
- **Violation rows**: left border in `Alert Red`, snapshot thumbnail,
  monospace speed reading, plain-language type ("Speeding" /
  "Failed to yield") — not raw enum values.
- **Charts**: Chart.js, colors pulled from the palette above (not
  default Chart.js blues) — violations-by-type uses Red/Yellow/Green
  by severity, not arbitrary hues.
- **Empty states**: e.g. "No violations recorded for this video" —
  direct, factual, not apologetic.

## Accessibility / Quality Floor

- Responsive down to a single-column layout on mobile (sidebar collapses
  to a top bar).
- Visible keyboard focus outlines on all interactive elements.
- Color is never the only signal for violation vs. compliant — text
  labels always accompany color coding.

