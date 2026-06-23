# KB capture — Obsidian Web Clipper setup

The KB's capture front door. Clipping a page writes a real note straight into
`Knowledge/inbox/` (no import hop), carrying the inbox schema **plus** a `why`
(your intent) so the engine can route it to topics and projects.

> The authoritative gate is **`kb-engine inbox-check`** on the clipped output —
> the template below is best-effort (Web Clipper's template format varies by
> version). If a clip doesn't pass `inbox-check`, adjust the template properties
> to match; the *output schema* is what matters, not the template JSON.

## 1. Install the extension

- **macOS Safari:** install "Obsidian Web Clipper" (App Store / Obsidian site),
  enable it in Safari → Settings → Extensions.
- **iPhone Safari:** install the same extension (it ships an iOS Safari
  extension), enable it in Settings → Safari → Extensions. You'll trigger it
  from the Share sheet / the `ᴀA`/extensions button.

In the clipper settings, set the **vault** to your iCloud `Main` vault so clips
land in the same vault the engine reads.

## 2. Import the template

Import `web-clipper-template.json` (this folder) into the clipper's *Templates*.
If import fails or your version's schema differs, recreate a template named
**"KB Inbox"** with:

- **Note location / path:** `Knowledge/inbox`
- **Note name:** the page title (safe filename)
- **Note content:** the page content as Markdown (readability extraction)
- **Properties (frontmatter):**

  | property | value | notes |
  |----------|-------|-------|
  | `title` | the page title | |
  | `url` | the page URL | engine normalizes on read (dedup) |
  | `source` | `article` | literal; engine re-infers (github/tweet/…) at process time |
  | `date_added` | clip date `YYYY-MM-DD` | |
  | `summary` | *(empty)* | filled at process time |
  | `status` | `inbox` | **must be exactly `inbox`** |
  | `context` | `Web Clipper` | provenance |
  | `tags` | *(empty list)* | applied later by topic tagging |
  | `why` | **prompt: "Why are you saving this?"** | your intent — the key new signal |
  | `project` | *(empty, optional)* | name a project if you already know it |

## 3. Verify the "why" prompt (pivotal)

The whole design leans on capturing *why* at clip time. After importing,
**do a test clip and confirm the clipper prompts you for "Why are you saving
this?"** and writes it to the `why` frontmatter.

- **If it prompts:** great — capture stays one step.
- **If your version can't prompt for free text** (especially on iOS): set `why`
  to empty in the template and use the **degraded path** — you'll add "why" in a
  5-second triage step during `/kb:review`. The design still holds; note this in
  the test checklist results.

## 4. Field intent (why each exists)

- `why` / `project` are the new signals: they enrich the note's embedding, sharpen
  topic classification, and route the note toward projects (e.g. "for the game —
  pixel-art reference" → topic `graphics`, project `retro-platformer`).
- The note is never "lost": even if it matches no topic, it stays searchable and
  appears in the by-category index. Capture liberally.

## 5. Confirm clips are ingestible

After clipping (see `CAPTURE-TEST-CHECKLIST.md`), run from `kb-engine/`:

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
uv run kb-engine --vault "$VAULT" inbox-check --json
```

`schema_bad` must be empty (every clip carries the required keys). `missing_why`
should be empty unless you chose the degraded path. Fix the template until clips
pass.
