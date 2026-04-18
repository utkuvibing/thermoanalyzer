# Bugs — MaterialScope

Tracked defects and suspected problems. **Root cause is never “proven” here without evidence**—update fields as facts change.

## Status definitions (use exactly these meanings)


| Status        | Meaning                                                                                      |
| ------------- | -------------------------------------------------------------------------------------------- |
| **Suspected** | Not yet reproduced or otherwise confirmed; hypothesis or report only.                        |
| **Open**      | Reproduced **or** otherwise confirmed; **not fixed** yet.                                    |
| **Fixed**     | A fix **was applied**; still **needs verification** (tests and/or agreed manual check).      |
| **Closed**    | Fix **verified**; no further work on this entry unless it regresses (then open a new entry). |


Do **not** use alternate labels (e.g. “mitigated”, “in progress”) in new entries—fold that into **Open** or **Fixed** per the table.

**Workflow / verification discipline:** `**.cursor/rules/00-workflow.mdc`**.

---

## Entry template (copy below the line)

```
### Title
<short name>

### Status
Suspected | Open | Fixed | Closed

### Symptoms
Observable facts only.

### Repro steps
Numbered steps; note branch/environment/data when relevant.

### Likely cause
Hypotheses; update after evidence.

### Files involved
Known paths, or “unknown until traced”.

### Next check
Smallest test, log, or experiment to advance status.
```

---

## BUG-001 — Possible parity gaps during Streamlit → Dash migration

### Title

Possible parity / behavior gaps between legacy Streamlit flows and Dash + Plotly surfaces

### Status

**Suspected**

### Symptoms

Users **may** see mismatches (missing views, different defaults, divergent plots/metrics, inconsistent file/workspace handling) **if** Streamlit and Dash paths diverge. No specific workflow is confirmed in this entry.

### Repro steps

1. Pick a workflow that **actually exists** on both paths (verify in app/docs).
2. Same inputs (project, files, settings); compare outputs/affordances; record differences.

*(If no dual path exists, note that—do not force a repro.)*

### Likely cause

**Unknown** until a concrete case exists; candidates include UI duplication, incomplete callbacks, API differences, or intentionally deferred features.

### Files involved

**Unknown** until traced; usual suspects live under `dash_app/`, `backend/`, `core/`, and any remaining Streamlit entrypoints—confirm, do not guess.

### Next check

One workflow: document parity with evidence, **or** promote a **narrow** child entry to **Open** with a confirmed repro and file pointers.

---

## BUG-002 — Saved analysis figures missing in exports/project persistence

### Title

Saved results intermittently lacked persisted analysis figures in shared state

### Status

**Closed**

### Symptoms

- Graph visible in Dash analysis page but missing in exported PDF/DOCX.
- Saved result artifacts lacked reliable figure linkage.
- Project save/load did not consistently carry figure payloads forward.

### Repro steps

1. Run real Dash app (`python -m dash_app.server`) on branch `web-dash-plotly-migration`.
2. Execute analysis and save result.
3. Export report (DOCX/PDF) and inspect figure presence.
4. Save/load project and check `figure_count` + result artifacts linkage.

### Likely cause

Shared figure persistence depended too heavily on UI capture callback success; backend save path did not guarantee figure registration at result-save time.

### Files involved

- `backend/app.py`
- `core/figure_render.py`
- `dash_app/components/analysis_page.py`
- `dash_app/pages/dta.py`

### Next check

Monitor for regressions in additional modalities during future Dash slices.

---

## BUG-003 — Branding logo upload lacked immediate pre-save feedback

### Title

No immediate UI confirmation after logo selection before Save Branding

### Status

**Closed**

### Symptoms

- Selecting a logo file showed no visible uploaded/selected state until Save Branding completed.

### Repro steps

1. Open Export page branding panel.
2. Select a logo file in upload control.
3. Observe no pending selection indicator before saving.

### Likely cause

Preview area was populated only by backend-loaded persisted branding state; no callback rendered pending upload contents.

### Files involved

- `dash_app/pages/export.py`

### Next check

Keep pending/saved branding distinction consistent if additional branding fields get staged UI behavior.
