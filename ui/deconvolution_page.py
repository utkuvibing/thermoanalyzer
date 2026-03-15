"""Peak Deconvolution page - Fit overlapping peaks using lmfit."""

import streamlit as st
import numpy as np
import pandas as pd

from core.peak_deconvolution import deconvolve_peaks
from core.result_serialization import serialize_deconvolution_result
from ui.components.plot_builder import (
    create_deconvolution_plot,
    create_thermal_plot,
    fig_to_bytes,
    PLOTLY_CONFIG,
    THERMAL_COLORS,
)
from ui.components.history_tracker import _log_event
from utils.i18n import tx


def render():
    st.title(tx("Pik Dekonvolüsyonu", "Peak Deconvolution"))
    st.warning(
        tx(
            "Deneysel modül: dekonvolüsyon keşif amaçlı kullanılabilir, ancak Faz 1 kararlı iş akışının parçası değildir.",
            "Experimental module: deconvolution is available for exploratory work, but it is not part of the Phase 1 stable workflow.",
        )
    )
    st.markdown(
        tx(
            "Çakışan pikleri Gaussian, Lorentzian veya Pseudo-Voigt modelleri ile doğrusal olmayan en küçük kareler (lmfit) kullanarak uydurun.",
            "Fit overlapping peaks with Gaussian, Lorentzian, or Pseudo-Voigt models using non-linear least-squares (lmfit).",
        )
    )

    datasets = st.session_state.get("datasets", {})
    if not datasets:
        st.warning(tx("Henüz veri seti yüklenmedi. Önce **Veri Al** sayfasına gidin.", "No datasets loaded. Go to **Import Runs** page first."))
        return

    # ── Dataset & signal selection ──────────────────────────────────────────
    col_ds, col_sig = st.columns(2)
    with col_ds:
        selected_key = st.selectbox(
            tx("Veri Seti", "Dataset"), list(datasets.keys()), key="deconv_dataset"
        )
    dataset = datasets[selected_key]
    temperature = dataset.data["temperature"].values
    raw_signal = dataset.data["signal"].values

    # Determine available signal variants
    state_prefixes = ["dsc_state_", "dta_state_", "tga_state_"]
    signal_options = [tx("Ham Sinyal", "Raw Signal")]
    state = None
    for prefix in state_prefixes:
        s = st.session_state.get(f"{prefix}{selected_key}")
        if s:
            state = s
            break
    if state:
        if state.get("smoothed") is not None:
            signal_options.append(tx("Yumuşatılmış", "Smoothed"))
        if state.get("corrected") is not None:
            signal_options.append(tx("Baz Çizgisi Düzeltilmiş", "Baseline-Corrected"))

    with col_sig:
        sig_choice = st.selectbox(
            tx("Uydurulacak Sinyal", "Signal to fit"),
            signal_options,
            key="deconv_signal_choice",
            help=tx("Dekonvolüsyon için sinyalin hangi sürümünün kullanılacağını seçin.", "Choose which version of the signal to deconvolve."),
        )

    if sig_choice == tx("Yumuşatılmış", "Smoothed") and state:
        working_signal = state["smoothed"]
    elif sig_choice == tx("Baz Çizgisi Düzeltilmiş", "Baseline-Corrected") and state:
        working_signal = state["corrected"]
    else:
        working_signal = raw_signal

    # ── Control panel ───────────────────────────────────────────────────────
    st.divider()
    ctrl_col, plot_col = st.columns([1, 3])

    with ctrl_col:
        n_peaks = st.number_input(
            tx("Pik Sayısı", "Number of peaks"),
            min_value=1, max_value=10, value=2, step=1,
            key="deconv_n_peaks",
            help=tx("Kaç çakışan pikin uydurulacağını seçin.", "How many overlapping peaks to fit."),
        )
        peak_shape = st.selectbox(
            tx("Pik Şekli", "Peak shape"),
            ["gaussian", "lorentzian", "pseudo_voigt"],
            key="deconv_peak_shape",
            help=tx("Gaussian: simetrik çan eğrisi. Lorentzian: daha geniş kuyruklar. Pseudo-Voigt: ikisinin ağırlıklı karışımı.", "Gaussian: symmetric bell curve. Lorentzian: broader tails. Pseudo-Voigt: weighted mix of both."),
        )

        # Optional temperature range restriction
        use_range = st.checkbox(tx("Sıcaklık aralığını sınırla", "Restrict temperature range"), key="deconv_use_range")
        if use_range:
            t_min_val = float(temperature.min())
            t_max_val = float(temperature.max())
            t_range = st.slider(
                tx("Sıcaklık aralığı (°C)", "Temperature range (°C)"),
                min_value=t_min_val,
                max_value=t_max_val,
                value=(t_min_val, t_max_val),
                key="deconv_t_range",
            )
        else:
            t_range = None

        # Optional initial parameter hints
        use_hints = st.checkbox(
            tx("Başlangıç tahmini ver", "Provide initial guesses"), key="deconv_use_hints",
            help=tx("Her pik için başlangıç merkezi, genlik ve sigma değerini manuel girin.", "Manually set starting center, amplitude, sigma for each peak."),
        )
        initial_params = None
        if use_hints:
            initial_params = []
            for i in range(n_peaks):
                with st.expander(tx("Pik {index} ipuçları", "Peak {index} hints", index=i + 1), expanded=i == 0):
                    center = st.number_input(
                        tx("Merkez (°C)", "Center (°C)"), value=float(temperature.mean()),
                        key=f"deconv_center_{i}",
                    )
                    amp = st.number_input(
                        tx("Genlik", "Amplitude"), value=float(np.abs(working_signal).max() / n_peaks),
                        key=f"deconv_amp_{i}",
                    )
                    sigma = st.number_input(
                        tx("Sigma", "Sigma"), value=10.0, min_value=0.01,
                        key=f"deconv_sigma_{i}",
                    )
                    initial_params.append({"center": center, "amplitude": amp, "sigma": sigma})

        run_btn = st.button(tx("Dekonvolüsyonu Çalıştır", "Run Deconvolution"), key="deconv_run", type="primary")

    # ── Run fitting ─────────────────────────────────────────────────────────
    result_key = "deconv_result"

    if run_btn:
        x = temperature.copy()
        y = working_signal.copy()

        # Apply range restriction
        if t_range is not None:
            mask = (x >= t_range[0]) & (x <= t_range[1])
            x = x[mask]
            y = y[mask]

        if len(x) < 10:
            st.error(tx("Seçilen aralıkta yeterli veri noktası yok.", "Not enough data points in the selected range."))
        else:
            with st.spinner(tx("Pikler uyduruluyor...", "Fitting peaks...")):
                try:
                    result = deconvolve_peaks(
                        x, y, n_peaks=n_peaks,
                        peak_shape=peak_shape,
                        initial_params=initial_params,
                    )
                    # Store x used for plotting
                    result["x"] = x
                    result["y"] = y
                    st.session_state[result_key] = result
                    _log_event(
                        tx("Dekonvolüsyon", "Deconvolution"),
                        f"{n_peaks} {peak_shape} peaks, R²={result['r_squared']:.4f}",
                        tx("Pik Dekonvolüsyonu", "Peak Deconvolution"),
                    )
                    st.success(
                        tx("Uyum tamamlandı — R² = {value:.6f}", "Fit converged — R² = {value:.6f}", value=result["r_squared"])
                    )
                except Exception as exc:
                    st.error(tx("Dekonvolüsyon başarısız oldu: {error}", "Deconvolution failed: {error}", error=exc))

    # ── Display results ─────────────────────────────────────────────────────
    result = st.session_state.get(result_key)

    with plot_col:
        if result is None:
            # Show raw data preview
            fig = create_thermal_plot(
                temperature, working_signal,
                title=tx("Sinyal Önizlemesi", "Signal Preview"),
                y_label=tx("Sinyal", "Signal"),
            )
            st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)
        else:
            x = result["x"]
            y = result["y"]
            fig = create_deconvolution_plot(
                x, y, result["fitted"], result["components"],
                title=tx("Dekonvolüsyon — R² = {value:.4f}", "Deconvolution — R² = {value:.4f}", value=result["r_squared"]),
            )
            st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

    if result is None:
        return

    # ── Fit quality metrics ─────────────────────────────────────────────────
    st.divider()
    x = result["x"]
    y = result["y"]
    residual = result["residual"]

    rmse = float(np.sqrt(np.mean(residual ** 2)))
    n_params = sum(1 for k in result["params"] if not k.startswith("__"))
    dof = max(len(y) - n_params, 1)
    chi2_red = float(np.sum(residual ** 2) / dof)

    m1, m2, m3 = st.columns(3)
    m1.metric("R²", f"{result['r_squared']:.6f}")
    m2.metric("RMSE", f"{rmse:.6f}")
    m3.metric("Reduced χ²", f"{chi2_red:.6f}")

    # ── Parameter table ─────────────────────────────────────────────────────
    st.subheader(tx("Pik Parametreleri", "Peak Parameters"))
    rows = []
    params = result["params"]
    for i in range(len(result["components"])):
        prefix = f"p{i + 1}_"
        row = {
            tx("Pik", "Peak"): i + 1,
            tx("Merkez (°C)", "Center (°C)"): f"{params.get(f'{prefix}center', 0):.2f}",
            tx("Genlik", "Amplitude"): f"{params.get(f'{prefix}amplitude', 0):.4f}",
            tx("Sigma", "Sigma"): f"{params.get(f'{prefix}sigma', 0):.4f}",
        }
        if f"{prefix}fraction" in params:
            row[tx("Fraksiyon (PV)", "Fraction (PV)")] = f"{params[f'{prefix}fraction']:.4f}"
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    # ── Residual plot ───────────────────────────────────────────────────────
    with st.expander(tx("Artık Grafiği", "Residual Plot")):
        fig_res = create_thermal_plot(
            x, residual,
            title=tx("Artıklar (Veri − Uyum)", "Residuals (Data − Fit)"),
            y_label=tx("Artık", "Residual"),
            color=THERMAL_COLORS[1],
        )
        fig_res.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
        st.plotly_chart(fig_res, width="stretch", config=PLOTLY_CONFIG)

    # ── lmfit report ────────────────────────────────────────────────────────
    with st.expander(tx("Tam lmfit Raporu", "Full lmfit Report")):
        st.code(result["report"], language="text")

    # ── Save results ────────────────────────────────────────────────────────
    if st.button(tx("Sonuçları Oturuma Kaydet", "Save Results to Session"), key="deconv_save"):
        figures = st.session_state.setdefault("figures", {})
        figure_key = f"Deconvolution - {selected_key}"
        figure_keys = []
        fig_save = create_deconvolution_plot(
            x, y, result["fitted"], result["components"],
            title=tx("Dekonvolüsyon — {dataset}", "Deconvolution — {dataset}", dataset=selected_key),
        )
        try:
            figures[figure_key] = fig_to_bytes(fig_save)
            figure_keys.append(figure_key)
        except Exception:
            pass  # kaleido not available
        record = serialize_deconvolution_result(
            selected_key,
            dataset,
            result,
            peak_shape,
            artifacts={"figure_keys": figure_keys},
        )
        st.session_state.setdefault("results", {})[record["id"]] = record
        st.success(tx("Deneysel dekonvolüsyon sonuçları kaydedildi. İndirmek için Rapor Merkezi'ne gidin.", "Experimental deconvolution results saved. Go to Report Center to download."))

