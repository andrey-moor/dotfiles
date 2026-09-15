---
name: plain-prose
description: "Use whenever writing or editing text a person will read, in any file or format: Markdown, HTML, Word, slides, email, UI copy, commit messages, and short forms such as bullets, headings, captions, profile or experience entries, and summaries. Also use when asked to remove mannered prose, cut flourish, simplify, or make writing sound human and direct."
---

# Plain Prose

## Overview

Say what you mean. When a literal phrase is available, use it.

Mannered prose substitutes metaphor and flourish for direct statement. Instead of "a parameter worth varying," the mannered writer produces "a dial worth turning." Instead of "this point still matters," they write "this point earns its keep." The phrases exist to display the writer, not to convey the idea, and readers can tell. That is why mannered prose irritates: it makes the reader work harder so the writer can perform. It is also imprecise. Metaphors drag in connotations the writer did not choose and cannot control. The fix is to say what you mean.

The rules are about words, not files. They apply to every container that holds text a person reads: a Word document, an HTML page, a README, a slide, an email, a table cell, a button label, a commit message. Load this skill for the words even when another skill owns the layout or the code.

**Violating the letter of these rules is violating their spirit.** "Polished," "persuasive," and "for leadership" are not exemptions. They are the situations where plain prose matters most.

## The recipe

Every sentence and paragraph you write has this shape:

1. **One idea per sentence.** Average under 20 words. No sentence over 30. Split at the second verb.
2. **A named subject and an active verb.** "The job fails twice a month," not "failures are experienced."
3. **Literal words.** If a phrase stands for something, write the something. If you cannot say what a metaphor stands for, delete it.
4. **Specific over evaluative.** Replace "significant," "robust," "seamless," "structural" with the number, the mechanism, or the consequence.
5. **Paragraphs of two to four sentences,** one topic each. Break at every change of subject.
6. **Numbers and comparisons of three or more items go in a table,** not a sentence.
7. **One term per thing** for the whole document. Do not alternate "pipeline," "system," and "platform" for the same component.
8. **No em-dashes, no semicolons.** Use a period or a comma. Parenthetical asides become their own sentence or get cut.
9. **No preamble.** Delete sentences that announce content ("This document describes," "It is worth noting," "Importantly").
10. **Hedge only with a condition or a number.** "May fail" becomes "fails when X" or "fails about twice a month."
11. **No placeholders and no invented facts.** Write the value when you have it. When you do not, write "unknown" and what would settle it: who supplies it by when on a live project, or where you looked when working from fixed sources. Never make up a number, a name, or a date to fill a gap.
12. **Bullets only for parallel items,** each one or two sentences. A line of argument stays in prose.

## Match the form to the container

The word rules never change. The sentence form does. Full sentences carry an argument; fragments carry facts in a slot that has no room for a subject.

| Container | Form |
|---|---|
| Paragraphs in a document, email, or page body | Full sentences, rules 1 to 12 |
| Bullets under a heading, slide text, experience or project entries, changelog lines | Fragments: start with the verb or the noun that matters, one fact per fragment, a number wherever one exists, no first person, parallel structure across the list |
| Headings, labels, buttons, table cells, captions | Noun phrases of the fewest words that still say what the thing is |
| Commit subjects, alert text, error messages | Imperative or declarative, under 12 words, states the action or the cause |
| Alt text and accessible descriptions | One or two sentences naming what the reader should see; a list of the parts is fine |

A fragment is still plain: "Cut deploy time from 2 hours to 12 minutes" passes; "Spearheaded a transformational deployment initiative" fails on rules 3 and 4.

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
| the returns are threefold: A, B, and C | Three things improve. (Then one sentence each.) |
| spearheaded, drove, championed, owned the vision for | led, built, ran, decided |
| passionate about, results-driven, seasoned | (delete; the results show it) |
| transformational, world-class, cutting-edge, best-in-class | (delete, or state the measurable change) |
| leverage, utilize | use |
| landscape, ecosystem, journey, north star, flywheel | the literal noun (the tools, the teams, the process, the goal, the loop) |
| at the end of the day, in today's world | (delete) |
| It is worth noting that X | X |

## Self-review pass

After drafting, make one pass and fix everything you find:

- Scan for metaphors and figurative verbs. Replace each with the literal statement.
- Find every sentence over 25 words. Split it.
- Delete the first sentence of each section if it only announces the section.
- Check that each paragraph has one topic.
- Read the first five sentences of the document. A reader who stops there must know the ask and the reason.

## Rationalizations

| Excuse | Reality |
|---|---|
| "Leadership expects polished language" | Leaders read fast and decide on facts. Flourish slows them and signals weak evidence. |
| "Metaphor makes it memorable" | It makes it ambiguous. The reader remembers the image, not the claim. |
| "Short sentences sound simplistic" | They sound like someone who knows what they mean. |
| "The ask was 'persuasive'" | Evidence persuades. Ornament is what writers add when evidence is thin. |
| "One dash won't hurt" | One dash becomes six. The rule has no exceptions. |
| "I'll clean it up after" | The cleanup is this skill. Do it now. |
| "A specific number reads better than 'unknown'" | A made-up number is a lie the reader will act on. Write unknown and who decides. |

## Red flags

Stop and rewrite when you notice:

- A noun that is not the thing itself (liability, shadow, dial, landscape, journey).
- A sentence that joins two clauses with a comma, or lists five or more items inline.
- A dash.
- "threefold," "twofold," "not X but Y," a rhetorical question.
- A bracketed placeholder, or a precise figure you did not get from a source.
- The word "robust," "seamless," "significant," or "leverage."

## About ASD-STE100

Simplified Technical English is an aerospace standard for maintenance manuals. Its writing rules (short sentences, one instruction per sentence, active voice, one term per thing) are the same rules as above and are worth following. Its 900-word approved dictionary is not: it forbids ordinary words a design document needs and produces stilted text. Follow the rules, not the dictionary.
