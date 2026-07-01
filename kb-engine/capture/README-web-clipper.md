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
If import fails or your version's schema differs, recreate the **"Default"**
template (empty triggers, so every clip uses it) with:

- **Note location / path:** `Knowledge/inbox`
- **Note name:** the page title (`{{title}}`) — a page with no title lands as
  `Untitled.md`; processing applies a title fallback later
- **Note content:** the page content (`{{content}}`, readability extraction)
- **Properties (frontmatter):**

  | property | value | notes |
  |----------|-------|-------|
  | `title` | the page title | |
  | `url` | the page URL | engine normalizes on read (dedup) |
  | `source` | `article` | literal; engine re-infers (github/tweet/…) at process time |
  | `date_added` | clip date (`{{date}}`) | ISO timestamp; presence-checked, normalized downstream |
  | `summary` | *(empty)* | filled at process time |
  | `status` | `inbox` | **must be exactly `inbox`** |
  | `context` | `Web Clipper` | provenance |
  | `tags` | *(empty list)* | omitted by the clipper when empty; applied later by topic tagging |
  | `why` | *(empty text — you fill it in the clip popup)* | your intent — the key new signal; **don't** use the Interpreter `{{"…?"}}` syntax (it makes the LLM guess) |
  | `project` | *(empty, optional)* | name a project if you already know it |

## 3. Fill "why" at clip time (pivotal)

The whole design leans on capturing *why* at clip time. `why` is an empty
**text** property, so it shows as a blank field in the clip popup — type your
reason there (e.g. "pixel-art reference for the game"). The clipper does **not**
modally prompt, so it's easy to forget (in testing it was missed on most clips).

That's expected, not a failure: a clip with no `why` still lands and stays
searchable. `kb-engine inbox-check` reports it under `missing_why`, and the
**`/kb:review` triage step backfills it in ~5 seconds** — your safety net.

Do **not** set `why` to the Interpreter prompt syntax (`{{"Why are you saving
this?"}}`): that hands the question to Web Clipper's LLM, which would *guess*
your intent — the opposite of capturing it. Keep it empty and human-filled.

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
