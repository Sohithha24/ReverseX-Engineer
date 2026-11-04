# IT-Tools Base64 — Private Holdout Evaluation Plan

**Status:** Plan only. No scores. Exact holdout values are evaluator-private and must not be placed in Muse or reconstruction prompts.

**Observed original behaviors (evaluator Playwright, not Muse):**

| Category | Original behavior observed |
|----------|----------------------------|
| Ordinary ASCII | Encodes to standard Base64 in the encode-output textarea |
| Empty text | Encode output becomes empty |
| Unicode | Encodes (UTF-8 Base64) in encode-output textarea |
| Punctuation | Encodes |
| Newlines | Encodes (includes newline bytes) |
| Encoded input (decode) | Valid Base64 round-trips for tested ASCII |
| Invalid Base64 | Decode output remained empty for `!!!!` (no visible error string observed in the decode textarea) |

**URL-safe encode toggle** exists in the UI; not exercised in depth for this plan (control may not be a SafeBrowser-discoverable button/input).

## Holdout categories (evaluator later)

Use independently chosen inputs in each category that exist above. Do **not** reuse probe strings from compatibility screenshots (`Hello ReverseX`) as the only holdouts.

1. Ordinary ASCII short string  
2. Empty string  
3. Unicode (non-ASCII letters / CJK)  
4. Punctuation / symbols  
5. Embedded newlines  
6. Valid Base64 decode case  
7. Invalid Base64 decode case  

## Comparison method (future)

- Run the same holdout inputs against the **original** IT-Tools page and any **reconstruction**, if one exists.
- Compare encode/decode textarea **values** (not ReverseX `visible_text`, which currently omits textarea values).
- Do not assign a pass rate until tests execute.

## Isolation rules

- Keep exact holdout literals out of investigation feature text, Muse context, and reconstruction prompts.
- Compatibility probe artifacts under `docs/audit-evidence-it-tools/` are evaluator evidence, not Muse training answers.
