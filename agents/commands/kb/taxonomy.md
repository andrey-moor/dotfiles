View and manage the knowledge base taxonomy.

## Usage

`/kb:taxonomy` — show current taxonomy with tag counts
`/kb:taxonomy proposals` — show pending proposals
`/kb:taxonomy approve <tag>` — approve a proposed tag
`/kb:taxonomy reject <tag>` — reject a proposed tag
`/kb:taxonomy add <Category/Tag> <description>` — add a new tag directly
`/kb:taxonomy deprecate <tag> [new-tag]` — deprecate a tag, optionally mapping to replacement

## Instructions

### Default: Show taxonomy

1. Read `Main/_system/_taxonomy.md` via `mcp__obsidian__read_note`.
2. Use `mcp__obsidian__list_all_tags` to get tag counts from the vault.
3. Display taxonomy with usage counts:

```
## Knowledge Base Taxonomy (v2026-03-29)

### AI (N notes)
  AI/LLMs (X) | AI/Agents (Y) | AI/RAG (Z) | AI/Prompting (W) | AI/MLOps (V)

### Dev (N notes)
  Dev/Rust (X) | Dev/Go (Y) | Dev/TypeScript (Z) | Dev/Tools (W) | Dev/Nix (V)

...

### Cross-cutting
  Tutorials (X) | Reference (Y) | Inspiration (Z) | Tools (W)

### Untagged: N notes
```

### `proposals` subcommand

Show the Proposals table from `_taxonomy.md`. For each pending proposal, show the source note that triggered it.

### `approve <tag>` subcommand

1. Find the proposal in the Proposals table.
2. Add the tag to the appropriate category section in `_taxonomy.md` via `mcp__obsidian__patch_note` (insert new tag line in the right section).
3. Update version date in frontmatter via `mcp__obsidian__update_frontmatter`.
4. Remove the proposal row from Proposals table via `mcp__obsidian__patch_note`.

### `reject <tag>` subcommand

1. Find the proposal row in the Proposals table.
2. Change status to `rejected` via `mcp__obsidian__patch_note` (replace the row).
3. Keep in table for history.

### `add <Category/Tag> <description>` subcommand

1. Validate format is `Category/Subcategory`.
2. Add to the appropriate section in `_taxonomy.md` via `mcp__obsidian__patch_note` (insert line after last tag in category).
3. Update version date in frontmatter via `mcp__obsidian__update_frontmatter`.

### `deprecate <tag> [new-tag]` subcommand

1. Remove tag line from its category section via `mcp__obsidian__patch_note`.
2. Add row to Deprecated table via `mcp__obsidian__patch_note`.
3. If `new-tag` provided, note the replacement in the Deprecated table.
4. Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` to count notes using the deprecated tag.
5. Report count and suggest running `/kb:retag` to update affected notes.
