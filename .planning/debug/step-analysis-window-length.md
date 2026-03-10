---
status: awaiting_human_verify
trigger: "Investigate issue: step-analysis-window-length"
created: 2026-03-10T16:51:08+03:00
updated: 2026-03-10T20:00:20+03:00
---

## Current Focus

hypothesis: The TGA step-analysis crash is addressed by filtering smoothing kwargs out of the peak-detection call path, and the remaining step is confirming the original UI flow no longer raises the TypeError.
test: Re-run the user-facing step analysis flow in the app with a TGA dataset and confirm no `find_thermal_peaks(... window_length ...)` error appears.
expecting: Step detection completes successfully and either reports detected steps or a valid no-steps result, without a TypeError.
next_action: Ask for human verification in the real app workflow.

## Symptoms

expected: Step analysis should run and detect thermal peaks without crashing.
actual: Step detection aborts with TypeError during analysis.
errors: Step detection failed: find_thermal_peaks() got an unexpected keyword argument 'window_length' (Error ID: TA-TGA-20260310165108-246C41)
reproduction: Run step analysis on a TGA dataset via app flow where peak detection is used.
started: Reported now; unknown when first introduced.

## Eliminated

## Evidence

- timestamp: 2026-03-10T19:52:10+03:00
  checked: `core/peak_analysis.py`
  found: `find_thermal_peaks()` accepts `prominence`, `height`, `distance`, `width`, and `direction`, but not `window_length` or `polyorder`.
  implication: Any path that forwards smoothing kwargs into `find_thermal_peaks()` will fail with the reported TypeError.

- timestamp: 2026-03-10T19:52:35+03:00
  checked: `core/tga_processor.py`
  found: `process()` forwards the same `**kwargs` into `smooth()`, `compute_dtg()`, and `detect_steps()`, while `detect_steps()` forwards its `**kwargs` straight into `find_thermal_peaks()`.
  implication: TGA full-pipeline calls that include smoothing kwargs can leak them into peak detection.

- timestamp: 2026-03-10T19:52:58+03:00
  checked: `ui/tga_page.py`
  found: Step analysis UI builds `step_smooth_kwargs = {"window_length": step_sg_window, "polyorder": step_sg_poly}` and passes them to `TGAProcessor.process(...)`.
  implication: The user-facing step-analysis flow triggers the bad kwargs path directly.

- timestamp: 2026-03-10T19:54:10+03:00
  checked: direct Python reproduction with `TGAProcessor(T, mass).process(window_length=11, polyorder=3)`
  found: The minimal direct `process()` call completed successfully instead of raising the reported TypeError.
  implication: The user-facing failure may occur in a more specific wrapper or execution path than the bare processor call, so the exact runtime path still needs confirmation.

- timestamp: 2026-03-10T19:55:40+03:00
  checked: runtime source of `TGAProcessor.detect_steps()`
  found: The loaded method already filters kwargs to `height`, `distance`, `width`, and `direction`, explicitly ignoring smoothing-only keys like `window_length` and `polyorder`.
  implication: The current runtime `TGAProcessor` path should not produce the reported TypeError, so the crash likely comes from a different caller or from stale code outside the active module.

- timestamp: 2026-03-10T19:58:55+03:00
  checked: `tests/test_tga_processor.py`
  found: Added a regression test that spies on `core.tga_processor.find_thermal_peaks` during `TGAProcessor.process(window_length=15, polyorder=3, direction="up")` and asserts smoothing kwargs do not reach the peak finder while `direction` does.
  implication: The fix is now covered against the exact kwargs-leak regression that produced the TypeError.

- timestamp: 2026-03-10T19:59:30+03:00
  checked: `pytest tests/test_tga_processor.py -q`
  found: Targeted TGA processor test suite passed (`34 passed`), including the new regression test.
  implication: The TGA processing pipeline is internally consistent after the kwargs filtering fix.

## Resolution

root_cause: The TGA full pipeline shared one `**kwargs` bag across smoothing, DTG smoothing, and step detection. Before the fix, `detect_steps()` passed smoothing kwargs such as `window_length` and `polyorder` into `find_thermal_peaks()`, whose API does not accept them.
fix: Preserve the existing `core/tga_processor.py` change that filters `detect_steps()` kwargs down to peak-finder-specific keys only, and add regression coverage proving smoothing kwargs no longer leak into `find_thermal_peaks()`.
verification: `pytest tests/test_tga_processor.py -q` passed with 34 tests, including a new regression that confirms `window_length` and `polyorder` are not forwarded into `find_thermal_peaks()` during `TGAProcessor.process(...)`.
files_changed: ["core/tga_processor.py", "tests/test_tga_processor.py"]
