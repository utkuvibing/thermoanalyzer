# Agent Workflow Guide

This repository uses a context-first vibecoding workflow.

## Primary operating model

- Prefer one primary agent per task.
- Do not simulate a company org chart such as PM -> Architect -> Developer -> QA handoffs.
- If parallel exploration is needed, use it only to gather alternatives or inspect different parts of the codebase, then merge the findings back into one implementation path.
- Preserve continuity through repository files, not chat memory.

## Files to read before making changes

Read these before planning or editing code:

1. `README.md`
2. `AGENTS.md`
3. `.ai/SESSION.md`
4. `.ai/TASK.md`
5. `.ai/DECISIONS.md`

If one of these files is missing or clearly stale, say so explicitly.

## Required pre-change behavior

Before changing code:

1. Read the relevant context files.
2. Inspect the files most likely involved in the task.
3. Summarize your understanding in 5 bullets.
4. State assumptions, risks, and missing information.
5. Propose the smallest useful next step.

Do not start with a broad rewrite when a smaller validated slice is possible.

## Implementation rules

- Prefer small, testable patches over large rewrites.
- Reuse existing patterns before inventing new abstractions.
- Keep functions and modules focused.
- Avoid touching unrelated modalities unless the task requires it.
- Explain why a structural change is necessary before making it.
- Preserve working flows while extending unfinished ones.

## Verification rules

After a meaningful code change:

- Check for import errors.
- Check the directly affected execution path.
- Note likely regressions or edge cases.
- Report what was verified and what was not verified.

## Handoff rules

At the end of a meaningful work session, update:

- `.ai/SESSION.md` with current status, blockers, next step, and touched files.
- `.ai/DECISIONS.md` with any durable technical decision and the reason for it.

Keep those files short, current, and specific.

## Task sizing

Break work into slices with clear acceptance criteria.

Good:
- add DTA page shell
- wire upload flow
- render first valid plot
- add invalid-file error path

Bad:
- finish entire Dash migration

## Review mode

When asked to review, critique, or verify:

- look for broken assumptions
- identify edge cases
- name regression risks
- suggest the smallest correction first

Do not default to rewriting everything.
