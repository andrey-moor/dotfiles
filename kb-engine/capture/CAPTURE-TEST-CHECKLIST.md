# Capture feasibility checklist (Phase 0a)

**Goal:** prove the Web Clipper captures everything we need — across sources and
devices — into an engine-ingestible inbox note with a `why`. This gates the rest
of the redesign.

**Before you start:** install + configure the clipper per `README-web-clipper.md`
(vault = iCloud `Main`, template "KB Inbox", note folder `Knowledge/inbox`).

## Test set — clip each, on the device(s) listed

Pick any real URL of each kind (your own saved links are ideal). Where two
devices are listed, clip it on both.

| # | Source | Device(s) | Pass = |
|---|--------|-----------|--------|
| 1 | plain article (blog/news) | Mac + iPhone | body clean, `why` captured |
| 2 | Twitter/X tweet + thread | Mac + iPhone | tweet text present (not a login wall) |
| 3 | GitHub repo page | Mac | README/description present |
| 4 | YouTube video | Mac + iPhone | title + description present |
| 5 | Reddit thread | Mac | post/top comments present (was headless-blocked) |
| 6 | paywalled / JS-heavy page (a Substack/doc you can read) | Mac | body present (you're logged in) |
| 7 | shortened link (`t.co` / bit.ly) | Mac | resolves to the destination page |
| 8 | Instagram post | Mac | best-effort — **allowed to fail** |
| 9 | page from an email link (open in Safari → clip) | Mac + iPhone | destination clipped |

For each clip, confirm the clipper **prompted for "Why are you saving this?"**
(or record that it didn't → degraded path, add `why` in review).

## Verify ingestion

After clipping the set, from `/Users/andreym/Documents/dotfiles/kb-engine`:

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
uv run kb-engine --vault "$VAULT" inbox-check --json
```

Pass criteria:
- `schema_bad` is **empty** (every clip carries `title,url,source,date_added,status,tags`).
- `missing_why` is **empty** (or non-empty only because you chose the degraded path).
- Review `dup_in_inbox` / `dup_vs_knowledge` (expected empty for fresh test URLs).

## Results — fill this in

| # | Source | Mac clean? | iPhone clean? | why captured? | notes |
|---|--------|-----------|---------------|---------------|-------|
| 1 | article | | | | |
| 2 | tweet | | | | |
| 3 | github | | n/a | | |
| 4 | youtube | | | | |
| 5 | reddit | | n/a | | |
| 6 | paywalled | | n/a | | |
| 7 | shortlink | | n/a | | |
| 8 | instagram | | n/a | | (ok to fail) |
| 9 | email link | | | | |

- `inbox-check` result: `schema_bad=___ missing_why=___`
- "why" prompt works at clip time? **yes / no (degraded path)**
- In-browser clipping obviated the old fetch tier (tweets/paywall/shortlink)? **yes / partly / no**

## Cleanup

These are throwaway test clips. After recording results, delete them from
`Knowledge/inbox/` (they should not flow into the real KB):

```bash
# review first, then remove the test clips you created
ls "$VAULT/Knowledge/inbox/"
```

Then tell me the results and I'll record them in the design spec (Phase 0 gate)
and we proceed to Phase 1 (or adjust the template / choose degraded paths first).
