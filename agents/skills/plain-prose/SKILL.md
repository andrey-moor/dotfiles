---
name: plain-prose
description: "Use whenever writing or editing text a person will read, in any file or format: Markdown, HTML, Word, slides, email, UI copy, commit messages, and short forms such as bullets, headings, captions, profile or experience entries, and summaries. Also use when asked to remove mannered prose, cut flourish, simplify, or make writing sound human and direct."
---

# Plain Prose

## Overview

Say what you mean. When a literal phrase is available, use it.

Mannered prose puts metaphor and flourish where a direct statement belongs. The mannered writer turns "a parameter worth varying" into "a dial worth turning." The same writer turns "this point still matters" into "this point earns its keep." Such phrases exist to display the writer, not to convey the idea, and readers can tell. Mannered prose irritates because it makes the reader work harder so the writer can perform. Mannered prose is also imprecise, because a metaphor drags in connotations the writer did not choose. The fix is to say what you mean.

The rules are about words, not files. The rules apply to every container that holds text a person reads, from a Word document to a table cell or a commit message. Load this skill for the words even when another skill owns the layout or the code.

The rules cover the sentences you write. Keep text you copy exactly as its source has it:

- code, commands, file names, and identifiers
- UI labels, spelled as the screen shows them
- quotations and titles
- formats a system requires, such as a fixed line layout in an index file

**Violating the letter of these rules is violating their spirit.** "Polished," "persuasive," and "for leadership" are not exemptions. Those are the situations where plain prose matters most.

## The recipe

Every sentence and paragraph you write has this shape:

1. **One idea per sentence.** Average under 20 words. No sentence over 30. Split at the second verb.
2. **A named subject and an active verb.** "The job fails twice a month," not "failures are experienced."
3. **Literal words.** If a phrase stands for something, write the something. If you cannot say what a metaphor stands for, delete it.
4. **Specific over evaluative.** Replace "significant," "robust," "seamless," "structural" with the number, the mechanism, or the consequence.
5. **Paragraphs of two to four sentences,** one topic each. Break at every change of subject.
6. **Numbers and comparisons of three or more items go in a table,** not a sentence.
7. **One term per thing, defined on first use.** Give each acronym and internal system name a short definition the first time it appears: "IGW, the ingest gateway that writes the audit log." Say what a change does, not only its number: "PR 4821, which adds request IDs to the audit log." Then use that one term for the whole document, never "pipeline," "system," and "platform" for the same component. In a document longer than about five pages, fix the terms in a short table near the start.
8. **No em-dashes, no semicolons.** Use a period or a comma. Parenthetical asides become their own sentence or get cut.
9. **No preamble.** Delete sentences that announce content, such as "This document describes," "It is worth noting," and "Importantly."
10. **Hedge only with a condition or a number.** "May fail" becomes "fails when X" or "fails about twice a month."
11. **No placeholders and no invented facts.** Write the value when you have it. When you do not, write "unknown" and what would settle it. On a live project, name who supplies the value and by when. Working from fixed sources, name where you looked. Never make up a number, a name, or a date to fill a gap. In a design doc, a labeled assumption is fine, and so is a value marked "Proposed" or "To be named." The label tells the reader the value is not settled.
12. **Bullets only for parallel items,** each one or two sentences. A line of argument stays in prose.

## Match the form to the container

The word rules never change. The sentence form does. Full sentences carry an argument. Fragments carry facts in a slot that has no room for a subject.

| Container | Form |
|---|---|
| Paragraphs in a document, email, or page body | Full sentences, rules 1 to 12 |
| Bullets under a heading, slide text, experience or project entries, changelog lines | Fragments: start with the verb or the noun that matters, one fact per fragment, a number wherever one exists, no first person, parallel structure across the list |
| Numbered procedure steps | One action per step, starting with the imperative verb. UI labels in bold, spelled as the screen shows them. The last step states the result the reader should see |
| Chat messages to paste into Teams, Slack, or an email | A friendly opening line, two or three sentences of context, then the questions as a numbered list. Define every acronym and internal name, because the reader may not share your context |
| Headings, labels, buttons, table cells, captions | Noun phrases of the fewest words that still say what the thing is |
| Commit subjects, alert text, error messages | Imperative or declarative, under 12 words, states the action or the cause |
| Alt text and accessible descriptions | One or two sentences naming what the reader should see. A list of the parts is fine |

A fragment is still plain. "Cut deploy time from 2 hours to 12 minutes" passes. "Spearheaded a transformational deployment initiative" fails rules 3 and 4.

Facts about a person, team, product, or organization come only from the source material or the user. Where a fact is missing, leave a visible marker for the user to fill, never a plausible substitute.

## Swap table

| Mannered | Plain |
|---|---|
| a dial worth turning | a parameter worth varying |
| this point earns its keep | this point still matters |
| has become a structural liability | fails twice a month and costs a day each time |
| within striking distance of business hours | ends 40 minutes before business hours |
| we cannot tune our way out of this | tuning will not fix this |
| a batch-shaped solution to an event-shaped problem | a batch job for work that arrives one event at a time |
| erodes trust with downstream consumers | Finance no longer relies on the numbers |
| the maintenance burden that shadows them | the maintenance they require |
| build proof and internal advocacy | show it works, so other teams ask for it |
| cost us more than they return | cost more than they save |
| the returns are threefold: A, B, and C | Three things improve. Then one sentence for each |
| spearheaded, drove, championed, owned the vision for | led, built, ran, decided |
| passionate about, results-driven, seasoned | Delete. The results show it |
| transformational, world-class, cutting-edge, best-in-class | Delete, or state the measurable change |
| leverage, utilize | use |
| landscape, ecosystem, journey, north star, flywheel | the literal noun: the tools, the teams, the process, the goal, the loop |
| at the end of the day, in today's world | Delete |
| It is worth noting that X | X |

## Self-review pass

After drafting, make one pass and fix everything you find:

- Run `python3 scripts/lint-prose.py <file>` on a Markdown or text file. The path is relative to this skill's directory. The script flags dashes, semicolons, parentheses, sentences over 25 words, an average over 20 words, and sentences that open with "It" or "They." The script skips code, quotations, bold UI labels, front matter, and link targets. Fix every finding.
- For text the script cannot read, such as a slide or a UI string, find every sentence over 25 words and split it.
- Scan for metaphors and figurative verbs. Replace each with the literal statement.
- Delete the first sentence of each section if it only announces the section.
- Check that each paragraph has one topic.
- Check that each acronym, internal name, and PR number is explained where it first appears.
- Read the first five sentences of the document. A reader who stops there must know the ask and the reason.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Leadership expects polished language" | Leaders read fast and decide on facts. Flourish slows them and signals weak evidence. |
| "Metaphor makes it memorable" | It makes it ambiguous. The reader remembers the image, not the claim. |
| "Short sentences sound simplistic" | They sound like someone who knows what they mean. |
| "The ask was 'persuasive'" | Evidence persuades. Ornament is what writers add when evidence is thin. |
| "One dash won't hurt" | One dash becomes six. The rule has no exceptions in your own sentences. |
| "I'll clean it up after" | The cleanup is this skill. Do it now. |
| "A specific number reads better than 'unknown'" | A made-up number is a lie the reader will act on. Write unknown and who decides. |
| "The team knows that acronym" | The reader may be on another team, or new. Define it once. |
| "The pronoun is clear from context" | Its referent sits in another sentence, where a wrong fact can hide. Name the thing again. |

## Red flags

Stop and rewrite when you notice:

- A noun that is not the thing itself, such as liability, shadow, dial, landscape, or journey.
- A sentence that joins two clauses with a comma, or lists five or more items inline.
- A dash.
- "threefold," "twofold," "not X but Y," a rhetorical question.
- A bracketed placeholder, or a precise figure you did not get from a source.
- The word "robust," "seamless," "significant," or "leverage."
- A sentence that opens with "It" or "They," or any pronoun whose referent is in another sentence. In a message to another person, name the thing every time.
- An acronym, an internal system name, or a PR number with no word on what it is or does.

## About ASD-STE100

Simplified Technical English is an aerospace standard for maintenance manuals. Its writing rules match the rules above: short sentences, one instruction per sentence, active voice, one term per thing. Those rules are worth following. Its 900-word approved dictionary is not, because the dictionary forbids ordinary words a design document needs and produces stilted text. Follow the rules, not the dictionary.
