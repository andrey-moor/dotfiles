---
name: learn
description: "Use when the user wants to understand or learn a complex topic, system, or codebase: asks to explain something, prepare for a technical interview, get a mental model, or says an existing document or page is too dense to learn from. Also use when asked for a study guide, an explainer, or a walkthrough."
---

# Learn

## Overview

Teaching is not summarizing. A summary compresses the reference. A lesson gives the reader a path: the gist first, then one concrete example followed end to end. Each part comes with its reason for existing, then the traps, then a way to check what stuck. The output is a study Markdown file in a fixed shape, rendered to an interactive single-file page by `scripts/build-study.mjs`.

**REQUIRED SUB-SKILL:** research-notes, when the topic has no checked notes yet. Teach only from notes, never from memory.
**REQUIRED SUB-SKILL:** plain-prose for every sentence.
**REQUIRED SUB-SKILL:** doc-diagrams for the mechanism figure, in step mode as its Step mode section describes.

Script paths are relative to this skill's directory. The research-notes skill sits next to this one, so its checker is `../research-notes/scripts/check-notes.py` from here. First use on a machine: `bash scripts/setup.sh`. A skill created or installed during the current session may not be listed by the Skill tool until after the next tool call. If a named skill is missing, retry once, then read its SKILL.md directly.

## Workflow

1. **State the plan in one message:** the topic, the goal, the sources, the depth, and the one worked example you will thread through. The goal is interview preparation, design review, operating the system, or curiosity. Proceed unless redirected.
2. **Get notes.** Use the topic's `notes/` folder when `python3 ../research-notes/scripts/check-notes.py notes/ --sources <cited folder>` passes. Otherwise run research-notes first. A dense existing document counts as a source: research-notes distills it into tagged claims before you teach from it.
3. **Pick the worked example.** Choose one concrete instance with fixed values that touches every part, such as one request, one job, one packet, or one deploy. The whole lesson follows it. Arithmetic on its values lives in the study file, never in the notes.
4. **Write `study.md`** in the shape below.
5. **Draw the mechanism figure** with doc-diagrams in step mode, one `data-step` per worked-example step. A step may reveal a connector, a label, or an outcome line rather than a node, so the figure can have fewer nodes than steps.
6. **Build:** `node scripts/build-study.mjs study.md` writes `study.html`. The builder stops on a broken rule and warns on a weak one, as listed under Builder checks. Fix the warnings before delivering. Then check the lesson against the notes: `python3 ../research-notes/scripts/check-notes.py notes/ --deliverable study.md --skip-section "Worked example"`. Every number and code name outside the worked example must come from a note.
7. **Check the page** in headless Chromium with a fresh browser profile, because the page remembers depth and grades. Click `button[data-depth="mechanism"]` first, since the Gist view hides everything after the Gist. Then confirm:
   - `[data-stepper-action="next"]` advances `[data-stepper-status]` and the figure's `[data-motion-root]` `data-step-current` together.
   - The figure's own `[data-motion-action="next"]` moves the step text too.
   - Opening a card's `summary` shows its `[data-grade]` buttons, and the grade in `.card[data-state]` survives a reload.
   - `.term[data-def]` spans carry glossary definitions, and none sit inside a button or control.
   - At 400px wide the page does not scroll sideways.

   Then read the Gist as if you know nothing. If a term appears before its definition, fix the order.
8. **Deliver the path to `study.html`** and say it is the one file to open. `figure.html` is the embedded diagram's source, and `study.md` is the editable text. If publishing as an artifact, load artifact-design for the treatment. The page keeps its behavior.

## The study file

Front matter: `title`, which is required, then `goal`, a `sources` list, `date`, and `walkthrough`. `walkthrough` is the word the page uses for the worked example's steps, `Step` by default. Set it to another word, such as `Stage`, when the system has steps of its own. Then these level-1 sections come in this order. HTML comments are allowed for author notes and do not render.

| Section | Required | What goes in it |
|---|---|---|
| `# Gist` | yes | One paragraph of three to six short sentences: what it is, why it exists, the three to five moving parts. It introduces at most three new terms and says everything else in plain words. Then one line starting `**Remember:**` with the single fact to keep |
| `# Mechanism` | no | One figure: `![caption](figure.html)` for a step-mode diagram, or `.png` for a static one. One paragraph of orientation at most |
| `# Worked example` | yes | A lead that declares the example's values as illustrative. That is one sentence, then a short list when there are more than three values. Then `## Step N: title` subsections numbered from 1, or with the `walkthrough` word in place of Step,, each two to four sentences following the example. The page turns them into a stepper that moves with the figure |
| `# Parts` | yes | `## Part name` per component, in the order the example meets them, at most seven. Each opens with four bold labels, **What:**, **Why:**, **Without it:**, and **Remember:**, which the page shows as a labeled list. A `### Details` subsection holds numbers, names, and edge cases, and stays collapsed until the reader chooses Details |
| `# Misconceptions` | no | Bullets of the form `**Wrong belief.** Why it is wrong, and what is true` |
| `# Check yourself` | yes | `## Q: question` subsections with the answer below. Six to ten, ordered from recall to design judgment: first "what does X do", then "why not Y", then "what breaks if Z" |
| `# Glossary` | yes | `- **Term**: definition`, taken from the notes' Terms sections. Every term the lesson uses before explaining it. The page shows the definition on hover at the first use in each section, singular or plural |
| `# Go deeper` | no | Links into the notes and the dense reference, one line each saying what is there |

`templates/study.md` is a complete example that builds without warnings.

## Rules that make it a lesson

- **Why before how.** Each part says what problem it solves before what it does.
- **Define before use.** No term appears before its definition or glossary entry.
- **One example, threaded.** The same request, with the same values, in every step and every part.
- **Gist stands alone.** A reader who stops after the Gist can say what the thing is and why in two sentences.
- **Details are earned.** Ports, header names, defaults, and hash granularities live only in `### Details` and the notes. The worked example's concrete values are its own ids, sizes, and counts, not header names or ports.
- **One name per concept.** Some systems have steps of their own, such as engine steps or training steps. Keep that word for the system and set `walkthrough: Stage` for the lesson. A common word used in two senses gets a qualified technical form everywhere, such as KV block. Put the qualified phrase in the glossary.
- **Definitions have sources too.** A glossary definition comes from the notes' Terms. If the notes do not define a term, add it there with a citation first.
- **Conflicts are stated, not settled silently.** Where the lesson relies on a point the notes mark `Conflict:`, it names both positions.
- **Analogies only when shorter.** If the literal explanation fits in a sentence, use it.
- **General versus here.** When the notes separate general concept from this system, the lesson says which one each claim is.
- **Questions test understanding, not recall of numbers.** "Why does the return path skip the load balancer" beats "what port does the responder use".
- **Every number comes from the notes,** with the same citation reachable through Go deeper. The one exception is the worked example's illustrative values, which its lead declares as such.
- **plain-prose wins on sentence shape.** No sentence over 30 words anywhere, including the Gist and Details. An enumeration that runs long becomes a list.

## Topics that need more than one lesson

Split when the worked example needs more than eight steps or the parts exceed seven. Lay the topic out like this:

```
<topic>/
  sources/          dense material, if any
  notes/            one notes folder shared by every lesson
  lesson-<name>/    study.md, figure.html, figure.png, study.html
```

A later lesson starts where the previous one ended. The later lesson reuses the earlier example values and declares any new assumption as new in its lead. Each lesson's Go deeper starts with links to the lessons before and after it.

## Builder checks

| Check | Result |
|---|---|
| A required section is missing | Error |
| More than eight steps, or more than seven parts | Error: split the topic |
| The stepped figure's step count differs from the worked example's | Error |
| No Remember line in the Gist, no lead in the worked example, or steps not numbered 1 to N | Warning |
| A part missing one of its four labels | Warning |
| Fewer than six or more than ten questions | Warning |
| A relative link whose target does not exist | Warning |

## Common mistakes

| Mistake | Fix |
|---|---|
| Output is a compressed reference: every section leads with implementation detail | Move the detail into `### Details`. Each part opens with What and Why |
| No worked example, or the example changes values between steps | Pick one instance and reuse its values everywhere |
| Terms used in the Gist that are defined later | Reorder, or replace the term with the plain phrase in the Gist |
| Nine or more steps | Split into two lessons, laid out as above |
| Check questions that ask for a number | Rewrite as why or what-if questions |
| Glossary definitions written from memory | Add the term to the notes' Terms with a citation, then use it |
| Taught from memory because notes were "obvious" | Run research-notes. The point is provenance |
