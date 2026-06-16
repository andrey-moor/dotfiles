Surface the knowledge base notes most relevant to what you're working on now, via the local `kb-engine` CLI.

## Usage

`/kb:surface <description>` — surface notes relevant to a free-text context/project
`/kb:surface --to <note>` — surface notes most similar to a specific note
`/kb:surface --limit N <description>` — cap the number of results (default 10)

Examples:
- `/kb:surface long-term memory for AI agents`
- `/kb:surface what's relevant to my Rust CLI project`
- `/kb:surface --to Knowledge/graph-memory.md`

## Background

Proactive surfacing — "what's relevant to what I'm working on now". This is
**engine-driven and read-only**: the local `kb-engine` does the retrieval (hybrid
semantic + keyword for `--query`; mean-vector cosine over the cache for `--to`), and
Claude presents the results and offers follow-ups. The engine **never mutates the vault**
here.

Assume `kb-engine` is on `PATH` (the Nix wrapper runs the in-repo project) and the vault
is the iCloud `Main` dir. Pass `--json` and parse the output.

## Instructions

### 1. Pick the mode

Parse `$ARGUMENTS`. Pass **exactly one** of `--query` / `--to` (the command errors
otherwise):

- **Free-text context / project / topic** → query mode:
  ```bash
  kb-engine related --query "<the context>" --limit 10 --json
  ```
- **A specific note** (a `--to <path>`, or an obvious note reference) → note mode
  (surfaces the note's nearest neighbors, excluding the note itself):
  ```bash
  kb-engine related --to "Knowledge/<note>.md" --limit 10 --json
  ```

Honor `--limit N` if the user passed one (default 10).

### 2. Parse results

Both modes emit `{hits:[{note_path, title, score}]}`, ranked best-first. If `hits` is
empty, tell the user nothing matched and stop.

### 3. Present + offer follow-ups

Show the ranked notes as `score  title  (note_path)`. Then offer:

- open / read one (`mcp__obsidian__read_note`),
- `/kb:synthesize` a wiki if several of the surfaced notes cluster on one topic,
- refine the query or raise `--limit`.

Read-only throughout — surfacing never writes to the vault.
