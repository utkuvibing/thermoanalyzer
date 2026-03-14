"""TGA Analysis page - Full TGA processing pipeline with interactive controls.

Tabs:
    Raw Data        - TGA curve (mass % vs temperature) with dataset info.
    Smoothing / DTG - Apply smoothing and inspect the DTG overlay.
    Step Analysis   - Auto-detect mass-loss steps and review the annotated plot.
    Results Summary - Review summary metrics and save stable results.
"""

import pandas as pd
import streamlit as st

from core.processing_schema import (
    ensure_processing_payload,
    get_tga_unit_modes,
    get_workflow_templates,
    set_tga_unit_mode,
    set_workflow_template,
    update_tga_unit_context,
    update_method_context,
    update_processing_step,
)
from core.preprocessing import compute_derivative, smooth_signal
from core.provenance import build_calibration_reference_context, build_result_provenance
from core.result_serialization import serialize_tga_result
from core.tga_processor import TGAProcessor, TGAResult, resolve_tga_unit_interpretation
from core.validation import validate_thermal_dataset
from ui.components.chrome import render_page_header
from ui.components.history_tracker import _log_event
from ui.components.plot_builder import (
    PLOTLY_CONFIG,
    THERMAL_COLORS,
    create_thermal_plot,
    create_tga_plot,
    fig_to_bytes,
)
from ui.components.preset_manager import render_processing_preset_panel
from ui.components.quality_dashboard import render_quality_dashboard
from ui.components.workflow_guide import render_tga_workflow_guide
from utils.diagnostics import record_exception
from utils.i18n import t, tx
from utils.license_manager import APP_VERSION
from utils.reference_data import render_reference_comparison
from utils.session_state import (
    advance_analysis_render_revision,
    init_analysis_state_history,
    push_analysis_undo_snapshot,
    redo_analysis_state,
    reset_analysis_state,
    undo_analysis_state,
)


def _chart_key(selected_key, slot, state):
    return f"tga_chart_{selected_key}_{slot}_{state.get('_render_revision', 0)}"


def _plot_with_status(fig, status_text, *, chart_key):
    """Render a plotly chart followed by a status bar."""
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG, key=chart_key)
    st.markdown(
        f'<div class="status-bar">{status_text}</div>',
        unsafe_allow_html=True,
    )


def _get_tga_datasets():
    """Return datasets suitable for TGA analysis (TGA type or unknown)."""
    datasets = st.session_state.get("datasets", {})
    return {k: v for k, v in datasets.items() if v.data_type in ("TGA", "UNKNOWN", "unknown")}


def _format_opt(value, fmt=".2f", suffix=""):
    """Format an optional float for display; return 'N/A' when None."""
    if value is None:
        return tx("Yok", "N/A")
    return f"{value:{fmt}}{suffix}"


def _create_localized_tga_plot(temperature, mass_signal, dataset, title, dtg=None, steps=None):
    """Build a TGA figure with localized labels."""
    temp_unit = dataset.units.get("temperature", "°C")
    mass_unit = dataset.units.get("signal", "%")
    return create_tga_plot(
        temperature,
        mass_signal,
        title=title,
        dtg=dtg,
        steps=steps,
        x_label=tx(f"Sıcaklık ({temp_unit})", f"Temperature ({temp_unit})"),
        y_label=tx(f"Kütle ({mass_unit})", f"Mass ({mass_unit})"),
        mass_name=tx(f"TGA (Kütle {mass_unit})", f"TGA (Mass {mass_unit})"),
        dtg_name="DTG",
        dtg_label="DTG (%/°C)",
        step_prefix=tx("Adım", "Step"),
    )


def _select_tga_reference_temperature(result):
    """Return the best available TGA step temperature for reference checking."""
    steps = getattr(result, "steps", []) or []
    if steps:
        return getattr(steps[0], "midpoint_temperature", None) or getattr(steps[0], "onset_temperature", None)
    return None


def _resolve_tga_processing_with_unit_context(processing, dataset):
    """Attach resolved TGA unit-mode context to the standardized processing payload."""
    method_context = (processing or {}).get("method_context") or {}
    unit_context = resolve_tga_unit_interpretation(
        dataset.data["signal"].values,
        unit_mode=method_context.get("tga_unit_mode_declared") or "auto",
        signal_unit=(dataset.units or {}).get("signal"),
        initial_mass_mg=dataset.metadata.get("sample_mass"),
    )
    return update_tga_unit_context(processing, unit_context), unit_context


def _store_tga_result(selected_key, dataset, temperature, mass_signal, result):
    """Persist the normalized TGA result record and linked figure."""
    figures = st.session_state.setdefault("figures", {})
    figure_key = f"TGA Analysis - {selected_key}"
    figure_keys = []
    fig_save = _create_localized_tga_plot(
        temperature,
        result.smoothed_signal if result.smoothed_signal is not None else mass_signal,
        dataset,
        title=tx("TGA Analizi - {dataset}", "TGA Analysis - {dataset}", dataset=selected_key),
        dtg=result.dtg_signal,
        steps=result.steps,
    )
    try:
        figures[figure_key] = fig_to_bytes(fig_save)
        figure_keys.append(figure_key)
    except Exception:
        pass
    calibration_context = build_calibration_reference_context(
        dataset=dataset,
        analysis_type="TGA",
        reference_temperature_c=_select_tga_reference_temperature(result),
    )
    processing_payload, unit_context = _resolve_tga_processing_with_unit_context(
        (st.session_state.get(f"tga_state_{selected_key}", {}) or {}).get("processing"),
        dataset,
    )
    processing_payload = update_method_context(
        processing_payload,
        calibration_context,
        analysis_type="TGA",
    )
    st.session_state.setdefault(f"tga_state_{selected_key}", {})["processing"] = processing_payload

    record = serialize_tga_result(
        selected_key,
        dataset,
        result,
        artifacts={"figure_keys": figure_keys},
        processing=processing_payload,
        provenance=build_result_provenance(
            dataset=dataset,
            dataset_key=selected_key,
            analysis_history=st.session_state.get("analysis_history", []),
            app_version=APP_VERSION,
            analyst_name=(st.session_state.get("branding", {}) or {}).get("analyst_name"),
            extra={
                "calibration_state": calibration_context.get("calibration_state"),
                "reference_state": calibration_context.get("reference_state"),
                "reference_name": calibration_context.get("reference_name"),
                "reference_delta_c": calibration_context.get("reference_delta_c"),
                "tga_unit_mode_declared": unit_context.get("declared_unit_mode"),
                "tga_unit_mode_resolved": unit_context.get("resolved_unit_mode"),
                "tga_unit_auto_inference_used": unit_context.get("auto_inference_used"),
            },
        ),
        validation=validate_thermal_dataset(dataset, analysis_type="TGA", processing=processing_payload),
        review={"commercial_scope": "stable_tga"},
    )
    st.session_state.setdefault("results", {})[record["id"]] = record


def render():
    render_page_header(t("tga.title"), t("tga.caption"))
    render_tga_workflow_guide()

    tga_datasets = _get_tga_datasets()
    if not tga_datasets:
        st.warning(
            tx(
                "Yüklü TGA veri seti yok. Veri yüklemek için Veri Al sayfasına gidin.",
                "No TGA datasets loaded. Go to Import Runs to load data.",
            )
        )
        return

    selected_key = st.selectbox(
        tx("Veri Seti Seç", "Select Dataset"),
        list(tga_datasets.keys()),
        key="tga_dataset_select",
    )
    dataset = tga_datasets[selected_key]
    state_key = f"tga_state_{selected_key}"
    default_state = {
        "smoothed": None,
        "dtg": None,
        "tga_result": None,
        "processing": ensure_processing_payload(analysis_type="TGA", workflow_template="General TGA"),
    }
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            **default_state,
        }
    state = st.session_state[state_key]
    init_analysis_state_history(state)
    state["processing"] = ensure_processing_payload(state.get("processing"), analysis_type="TGA")
    workflow_catalog = get_workflow_templates("TGA")
    workflow_labels = {
        "tga.general": tx("Genel TGA", "General TGA"),
        "tga.single_step_decomposition": tx("Tek Adımlı Ayrışma", "Single-Step Decomposition"),
        "tga.multi_step_decomposition": tx("Çok Adımlı Ayrışma", "Multi-Step Decomposition"),
    }
    for entry in workflow_catalog:
        workflow_labels.setdefault(entry["id"], entry["label"])
    workflow_options = list(workflow_labels.keys())
    current_template = state["processing"].get("workflow_template_id")
    template_index = workflow_options.index(current_template) if current_template in workflow_options else 0
    workflow_template_id = st.selectbox(
        tx("İş Akışı Şablonu", "Workflow Template"),
        workflow_options,
        format_func=lambda template_id: workflow_labels.get(template_id, template_id),
        index=template_index,
        key=f"tga_template_{selected_key}",
    )
    state["processing"] = set_workflow_template(
        state.get("processing"),
        workflow_template_id,
        analysis_type="TGA",
        workflow_template_label=workflow_labels.get(workflow_template_id),
    )
    render_processing_preset_panel(
        analysis_type="TGA",
        state=state,
        key_prefix=f"tga_presets_{selected_key}",
        workflow_select_key=f"tga_template_{selected_key}",
    )
    unit_mode_catalog = get_tga_unit_modes()
    unit_mode_labels = {
        "auto": tx("Otomatik", "Auto"),
        "percent": tx("Yüzde", "Percent"),
        "absolute_mass": tx("Mutlak Kütle", "Absolute Mass"),
    }
    current_unit_mode = (state["processing"].get("method_context") or {}).get("tga_unit_mode_declared", "auto")
    unit_mode_options = [entry["id"] for entry in unit_mode_catalog]
    unit_mode_index = unit_mode_options.index(current_unit_mode) if current_unit_mode in unit_mode_options else 0
    selected_unit_mode = st.selectbox(
        tx("Birim Modu", "Unit Mode"),
        unit_mode_options,
        format_func=lambda mode: unit_mode_labels.get(mode, mode),
        index=unit_mode_index,
        key=f"tga_unit_mode_{selected_key}",
        help=tx(
            "Otomatik mod mevcut unit bilgisini ve sinyal aralığını kullanır. Belirsiz düşük aralıklı TGA verilerinde açık seçim önerilir.",
            "Auto mode uses any recorded unit plus the signal range. Choose an explicit mode for low-range or ambiguous TGA signals.",
        ),
    )
    state["processing"] = set_tga_unit_mode(
        state.get("processing"),
        selected_unit_mode,
        unit_mode_label=unit_mode_labels.get(selected_unit_mode),
    )
    state["processing"], unit_context = _resolve_tga_processing_with_unit_context(state.get("processing"), dataset)

    dataset_validation = validate_thermal_dataset(dataset, analysis_type="TGA", processing=state.get("processing"))
    if dataset_validation["status"] == "fail":
        st.error(tx("Veri seti kararlı TGA iş akışına alınmadı: ", "Dataset is blocked from the stable TGA workflow: ") + "; ".join(dataset_validation["issues"]))
        return
    if dataset_validation["warnings"]:
        with st.expander(tx("Veri Doğrulama", "Dataset Validation"), expanded=False):
            for warning in dataset_validation["warnings"]:
                st.warning(warning)

    temperature = dataset.data["temperature"].values
    mass_signal = dataset.data["signal"].values
    temp_unit = dataset.units.get("temperature", "°C")
    mass_unit = dataset.units.get("signal", "%")
    tracked_keys = tuple(default_state.keys())

    undo_count = len(state.get("_undo_stack", []))
    redo_count = len(state.get("_redo_stack", []))
    control_cols = st.columns([1, 1, 1, 3])
    with control_cols[0]:
        if st.button(tx("Geri Al", "Undo"), key=f"tga_undo_{selected_key}", disabled=undo_count == 0):
            if undo_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("İşlem Geri Alındı", "Undo Applied"),
                    tx("TGA görünümü bir önceki adıma döndürüldü.", "TGA view restored to the previous step."),
                    t("tga.title"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[1]:
        if st.button(tx("İleri Al", "Redo"), key=f"tga_redo_{selected_key}", disabled=redo_count == 0):
            if redo_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("İşlem İleri Alındı", "Redo Applied"),
                    tx("TGA görünümü bir sonraki adıma taşındı.", "TGA view advanced to the next step."),
                    t("tga.title"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[2]:
        if st.button(tx("Varsayılana Dön", "Reset to Default"), key=f"tga_reset_{selected_key}"):
            if reset_analysis_state(state, default_state):
                advance_analysis_render_revision(state)
                _log_event(
                    tx("Varsayılana Dönüldü", "Reset to Default"),
                    tx("TGA işlem durumu temizlendi.", "TGA processing state was cleared."),
                    t("tga.title"),
                    dataset_key=selected_key,
                )
                st.rerun()
    with control_cols[3]:
        st.caption(
            tx(
                "Geçmiş: {undo} geri alınabilir, {redo} ileri alınabilir.",
                "History: {undo} undo available, {redo} redo available.",
                undo=undo_count,
                redo=redo_count,
            )
        )

    tab_raw, tab_smooth, tab_steps, tab_results = st.tabs(
        [
            tx("Ham Veri", "Raw Data"),
            tx("Yumuşatma / DTG", "Smoothing / DTG"),
            tx("Adım Analizi", "Step Analysis"),
            tx("Sonuç Özeti", "Results Summary"),
        ]
    )

    with tab_raw:
        st.subheader(tx("Ham TGA Verisi", "Raw TGA Data"))

        fig = _create_localized_tga_plot(
            temperature,
            mass_signal,
            dataset,
            title=tx("Ham TGA - {name}", "Raw TGA - {name}", name=dataset.metadata.get("file_name", "")),
        )
        _plot_with_status(
            fig,
            tx(
                "Aralık: {t_min:.1f} - {t_max:.1f} {temp_unit} &nbsp;|&nbsp; Nokta: {points:,} &nbsp;|&nbsp; Kütle: {mass_min:.2f} - {mass_max:.2f} {mass_unit}",
                "Range: {t_min:.1f} - {t_max:.1f} {temp_unit} &nbsp;|&nbsp; Points: {points:,} &nbsp;|&nbsp; Mass: {mass_min:.2f} - {mass_max:.2f} {mass_unit}",
                t_min=float(temperature.min()),
                t_max=float(temperature.max()),
                temp_unit=temp_unit,
                points=len(temperature),
                mass_min=float(mass_signal.min()),
                mass_max=float(mass_signal.max()),
                mass_unit=mass_unit,
            ),
            chart_key=_chart_key(selected_key, "raw", state),
        )

        render_quality_dashboard(temperature, mass_signal, key_prefix=f"tga_qd_{selected_key}")

        col_info, col_meta = st.columns(2)

        with col_info:
            t_min = float(temperature.min())
            t_max = float(temperature.max())
            st.write(
                f"**{tx('Sıcaklık aralığı', 'Temperature range')}:** "
                f"{t_min:.1f} - {t_max:.1f} {temp_unit}"
            )
            st.write(f"**{tx('Veri noktası', 'Data points')}:** {len(temperature)}")

            mass_min = float(mass_signal.min())
            mass_max = float(mass_signal.max())
            total_raw_loss = mass_max - mass_min
            st.write(
                f"**{tx('Kütle aralığı', 'Mass range')}:** "
                f"{mass_min:.2f} - {mass_max:.2f} {mass_unit}"
            )
            st.write(
                f"**{tx('Görünen toplam kütle değişimi', 'Apparent total mass change')}:** "
                f"{total_raw_loss:.2f} {mass_unit}"
            )

        with col_meta:
            sample_name = dataset.metadata.get("sample_name") or tx("Yok", "N/A")
            sample_mass = dataset.metadata.get("sample_mass")
            heating_rate = dataset.metadata.get("heating_rate")
            instrument = dataset.metadata.get("instrument") or tx("Yok", "N/A")

            st.write(f"**{tx('Numune adı', 'Sample name')}:** {sample_name}")
            if sample_mass:
                st.write(f"**{tx('Numune kütlesi', 'Sample mass')}:** {sample_mass} mg")
            if heating_rate:
                st.write(f"**{tx('Isıtma hızı', 'Heating rate')}:** {heating_rate} °C/min")
            st.write(f"**{tx('Cihaz', 'Instrument')}:** {instrument}")

    with tab_smooth:
        st.subheader(tx("Yumuşatma ve DTG", "Smoothing and DTG"))
        st.caption(
            tx(
                "Bu sekme ham kütle eğrisini yumuşatır ve türevini alarak DTG üst bindirmesini üretir.",
                "This tab smooths the raw mass curve and computes the derivative for DTG overlay inspection.",
            )
        )

        col_ctrl, col_plot = st.columns([1, 3])

        with col_ctrl:
            smooth_method = st.selectbox(
                tx("Yumuşatma Yöntemi", "Smoothing Method"),
                ["savgol", "moving_average", "gaussian"],
                key="tga_smooth_method",
                help=tx(
                    "Savitzky-Golay adım kenarlarını daha iyi korur. Moving average en basit seçenektir. Gaussian çok gürültülü veride yararlıdır.",
                    "Savitzky-Golay preserves step edges best. Moving average is simplest. Gaussian is useful for very noisy data.",
                ),
            )

            if smooth_method == "savgol":
                sg_window = st.slider(
                    tx("Pencere Uzunluğu", "Window Length"),
                    5,
                    51,
                    11,
                    step=2,
                    key="tga_sg_window",
                    help=tx(
                        "Yumuşatma penceresindeki nokta sayısı. Daha büyük değerler daha agresif yumuşatma yapar ancak adım kenarlarını bozabilir.",
                        "Number of points in the smoothing window. Larger values smooth more aggressively but can distort step edges.",
                    ),
                )
                sg_poly = st.slider(
                    tx("Polinom Derecesi", "Polynomial Order"),
                    1,
                    7,
                    3,
                    key="tga_sg_poly",
                    help=tx(
                        "Savitzky-Golay uyumu için kullanılan polinom derecesi. Daha yüksek dereceler keskin özellikleri daha iyi izler.",
                        "Polynomial degree used by the Savitzky-Golay fit. Higher orders follow sharper features more closely.",
                    ),
                )
                smooth_kwargs = {"window_length": sg_window, "polyorder": sg_poly}
            elif smooth_method == "moving_average":
                ma_window = st.slider(
                    tx("Pencere Boyutu", "Window Size"),
                    3,
                    51,
                    11,
                    step=2,
                    key="tga_ma_window",
                    help=tx(
                        "Ortalamaya alınan nokta sayısı. Daha büyük pencere daha pürüzsüz sonuç üretir.",
                        "Number of points included in the moving average. Larger windows produce smoother curves.",
                    ),
                )
                smooth_kwargs = {"window": ma_window}
            else:
                gauss_sigma = st.slider(
                    "Sigma",
                    0.5,
                    10.0,
                    2.0,
                    step=0.5,
                    key="tga_gauss_sigma",
                    help=tx(
                        "Gaussian çekirdeğinin standart sapması. Yüksek değerler daha güçlü yumuşatma uygular.",
                        "Standard deviation of the Gaussian kernel. Higher values apply stronger smoothing.",
                    ),
                )
                smooth_kwargs = {"sigma": gauss_sigma}

            show_dtg = st.checkbox(tx("DTG üst bindirmesini göster", "Show DTG overlay"), value=True, key="tga_show_dtg")
            smooth_dtg_extra = st.checkbox(
                tx("DTG sinyalini ek olarak yumuşat", "Smooth DTG signal"),
                value=True,
                key="tga_smooth_dtg",
            )

            if st.button(tx("Yumuşatmayı Uygula", "Apply Smoothing"), key="tga_apply_smooth"):
                try:
                    smoothed = smooth_signal(mass_signal, method=smooth_method, **smooth_kwargs)
                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["smoothed"] = smoothed
                    _log_event(
                        tx("Yumuşatma Uygulandı", "Smoothing Applied"),
                        f"{tx('Yöntem', 'Method')}: {smooth_method}",
                        t("tga.title"),
                        dataset_key=selected_key,
                        parameters={"method": smooth_method, **smooth_kwargs},
                    )

                    dtg = compute_derivative(temperature, smoothed, order=1, smooth_first=False)
                    if smooth_dtg_extra:
                        dtg = smooth_signal(dtg, method="savgol", window_length=11, polyorder=3)
                    state["dtg"] = dtg
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "smoothing",
                        {
                            "method": smooth_method,
                            "show_dtg": show_dtg,
                            "smooth_dtg": smooth_dtg_extra,
                            **smooth_kwargs,
                        },
                        analysis_type="TGA",
                    )
                    advance_analysis_render_revision(state)
                    st.success(tx("Yumuşatma uygulandı. DTG hesaplandı.", "Smoothing applied. DTG computed."))
                except Exception as exc:
                    error_id = record_exception(
                        st.session_state,
                        area="tga_analysis",
                        action="smoothing",
                        message="TGA smoothing failed.",
                        context={"dataset_key": selected_key, "method": smooth_method},
                        exception=exc,
                    )
                    st.error(tx("Yumuşatma başarısız oldu: {error}", "Smoothing failed: {error}", error=f"{exc} (Error ID: {error_id})"))

        with col_plot:
            smoothed_for_plot = state.get("smoothed")
            dtg_for_plot = state.get("dtg") if show_dtg else None

            fig = _create_localized_tga_plot(
                temperature,
                mass_signal if smoothed_for_plot is None else smoothed_for_plot,
                dataset,
                title=tx("DTG Üst Bindirmeli TGA", "TGA with DTG Overlay"),
                dtg=dtg_for_plot,
            )

            if smoothed_for_plot is not None:
                import plotly.graph_objects as go

                fig.add_trace(
                    go.Scatter(
                        x=temperature,
                        y=mass_signal,
                        mode="lines",
                        name=tx("Ham Veri", "Raw"),
                        line=dict(color="#CCCCCC", width=1),
                        opacity=0.5,
                    ),
                    **({"secondary_y": False} if dtg_for_plot is not None else {}),
                )

            st.plotly_chart(
                fig,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "smoothing", state),
            )

        if not show_dtg and state.get("dtg") is not None:
            fig_dtg = create_thermal_plot(
                temperature,
                state["dtg"],
                title=tx("DTG Eğrisi (dm/dT)", "DTG Curve (dm/dT)"),
                x_label=tx(f"Sıcaklık ({temp_unit})", f"Temperature ({temp_unit})"),
                y_label="DTG (%/°C)",
                color=THERMAL_COLORS[1],
            )
            st.plotly_chart(
                fig_dtg,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "dtg_only", state),
            )

    with tab_steps:
        st.subheader(tx("Kütle Kaybı Adım Tespiti", "Mass-Loss Step Detection"))
        st.caption(
            tx(
                "Adım tespiti DTG piklerini kullanır ve onset/midpoint/endset sıcaklıklarını otomatik çıkarır.",
                "Step detection uses DTG peaks to estimate onset, midpoint, and endset temperatures automatically.",
            )
        )

        col_ctrl2, col_plot2 = st.columns([1, 3])

        with col_ctrl2:
            st.markdown(f"**{tx('Tespit Parametreleri', 'Detection Parameters')}**")

            prominence_input = st.number_input(
                tx("DTG Belirginliği (0 = otomatik)", "DTG Prominence (0 = auto)"),
                value=0.0,
                min_value=0.0,
                format="%.4f",
                key="tga_prominence",
                help=tx(
                    "Bir adımın algılanması için gereken minimum DTG pik belirginliği. 0 girildiğinde eşik maksimum DTG değerinin %5'i olarak uyarlanır.",
                    "Minimum DTG peak prominence required to detect a step. When set to 0, an adaptive threshold of 5% of the max DTG value is used.",
                ),
            )

            min_mass_loss = st.number_input(
                tx("Minimum Kütle Kaybı (%)", "Min Mass Loss (%)"),
                value=0.5,
                min_value=0.0,
                max_value=100.0,
                format="%.2f",
                key="tga_min_mass_loss",
                help=tx(
                    "Bu eşikten küçük kütle değişimleri atılır. Küçük artefaktları filtrelemek için artırın.",
                    "Mass changes smaller than this threshold are discarded. Increase it to filter minor artifacts.",
                ),
            )

            st.markdown(f"**{tx('Adım Tespiti için Yumuşatma', 'Smoothing for Step Detection')}**")
            step_smooth_method = st.selectbox(
                tx("Yumuşatma Yöntemi", "Smoothing Method"),
                ["savgol", "moving_average", "gaussian"],
                key="tga_step_smooth_method",
            )
            step_sg_window = st.slider(
                tx("Pencere Uzunluğu", "Window Length"),
                5,
                51,
                11,
                step=2,
                key="tga_step_sg_window",
            )
            step_sg_poly = st.slider(
                tx("Polinom Derecesi", "Polynomial Order"),
                1,
                7,
                3,
                key="tga_step_sg_poly",
            )

            initial_mass = dataset.metadata.get("sample_mass")

            if st.button(tx("Adımları Algıla", "Detect Steps"), key="tga_detect_steps"):
                prom_kwarg = prominence_input if prominence_input > 0.0 else None
                try:
                    step_smooth_kwargs = {}
                    if step_smooth_method == "savgol":
                        step_smooth_kwargs = {
                            "window_length": step_sg_window,
                            "polyorder": step_sg_poly,
                        }

                    processor = TGAProcessor(
                        temperature,
                        mass_signal,
                        initial_mass_mg=initial_mass,
                        metadata=dataset.metadata,
                        unit_mode=str(unit_context["resolved_unit_mode"]),
                        signal_unit=dataset.units.get("signal"),
                    )
                    result: TGAResult = processor.process(
                        smooth_method=step_smooth_method,
                        smooth_dtg=True,
                        prominence=prom_kwarg,
                        min_mass_loss=min_mass_loss,
                        **step_smooth_kwargs,
                    )
                    push_analysis_undo_snapshot(state, tracked_keys)
                    state["tga_result"] = result
                    state["smoothed"] = result.smoothed_signal
                    state["dtg"] = result.dtg_signal
                    state["processing"] = update_processing_step(
                        state.get("processing"),
                        "step_detection",
                        {
                            "method": step_smooth_method,
                            "prominence": prom_kwarg,
                            "min_mass_loss": min_mass_loss,
                            **step_smooth_kwargs,
                        },
                        analysis_type="TGA",
                    )
                    advance_analysis_render_revision(state)

                    n_steps = len(result.steps)
                    _log_event(
                        tx("Adımlar Algılandı", "Steps Detected"),
                        tx(
                            "{count} adım, toplam kayıp: {loss:.2f}%",
                            "{count} step(s), total loss: {loss:.2f}%",
                            count=n_steps,
                            loss=result.total_mass_loss_percent,
                        ),
                        t("tga.title"),
                        dataset_key=selected_key,
                        parameters={"step_count": n_steps, "prominence": prom_kwarg, "min_mass_loss": min_mass_loss},
                    )
                    st.success(
                        tx(
                            "{count} adım algılandı. Toplam kütle kaybı: {loss:.2f} % | Kalıntı: {residue:.2f} %",
                            "Detected {count} step(s). Total mass loss: {loss:.2f} % | Residue: {residue:.2f} %",
                            count=n_steps,
                            loss=result.total_mass_loss_percent,
                            residue=result.residue_percent,
                        )
                    )
                except Exception as exc:
                    error_id = record_exception(
                        st.session_state,
                        area="tga_analysis",
                        action="step_detection",
                        message="TGA step detection failed.",
                        context={"dataset_key": selected_key, "method": step_smooth_method},
                        exception=exc,
                    )
                    st.error(
                        tx(
                            "Adım tespiti başarısız oldu: {error}",
                            "Step detection failed: {error}",
                            error=f"{exc} (Error ID: {error_id})",
                        )
                    )

        with col_plot2:
            result = state.get("tga_result")

            if result is not None:
                smoothed_display = result.smoothed_signal
                dtg_display = result.dtg_signal
                steps_display = result.steps if result.steps else None
            else:
                smoothed_display = state.get("smoothed")
                dtg_display = state.get("dtg")
                steps_display = None

            fig_steps = _create_localized_tga_plot(
                temperature,
                mass_signal if smoothed_display is None else smoothed_display,
                dataset,
                title=tx("Adım Tespiti", "Step Detection"),
                dtg=dtg_display,
                steps=steps_display,
            )
            st.plotly_chart(
                fig_steps,
                use_container_width=True,
                config=PLOTLY_CONFIG,
                key=_chart_key(selected_key, "steps", state),
            )

        if state.get("tga_result") is not None:
            result = state["tga_result"]
            if result.steps:
                st.subheader(tx("Algılanan Adımlar", "Detected Steps"))
                rows = []
                for i, step in enumerate(result.steps):
                    row = {
                        tx("Adım #", "Step #"): i + 1,
                        tx("Başlangıç T (°C)", "Onset T (°C)"): f"{step.onset_temperature:.1f}",
                        tx("Orta Nokta T (°C)", "Midpoint T (°C)"): f"{step.midpoint_temperature:.1f}",
                        tx("Bitiş T (°C)", "Endset T (°C)"): f"{step.endset_temperature:.1f}",
                        tx("Kütle Kaybı (%)", "Mass Loss (%)"): f"{step.mass_loss_percent:.2f}",
                        tx("Kalıntı (%)", "Residue (%)"): _format_opt(step.residual_percent, ".2f"),
                    }
                    if step.mass_loss_mg is not None:
                        row[tx("Kütle Kaybı (mg)", "Mass Loss (mg)")] = f"{step.mass_loss_mg:.3f}"
                    rows.append(row)

                df_steps = pd.DataFrame(rows)
                st.dataframe(df_steps, use_container_width=True, hide_index=True)
            else:
                st.info(
                    tx(
                        "Mevcut parametrelerle adım bulunamadı. Belirginlik veya minimum kütle kaybı eşiğini düşürmeyi deneyin.",
                        "No steps detected with the current parameters. Try lowering the prominence or minimum mass-loss threshold.",
                    )
                )

    with tab_results:
        st.subheader(tx("Analiz Özeti", "Analysis Summary"))

        result = state.get("tga_result")
        if result is None:
            st.info(
                tx(
                    "Burada sonuç görmek için önce Adım Analizi sekmesinde tespiti çalıştırın.",
                    "Run step detection first in the Step Analysis tab to see results here.",
                )
            )
            return

        st.markdown(f"**{tx('Veri seti', 'Dataset')}:** {dataset.metadata.get('file_name', selected_key)}")
        st.markdown(f"**{tx('Numune', 'Sample')}:** {dataset.metadata.get('sample_name') or tx('Yok', 'N/A')}")
        if dataset.metadata.get("sample_mass"):
            st.markdown(f"**{tx('Kütle', 'Mass')}:** {dataset.metadata['sample_mass']} mg")
        if dataset.metadata.get("heating_rate"):
            st.markdown(f"**{tx('Isıtma Hızı', 'Heating Rate')}:** {dataset.metadata['heating_rate']} °C/min")
        if dataset.metadata.get("atmosphere"):
            st.markdown(f"**{tx('Atmosfer', 'Atmosphere')}:** {dataset.metadata['atmosphere']}")

        st.divider()

        ov1, ov2, ov3 = st.columns(3)
        ov1.metric(tx("Toplam Kütle Kaybı", "Total Mass Loss"), f"{result.total_mass_loss_percent:.2f} %")
        ov2.metric(tx("Son Kalıntı", "Final Residue"), f"{result.residue_percent:.2f} %")
        ov3.metric(tx("Algılanan Adım", "Steps Detected"), str(len(result.steps)))

        st.divider()

        if result.steps:
            for i, step in enumerate(result.steps):
                st.markdown(f"### {tx('Adım', 'Step')} {i + 1}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(tx("Başlangıç T", "Onset T"), f"{step.onset_temperature:.1f} °C")
                c2.metric(tx("Orta Nokta T", "Midpoint T"), f"{step.midpoint_temperature:.1f} °C")
                c3.metric(tx("Bitiş T", "Endset T"), f"{step.endset_temperature:.1f} °C")
                c4.metric(tx("Kütle Kaybı", "Mass Loss"), f"{step.mass_loss_percent:.2f} %")
                ref_info = render_reference_comparison(step.midpoint_temperature, "TGA")
                if ref_info:
                    st.markdown(ref_info)

                d1, d2 = st.columns(2)
                d1.metric(
                    tx("Adım sonrası kalıntı", "Residue after step"),
                    _format_opt(step.residual_percent, ".2f", " %"),
                )
                if step.mass_loss_mg is not None:
                    d2.metric(tx("Mutlak kütle kaybı", "Mass Loss (abs)"), f"{step.mass_loss_mg:.3f} mg")
        else:
            st.info(tx("Kütle kaybı adımı bulunamadı.", "No mass-loss steps were detected."))

        st.divider()

        if st.button(tx("Sonuçları Oturuma Kaydet", "Save Results to Session"), key="tga_save_results"):
            try:
                _store_tga_result(selected_key, dataset, temperature, mass_signal, result)
                _log_event(tx("Sonuçlar Kaydedildi", "Results Saved"), tx("Kararlı TGA sonucu kaydedildi", "Stable TGA result saved"), t("tga.title"), dataset_key=selected_key, result_id=f"tga_{selected_key}")
                st.success(
                    tx(
                        "Kararlı TGA sonuçları kaydedildi. İndirmek için Rapor Merkezi'ne geçin.",
                        "Stable TGA results saved. Go to Report Center to download.",
                    )
                )
            except Exception as exc:
                error_id = record_exception(
                    st.session_state,
                    area="tga_analysis",
                    action="save_results",
                    message="Saving TGA results failed.",
                    context={"dataset_key": selected_key},
                    exception=exc,
                )
                st.error(
                    tx(
                        "Sonuç kaydı başarısız oldu: {error}",
                        "Saving results failed: {error}",
                        error=f"{exc} (Error ID: {error_id})",
                    )
                )
