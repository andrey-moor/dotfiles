# Cowork ↔ kb-engine MCP probe (Phase 0b)

**Goal:** confirm Claude Cowork can reach a **local** kb-engine MCP tool, and that
a **Live Artifact** can refresh from it. This decides whether the Phase 2 project
workbench can be a live, auto-refreshing artifact (or needs the scheduled-task
fallback). Throwaway probe — the production read/review MCP is Phase 1.

## 1. Find your `uv` path

GUI-launched apps don't inherit your shell `PATH`, so the MCP config needs an
**absolute** path to `uv`:

```bash
which uv     # e.g. /etc/profiles/per-user/andreym/bin/uv
```

## 2. Register the probe as a local MCP server

In Claude Desktop / Cowork, add a local MCP server (Cowork sidebar → **Customize**
→ connectors / MCP, or edit the config file directly:
`~/Library/Application Support/Claude/claude_desktop_config.json`). Merge this into
`mcpServers` (replace `/ABS/PATH/TO/uv` with the path from step 1):

```json
{
  "mcpServers": {
    "kb-engine-probe": {
      "command": "/ABS/PATH/TO/uv",
      "args": [
        "run", "--extra", "mcp",
        "--project", "/Users/andreym/Documents/dotfiles/kb-engine",
        "python", "-m", "kb_engine.mcp.probe"
      ],
      "env": {
        "KB_VAULT": "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
      }
    }
  }
}
```

Restart Cowork so it picks up the server. It should list `kb-engine-probe` with
two tools: `kb_status` and `kb_search`.

## 3. Connectivity test

In a Cowork task, ask it to:
- call **`kb_status`** → expect `{notes, chunks, server_time}` with your real
  vault counts (hundreds of notes).
- call **`kb_search`** with a query you know is in the KB (e.g. "rust") → expect a
  list of `{note_path, title, score}` hits.

If both return real data → **connectivity confirmed**.

Troubleshooting: if the server won't start, run the exact command from the config
in a terminal (with `KB_VAULT` set) and check the error; the most common cause is
a wrong `uv` path or `--extra mcp` not yet installed (run it once in the terminal
to warm the install).

## 4. Live-Artifact refresh test

Ask Cowork to **create a Live Artifact** that displays `kb_status` — notes/chunks
plus the `server_time`. Then:
1. Note the `server_time` shown.
2. Close the artifact and reopen it (or hit refresh).
3. Check whether `server_time` **updates**.

- **It updates** → the Live Artifact re-queries the custom local MCP on open. The
  Phase 2 project workbench can be a live artifact (References + Inspiration lanes
  that refresh as you capture). ✅
- **It does NOT update / can't reach the MCP** → record the **fallback**: a Cowork
  *scheduled or on-demand task* regenerates the project artifact's data instead of
  a live refresh. The design still holds; the workbench just refreshes on a task
  rather than on open.

## 5. Results — fill this in

- `kb-engine-probe` server starts + lists tools: **yes / no**
- `kb_status` returns real counts: **yes / no**  (notes=____ chunks=____)
- `kb_search` returns hits: **yes / no**
- Live Artifact refreshes `server_time` from the custom MCP: **yes / no**
- Phase 2 refresh mechanism: **live-artifact refresh / scheduled task fallback**

Tell me the results and I'll record them in the design spec (Phase 0 gate).
