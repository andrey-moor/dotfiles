# Content Fetching Strategy

How to fetch URL content during `/kb:process`. Uses a tiered approach: fast static fetch first, browser automation as fallback.

## Tier 1: WebFetch (default)

Use `WebFetch` for the URL. This works for most static pages: blogs, GitHub READMEs, documentation, newsletters.

**Success indicators:** Response contains actual page content (paragraphs, headings, article text).

**Failure indicators — escalate to Tier 2:**
- Response contains "JavaScript is not available" or "Please enable JavaScript"
- Response is mostly HTML/CSS/JS scaffolding with no article content
- Response is a login wall or "Sign up to continue"
- Response is empty or just navigation elements
- HTTP error (403, 429, etc.)

## Tier 2: agent-browser (JS-heavy pages)

Use `agent-browser` CLI to load the page in a headless browser.

### For Twitter/X URLs (`x.com`, `twitter.com`)

Twitter requires authentication. Use the saved auth state:

```bash
agent-browser --state ~/.agent-browser/twitter-auth.json open "<url>"
agent-browser wait 3000
```

Extract tweet thread content:
```bash
agent-browser eval --stdin <<'EVALEOF'
Array.from(document.querySelectorAll('[data-testid="tweetText"]')).map(el => el.innerText).join("\n\n---\n\n")
EVALEOF
```

Extract author:
```bash
agent-browser eval --stdin <<'EVALEOF'
document.querySelector('[data-testid="User-Name"] a')?.textContent || ""
EVALEOF
```

Always close when done:
```bash
agent-browser close
```

**Auth expired?** If the page shows "Log in" / "Sign up" instead of content:
1. Do NOT silently fall back to partial content
2. Tell the user:
   ```
   ⚠ Twitter auth expired. Re-export by:
   1. Open Chrome with remote debugging enabled (chrome://inspect/#remote-debugging)
   2. Run: agent-browser --cdp "ws://127.0.0.1:9222/devtools/browser" state save ~/.agent-browser/twitter-auth.json
   ```
3. Skip this note (leave in inbox) and continue processing others

### For YouTube URLs

```bash
agent-browser open "<url>"
agent-browser wait --load networkidle
```

Extract title and description:
```bash
agent-browser eval --stdin <<'EVALEOF'
JSON.stringify({
  title: document.querySelector('h1.ytd-watch-metadata yt-formatted-string')?.textContent || document.title,
  description: document.querySelector('#description-inline-expander yt-attributed-string')?.textContent || "",
  channel: document.querySelector('#channel-name yt-formatted-string a')?.textContent || ""
})
EVALEOF
```

### For other JS-heavy pages (Notion, SPAs, etc.)

```bash
agent-browser open "<url>"
agent-browser wait --load networkidle
agent-browser wait 2000
```

Extract page text:
```bash
agent-browser eval --stdin <<'EVALEOF'
document.querySelector('article')?.innerText ||
document.querySelector('[role="main"]')?.innerText ||
document.querySelector('main')?.innerText ||
document.body.innerText.substring(0, 5000)
EVALEOF
```

### Auth detection for any site

After loading a page, check if content was actually retrieved:

```bash
agent-browser snapshot -i
```

**Signs of auth wall (do NOT silently skip):**
- Snapshot shows "Log in", "Sign up", "Sign in" buttons as primary actions
- Page title contains "Login" or "Sign in"
- No meaningful content elements, only auth forms

**If auth is needed:**
```
⚠ <url> requires authentication.
  The page shows a login wall. To fetch this content:
  1. Log in to <domain> in Chrome
  2. With chrome://inspect/#remote-debugging enabled, run:
     agent-browser --cdp "ws://127.0.0.1:9222/devtools/browser" state save ~/.agent-browser/<domain>-auth.json
  3. Re-run /kb:process

  Skipping this note (left in inbox).
```

Always close agent-browser when done:
```bash
agent-browser close
```

## Error Handling Rules

1. **Never silently swallow fetch failures.** If content can't be fetched, tell the user why.
2. **Never fabricate content.** If you can't fetch the page, say so. Don't write a summary based on the URL alone and pretend it's from the page.
3. **Partial content is OK if disclosed.** If you got the first tweet but not the full thread, say "Extracted 1/6 tweets — thread may be truncated."
4. **Auth failures are user-actionable.** Always provide the re-auth steps.
5. **Leave unfetchable notes in inbox.** Don't move them to Knowledge/ with empty content. The user can retry later.
