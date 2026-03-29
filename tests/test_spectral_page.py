from __future__ import annotations

from types import SimpleNamespace

from ui import spectral_page


def test_render_literature_compare_if_supported_runs_for_ftir(monkeypatch):
    captions: list[str] = []
    divider_calls: list[bool] = []
    log_calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        spectral_page,
        "st",
        SimpleNamespace(
            divider=lambda: divider_calls.append(True),
            caption=lambda text: captions.append(str(text)),
            session_state={"lang": "en"},
        ),
    )
    monkeypatch.setattr(spectral_page, "t", lambda key: key)
    monkeypatch.setattr(spectral_page, "_log_event", lambda *args, **kwargs: log_calls.append((args, kwargs)))
    monkeypatch.setattr(
        spectral_page,
        "render_literature_compare_panel",
        lambda **kwargs: (
            {**dict(kwargs["record"] or {}), "literature_context": {"comparison_run_id": "litcmp_ftir_001"}},
            {"status": "success"},
        ),
    )

    updated = spectral_page._render_literature_compare_if_supported(
        analysis_type="FTIR",
        selected_key="demo",
        record={"id": "ftir_demo"},
        title_key="ftir.title",
    )

    assert divider_calls == [True]
    assert captions
    assert updated["literature_context"]["comparison_run_id"] == "litcmp_ftir_001"
    assert log_calls
