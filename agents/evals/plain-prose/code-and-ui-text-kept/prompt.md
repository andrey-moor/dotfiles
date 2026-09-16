---
description: Rewriting a how-to keeps commands and UI labels exactly as given, even where they contain semicolons or parentheses.
tags: [plain-prose, regression]
max_turns: 8
timeout_seconds: 300
allowed_tools: [Read, Skill]
---

tidy up this how-to so it reads cleanly, and save it as howto.md. don't change what people type or click. the menu item is literally labeled "Settings (Advanced)" on screen, so that label has to stay exactly like that.

"To clear the cache you should probably first of all run `cache-tool purge --older-than 7d; cache-tool stats` (this takes a minute or so) — and then, once that's done, go into the app and choose Settings (Advanced) and switch off Preload on start; after that restart the app."
