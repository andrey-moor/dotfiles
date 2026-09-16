# Outlines by document type

Pick the reader before the outline. The reader decides what the document explains, what it asks, and how long it runs.

| Reader | What the document does |
|---|---|
| Your own team | Explains the problem and the design so teammates can review it |
| Your manager or another decision maker | Asks for one decision, with the options and a recommendation |
| Another team | Defines every term and says exactly what you need from them, and by when |

The person who asked for the document is not always its reader. A manager can ask for a design doc that the team reviews. That document is written for the team, and the manager appears at most as a stakeholder.

## Design doc

Reader: your team or a review board. Length: three to eight pages.

1. **Summary.** The problem, the proposal, and what you need from reviewers, in one paragraph.
2. **Background.** How it works today and what goes wrong, with numbers.
3. **Goals and non-goals.** Two short lists.
4. **Proposal.** The design. Add a figure when the flow has more than three parts.
5. **Alternatives considered.** One entry per alternative, each with the reason it lost.
6. **Risks.** Each risk with its mitigation.
7. **Rollout.** Steps, in order, with the first date you know.
8. **Open questions.** Each with an owner.

## Decision doc

Reader: the person who decides. Length: two to four pages.

1. **Decision needed.** What must be decided, by whom, and by when, in the first paragraph.
2. **Context.** Only what the decision depends on.
3. **Options.** A table that compares cost, risk, and time.
4. **Recommendation.** The option and the reason.
5. **After the decision.** What happens next for each option.

## Status update

Reader: a manager or stakeholders. Length: one to two pages.

1. **Summary.** On track or not, and the main reason, in two or three sentences.
2. **Progress.** Bullets, one result per bullet, with numbers.
3. **Risks and asks.** Each ask names who must act and by when.
4. **Next steps.** Each with a date.

## Procedural guide

Reader: someone who will follow the steps, often new to the system. Length: as long as the procedure needs.

1. **What you will have at the end,** and what the reader needs before starting.
2. **Terms used in this guide,** as a table, when the guide runs past about five pages.
3. **One section per task.** Numbered steps in the plain-prose procedure form. Put one screenshot after the step that opens each new screen, with `"scale=1"` or `"scale=2"` in its title.
4. **Troubleshooting.** A table of symptom and fix.
5. **Appendices,** after `<!-- pagebreak -->`: long code, full configuration, reference tables.

Keep the top level to about eight sections plus appendices. Split a guide that needs more.
