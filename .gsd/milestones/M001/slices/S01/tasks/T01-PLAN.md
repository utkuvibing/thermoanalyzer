# T01: 01-foundation-contracts-and-execution-path 01

**Slice:** S01 — **Milestone:** M001

## Description

Establish the foundation contract and registry layer for stable modalities before touching backend routing.

Purpose: Satisfy ARCH-01 first with a concrete, testable modality interface and explicit registration model that Phase 2+ can extend.
Output: New modality contract package, DSC/TGA adapter implementations, centralized stable state-key resolver, and contract tests.

## Must-Haves

- [ ] "Stable modalities are declared in one explicit registry and expose standardized lifecycle hooks for import, preprocess, analyze, serialize, and report context."
- [ ] "DSC and TGA execute through contract adapters that reuse existing batch runner behavior without changing scientific outputs."
- [ ] "State-key resolution is centralized and deterministic for stable analysis types."

## Files

- `core/modalities/__init__.py`
- `core/modalities/contracts.py`
- `core/modalities/adapters.py`
- `core/modalities/registry.py`
- `core/modalities/state_keys.py`
- `tests/test_modality_registry.py`
