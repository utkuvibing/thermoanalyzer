import numpy as np

from utils.session_state import (
    advance_analysis_render_revision,
    init_analysis_state_history,
    push_analysis_undo_snapshot,
    redo_analysis_state,
    reset_analysis_state,
    undo_analysis_state,
)


def test_undo_restores_previous_analysis_snapshot():
    default_state = {
        "smoothed": None,
        "baseline": None,
        "corrected": None,
        "peaks": None,
    }
    state = {
        **default_state,
        "smoothed": np.array([1.0, 2.0, 3.0]),
        "corrected": np.array([0.5, 1.5, 2.5]),
    }

    init_analysis_state_history(state)
    push_analysis_undo_snapshot(state, tuple(default_state.keys()))
    state["smoothed"] = np.array([10.0, 20.0, 30.0])
    state["corrected"] = np.array([9.0, 19.0, 29.0])

    assert undo_analysis_state(state, default_state) is True
    assert np.array_equal(state["smoothed"], np.array([1.0, 2.0, 3.0]))
    assert np.array_equal(state["corrected"], np.array([0.5, 1.5, 2.5]))
    assert len(state["_redo_stack"]) == 1


def test_redo_reapplies_next_analysis_snapshot():
    default_state = {
        "smoothed": None,
        "baseline": None,
        "corrected": None,
        "peaks": None,
    }
    state = {
        **default_state,
        "smoothed": np.array([1.0, 2.0, 3.0]),
    }

    init_analysis_state_history(state)
    push_analysis_undo_snapshot(state, tuple(default_state.keys()))
    state["smoothed"] = np.array([7.0, 8.0, 9.0])
    assert undo_analysis_state(state, default_state) is True

    assert redo_analysis_state(state, default_state) is True
    assert np.array_equal(state["smoothed"], np.array([7.0, 8.0, 9.0]))
    assert len(state["_undo_stack"]) == 1


def test_reset_restores_defaults_and_clears_redo_stack():
    default_state = {
        "smoothed": None,
        "baseline": None,
        "corrected": None,
        "peaks": None,
    }
    state = {
        **default_state,
        "smoothed": np.array([4.0, 5.0, 6.0]),
        "baseline": np.array([0.1, 0.1, 0.1]),
        "_redo_stack": [{"smoothed": np.array([8.0, 9.0, 10.0]), "baseline": None, "corrected": None, "peaks": None}],
    }

    init_analysis_state_history(state)

    assert reset_analysis_state(state, default_state) is True
    assert state["smoothed"] is None
    assert state["baseline"] is None
    assert state["corrected"] is None
    assert state["peaks"] is None
    assert state["_redo_stack"] == []
    assert len(state["_undo_stack"]) == 1


def test_advance_analysis_render_revision_increments_counter():
    state = {}

    assert advance_analysis_render_revision(state) == 1
    assert advance_analysis_render_revision(state) == 2
