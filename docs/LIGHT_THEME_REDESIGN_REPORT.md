# Light Theme Redesign Report

**Branch:** `ui/hackathon-redesign`  
**Date:** 2026-11-03  
**Scope:** Visual design system + UX polish only (no backend / verification / Muse changes)

---

## 1. Design direction

Shifted from a dark violet AI-dashboard look to a warm, calm productivity aesthetic inspired by Notion-style documents and polished SaaS workspaces.

Keywords: premium, approachable, trustworthy, minimal, readable for nontechnical users.

---

## 2. Color palette

| Token | Hex | Role |
|-------|-----|------|
| `--color-rx-bg` | `#FDFCF9` | Main background |
| `--color-rx-beige` / panel-2 | `#F3F0E8` | Sidebar, secondary surfaces |
| `--color-rx-panel` | `#FFFFFF` | Cards / documents |
| `--color-rx-sage-soft` | `#DDEBDD` | Soft green fills |
| `--color-rx-sage` / ok | `#477A63` | Success / verified |
| `--color-rx-blue-soft` | `#E6F0FA` | Nav active, info |
| `--color-rx-blue` | `#315F86` | Primary actions / nav |
| `--color-rx-text` | `#263238` | Body text |
| `--color-rx-muted` | `#78817D` | Secondary text |
| `--color-rx-line` | `#E6E5DF` | Borders |
| warn | `#B45309` | Incomplete / invalid |
| danger | `#B42318` | Failures |

Approx distribution: warm white/white dominant, beige secondary, sage for verification, blue for actions/navigation.

---

## 3. Typography

- **Inter** — UI / body  
- **Source Serif 4** — restrained hero / Simple Report titles  
- **IBM Plex Mono** — technical IDs and code only  

Loaded via Google Fonts in `index.html`.

---

## 4. Components updated

- `src/index.css` — design tokens, light React Flow chrome  
- `src/components/ui.tsx` — beige sidebar shell, buttons, pills, panels  
- `ReportResultsView.tsx` — Notion-like Simple Report document; light Developer Report  
- `EvidenceGraphView.tsx` — white canvas, blue/sage/beige nodes  
- `ValidationPanel.tsx` — sage/red/amber result cards with labeled sections  
- `RepairPanel.tsx` — blue info banner for evaluation kind  

---

## 5. Pages updated

| Page | Changes |
|------|---------|
| Home / Overview | Serif hero, blue CTA, four capability cards, beige status |
| New Investigation | Blue selected targets, sage mode cards |
| Investigations / Workspace | Light tabs, white timeline cards |
| Results / Reports | Document-width Simple Report sections |
| EvidenceGraph | Light theme nodes + “How We Know” retained |

Navigation (existing views preserved):

- Home → overview  
- New Investigation → setup  
- Investigations → workspace (non-reports tabs)  
- Results → workspace reports tab  

---

## 6. Report styling

Simple Report uses a white document column with serif title and section headings:

Investigation Summary · What ReverseX Tested · What It Discovered · What Remains Unknown · How We Know · What Was Reconstructed · Test Results & Problems · Repairs  

Verified findings use sage cards; informational/partial use mist blue; uncertain use beige.

Developer Report keeps expandable technical sections + React Flow.

---

## 7. EvidenceGraph styling

- White canvas, beige grid  
- Blue investigation/action nodes  
- Sage requirement/validation outcome nodes  
- Beige observation/artifact nodes  
- Warning/failure tones preserved for repair/mismatch  

---

## 8. Responsive behavior

- Sidebar from `min-width: 900px`; compact top nav below that  
- Content max width ~1440px; Simple Report ~768px document column  
- Long IDs wrap via `break-all` on mono text  
- No intentional horizontal overflow  

---

## 9. Accessibility

- Charcoal on warm white for body contrast  
- Focus-visible outline in primary blue  
- Status pills include a text label + dot (not color alone)  
- `aria-current` on active sidebar items  
- Keyboard-focusable buttons retained  

---

## 10. Actual test results

```text
npm run build (tsc -b && vite build)  → success
pytest                                → 104 passed, 2 skipped
GET /health                           → 200
Frontend                             → 200 at http://127.0.0.1:5173/
Verified-findings / human-report     → still served by FastAPI (unchanged contracts)
```

---

## 11. Screenshots

| File | Page |
|------|------|
| `docs/ui-redesign-screenshots/10-light-home.png` | Homepage |
| `docs/ui-redesign-screenshots/11-light-simple-report.png` | Simple Report / workspace |
| `docs/ui-redesign-screenshots/12-light-setup.png` | Investigation setup |

---

## 12. Remaining issues

- Browser automation viewport often shows the compact top nav (<900px); full sidebar appears on typical laptop widths ≥900px.  
- Some older dark-theme screenshots (01–09) remain in the docs folder for historical redesign history.  
- No Git push/merge performed.  

---

## Open URL

**http://127.0.0.1:5173/**

Deep link example:  
**http://127.0.0.1:5173/?job=69f0a4845ee347c8831d691aac18951a**
