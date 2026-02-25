"""
tga_processor.py
----------------
Thermogravimetric Analysis (TGA) processing pipeline.

TGA measures the change in mass of a sample as a function of temperature
(or time) under a controlled atmosphere.  The primary outputs are:

  - TGA curve         : mass (%) vs. temperature
  - DTG curve         : derivative of mass with respect to temperature
                        (dm/dT, %/degC).  Peaks in -DTG correspond to mass
                        loss events.
  - Mass-loss steps   : onset, endset, midpoint temperatures and the
                        percentage of mass lost in each decomposition step.

Pipeline
--------
    raw data
        -> smooth()         : noise reduction (Savitzky-Golay by default)
        -> compute_dtg()    : numerical differentiation to obtain DTG
        -> detect_steps()   : locate decomposition steps via DTG peak finding
        -> TGAResult        : structured output dataclass

Usage example
-------------
    import numpy as np
    from core.tga_processor import TGAProcessor

    temperature = np.linspace(30, 800, 2000)
    mass_percent = ...   # experimental data

    result = TGAProcessor(temperature, mass_percent).process()
    for step in result.steps:
        print(step.onset_temperature, step.mass_loss_percent)
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional

from core.preprocessing import smooth_signal, compute_derivative
from core.baseline import correct_baseline
from core.peak_analysis import find_thermal_peaks, ThermalPeak


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MassLossStep:
    """
    Represents a single decomposition / mass-loss step in a TGA experiment.

    Temperatures are in the same unit supplied to TGAProcessor (typically
    degrees Celsius).  Mass values are expressed as percentages of the
    initial sample mass.

    Attributes
    ----------
    onset_temperature : float
        Temperature at which significant mass loss begins, determined by the
        tangent intersection method on the TGA curve.
    endset_temperature : float
        Temperature at which the mass-loss step is essentially complete,
        determined by the tangent intersection method on the TGA curve.
    midpoint_temperature : float
        Midpoint of the step, taken as the temperature of the corresponding
        DTG peak (maximum rate of mass loss).
    mass_loss_percent : float
        Percentage of the *initial* sample mass lost during this step.
    mass_loss_mg : float or None
        Absolute mass lost in milligrams.  Populated only when
        ``initial_mass_mg`` is provided to TGAProcessor.
    residual_percent : float or None
        Remaining mass (as % of initial mass) immediately after the step
        ends, i.e., at ``endset_temperature``.
    dtg_peak_temperature : float or None
        Temperature of the DTG peak (same as ``midpoint_temperature`` unless
        overridden).  Stored separately for clarity.
    """

    onset_temperature: float
    endset_temperature: float
    midpoint_temperature: float
    mass_loss_percent: float
    mass_loss_mg: Optional[float] = None
    residual_percent: Optional[float] = None
    dtg_peak_temperature: Optional[float] = None


@dataclass
class TGAResult:
    """
    Full results of a TGA processing run.

    Attributes
    ----------
    steps : list of MassLossStep
        Detected decomposition steps, ordered by onset temperature.
    dtg_peaks : list of ThermalPeak
        Peak objects from the DTG curve as returned by
        :func:`~core.peak_analysis.find_thermal_peaks`.
    dtg_signal : np.ndarray
        Computed DTG curve (dm/dT) in units of %/degC (or %/K), same length
        as the temperature array.
    smoothed_signal : np.ndarray
        TGA mass-% signal after smoothing.
    total_mass_loss_percent : float
        Net mass loss from the first to the last data point, expressed as a
        percentage of the initial mass.
    residue_percent : float
        Mass remaining at the end of the experiment as a percentage of the
        initial mass.
    metadata : dict
        Arbitrary key-value pairs (e.g., sample name, heating rate, units)
        passed through from the processor.
    """

    steps: List[MassLossStep]
    dtg_peaks: List[ThermalPeak]
    dtg_signal: np.ndarray
    smoothed_signal: np.ndarray
    total_mass_loss_percent: float
    residue_percent: float
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper: tangent-intersection onset / endset detection
# ---------------------------------------------------------------------------

def _find_onset_endset_tangent(
    temperature: np.ndarray,
    mass_percent: np.ndarray,
    peak_index: int,
    search_half_width: int = 80,
) -> tuple[float, float]:
    """
    Locate onset and endset temperatures for a mass-loss step using the
    tangent-line intersection method.

    The algorithm:
      1. Identify a "before-peak" plateau region to the left of the DTG peak
         and fit a tangent line to the TGA curve there.
      2. Identify the steepest descent region (around the DTG peak itself)
         and fit a tangent line to the TGA curve there.
      3. The intersection of these two tangent lines is the onset temperature.
      4. Repeat symmetrically on the right side to find the endset.

    Parameters
    ----------
    temperature : np.ndarray
        Temperature axis, monotonically increasing.
    mass_percent : np.ndarray
        TGA mass-% curve (smoothed).
    peak_index : int
        Index of the DTG peak in the arrays.
    search_half_width : int
        Number of points to consider on each side of the peak.

    Returns
    -------
    (onset_temperature, endset_temperature) : tuple of float
    """
    n = len(temperature)

    # Bounds for the search region
    left_start = max(0, peak_index - search_half_width)
    right_end = min(n - 1, peak_index + search_half_width)

    # ---- Onset (left side) ----
    # Plateau region: 20% of search_half_width points well before the peak
    plateau_width = max(5, search_half_width // 5)
    plateau_left_idx = left_start
    plateau_right_idx = min(peak_index - plateau_width, peak_index - 2)
    plateau_right_idx = max(plateau_right_idx, plateau_left_idx + 2)

    T_plateau = temperature[plateau_left_idx:plateau_right_idx]
    M_plateau = mass_percent[plateau_left_idx:plateau_right_idx]
    if len(T_plateau) >= 2:
        p_plateau = np.polyfit(T_plateau, M_plateau, 1)
    else:
        p_plateau = np.array([0.0, mass_percent[plateau_left_idx]])

    # Steepest descent region: points around peak where DTG is most negative
    steep_half = max(3, search_half_width // 8)
    steep_left = max(left_start, peak_index - steep_half)
    steep_right = min(peak_index + steep_half, right_end)

    T_steep = temperature[steep_left:steep_right]
    M_steep = mass_percent[steep_left:steep_right]
    if len(T_steep) >= 2:
        p_steep = np.polyfit(T_steep, M_steep, 1)
    else:
        p_steep = np.array([
            (mass_percent[peak_index] - mass_percent[steep_left]) /
            max(temperature[peak_index] - temperature[steep_left], 1e-6),
            mass_percent[peak_index],
        ])

    # Intersection: p_plateau[0]*T + p_plateau[1] = p_steep[0]*T + p_steep[1]
    denom = p_steep[0] - p_plateau[0]
    if abs(denom) < 1e-12:
        onset_temp = temperature[peak_index]
    else:
        T_intersect = (p_plateau[1] - p_steep[1]) / denom
        # Clamp to the left search region
        onset_temp = float(
            np.clip(T_intersect, temperature[left_start], temperature[peak_index])
        )

    # ---- Endset (right side) ----
    plateau2_left_idx = min(peak_index + plateau_width, right_end - 2)
    plateau2_right_idx = right_end
    plateau2_left_idx = min(plateau2_left_idx, plateau2_right_idx - 2)

    T_plateau2 = temperature[plateau2_left_idx:plateau2_right_idx]
    M_plateau2 = mass_percent[plateau2_left_idx:plateau2_right_idx]
    if len(T_plateau2) >= 2:
        p_plateau2 = np.polyfit(T_plateau2, M_plateau2, 1)
    else:
        p_plateau2 = np.array([0.0, mass_percent[min(plateau2_right_idx, n - 1)]])

    denom2 = p_steep[0] - p_plateau2[0]
    if abs(denom2) < 1e-12:
        endset_temp = temperature[peak_index]
    else:
        T_intersect2 = (p_plateau2[1] - p_steep[1]) / denom2
        endset_temp = float(
            np.clip(T_intersect2, temperature[peak_index], temperature[right_end])
        )

    return onset_temp, endset_temp


# ---------------------------------------------------------------------------
# TGAProcessor
# ---------------------------------------------------------------------------

class TGAProcessor:
    """
    Fluent-interface processing pipeline for TGA data.

    Each method returns ``self`` so calls can be chained:

        result = TGAProcessor(T, mass).smooth().compute_dtg().detect_steps().get_result()

    Or use the convenience :meth:`process` method which runs the full
    pipeline in one call.

    Parameters
    ----------
    temperature : array-like
        Temperature array in degrees Celsius (or Kelvin).  Must be
        monotonically increasing and match the length of ``mass_signal``.
    mass_signal : array-like
        TGA mass signal.  Accepted formats:

        - Percentage (0–100 %) – used as-is.
        - Absolute mass in milligrams – automatically converted to % when
          ``initial_mass_mg`` is provided, otherwise the first value is
          used as the 100 % reference.

    initial_mass_mg : float, optional
        Initial sample mass in milligrams.  Required to compute
        ``mass_loss_mg`` in each :class:`MassLossStep`.  If ``mass_signal``
        is in mg this value is also used for the % conversion.
    metadata : dict, optional
        Arbitrary metadata (sample name, atmosphere, heating rate, …)
        forwarded into :class:`TGAResult`.
    """

    def __init__(
        self,
        temperature,
        mass_signal,
        initial_mass_mg: Optional[float] = None,
        metadata: Optional[dict] = None,
    ):
        self._temperature = np.asarray(temperature, dtype=float)
        raw_mass = np.asarray(mass_signal, dtype=float)

        self._initial_mass_mg = initial_mass_mg
        self._metadata = metadata or {}

        # Auto-detect unit: if the maximum value is much greater than 100 the
        # signal is almost certainly in absolute mass (mg or g).
        if raw_mass.max() > 105.0:
            # Treat as absolute mass; convert to % using the initial value
            ref = initial_mass_mg if initial_mass_mg is not None else raw_mass[0]
            if ref <= 0:
                raise ValueError(
                    "Cannot convert mass signal to percent: reference mass is zero "
                    "or negative.  Supply a positive initial_mass_mg."
                )
            self._mass_percent = raw_mass / ref * 100.0
        else:
            self._mass_percent = raw_mass

        # Internal state populated by each pipeline stage
        self._smoothed: Optional[np.ndarray] = None
        self._dtg: Optional[np.ndarray] = None
        self._dtg_peaks: Optional[List[ThermalPeak]] = None
        self._steps: Optional[List[MassLossStep]] = None
        self._result: Optional[TGAResult] = None

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def smooth(self, method: str = "savgol", **kwargs) -> "TGAProcessor":
        """
        Smooth the TGA mass-% signal.

        Parameters
        ----------
        method : str, default 'savgol'
            Smoothing algorithm forwarded to
            :func:`~core.preprocessing.smooth_signal`.
            Options: ``'savgol'``, ``'moving_average'``, ``'gaussian'``.
        **kwargs
            Additional keyword arguments forwarded to the smoothing function
            (e.g., ``window_length``, ``polyorder`` for Savitzky-Golay).

        Returns
        -------
        TGAProcessor
            ``self`` for method chaining.
        """
        self._smoothed = smooth_signal(self._mass_percent, method=method, **kwargs)
        return self

    def compute_dtg(self, smooth_dtg: bool = True, **kwargs) -> "TGAProcessor":
        """
        Compute the DTG curve (dm/dT) by numerical differentiation.

        The DTG is the first derivative of mass with respect to temperature.
        Peaks in the *negative* DTG correspond to mass-loss events.

        Parameters
        ----------
        smooth_dtg : bool, default True
            Apply an additional Savitzky-Golay pass to the DTG curve to
            suppress differentiation-induced noise.
        **kwargs
            Keyword arguments forwarded to :func:`~core.preprocessing.smooth_signal`
            when ``smooth_dtg=True`` (e.g., ``window_length``, ``polyorder``).

        Returns
        -------
        TGAProcessor
            ``self`` for method chaining.

        Raises
        ------
        RuntimeError
            If :meth:`smooth` has not been called before this method.
        """
        if self._smoothed is None:
            raise RuntimeError(
                "Call smooth() before compute_dtg(), or use process() for the full pipeline."
            )

        # Use compute_derivative with smooth_first=False because the signal
        # has already been smoothed.
        dtg = compute_derivative(
            self._temperature,
            self._smoothed,
            order=1,
            smooth_first=False,
        )

        if smooth_dtg:
            window_length = kwargs.get("window_length", 11)
            polyorder = kwargs.get("polyorder", 3)
            dtg = smooth_signal(dtg, method="savgol", window_length=window_length, polyorder=polyorder)

        self._dtg = dtg
        return self

    def detect_steps(
        self,
        prominence: Optional[float] = None,
        min_mass_loss: float = 0.5,
        search_half_width: int = 80,
        **kwargs,
    ) -> "TGAProcessor":
        """
        Detect mass-loss steps by finding peaks in the negative DTG signal.

        Algorithm
        ---------
        1. Invert the DTG (multiply by -1) so mass-loss events appear as
           positive peaks.
        2. Call :func:`~core.peak_analysis.find_thermal_peaks` to locate
           peaks in ``-DTG``.
        3. For each DTG peak, apply the tangent-intersection method on the
           TGA curve to determine onset and endset temperatures.
        4. Compute ``mass_loss_percent`` as the difference in smoothed TGA
           mass between onset and endset.

        Parameters
        ----------
        prominence : float, optional
            Minimum peak prominence in %/degC.  If ``None``, defaults to
            5 % of the maximum absolute DTG value, providing an adaptive
            threshold.
        min_mass_loss : float, default 0.5
            Steps with a computed mass loss below this value (in %) are
            discarded as noise artefacts.
        search_half_width : int, default 80
            Number of data points to search on each side of a DTG peak
            when fitting tangent lines.
        **kwargs
            Additional keyword arguments forwarded to
            :func:`~core.peak_analysis.find_thermal_peaks`.

        Returns
        -------
        TGAProcessor
            ``self`` for method chaining.

        Raises
        ------
        RuntimeError
            If :meth:`compute_dtg` has not been called before this method.
        """
        if self._dtg is None:
            raise RuntimeError(
                "Call compute_dtg() before detect_steps(), or use process() for the full pipeline."
            )

        # Invert DTG: mass-loss events are negative in dm/dT but we want
        # positive peaks for find_thermal_peaks.
        neg_dtg = -self._dtg

        # Adaptive prominence if not supplied
        if prominence is None:
            prominence = max(0.005 * neg_dtg.max(), 0.01)

        # Find peaks in the inverted DTG
        dtg_peaks: List[ThermalPeak] = find_thermal_peaks(
            self._temperature,
            neg_dtg,
            prominence=prominence,
            **kwargs,
        )

        self._dtg_peaks = dtg_peaks

        steps: List[MassLossStep] = []
        for peak in dtg_peaks:
            peak_idx = int(np.argmin(np.abs(self._temperature - peak.peak_temperature)))

            onset_temp, endset_temp = _find_onset_endset_tangent(
                self._temperature,
                self._smoothed,
                peak_index=peak_idx,
                search_half_width=search_half_width,
            )

            # Mass values at onset and endset from the smoothed TGA curve
            onset_idx = int(np.argmin(np.abs(self._temperature - onset_temp)))
            endset_idx = int(np.argmin(np.abs(self._temperature - endset_temp)))

            mass_at_onset = float(self._smoothed[onset_idx])
            mass_at_endset = float(self._smoothed[endset_idx])
            mass_loss_pct = mass_at_onset - mass_at_endset  # positive value

            if mass_loss_pct < min_mass_loss:
                continue

            mass_loss_mg: Optional[float] = None
            if self._initial_mass_mg is not None:
                mass_loss_mg = mass_loss_pct / 100.0 * self._initial_mass_mg

            steps.append(
                MassLossStep(
                    onset_temperature=onset_temp,
                    endset_temperature=endset_temp,
                    midpoint_temperature=peak.peak_temperature,
                    mass_loss_percent=mass_loss_pct,
                    mass_loss_mg=mass_loss_mg,
                    residual_percent=mass_at_endset,
                    dtg_peak_temperature=peak.peak_temperature,
                )
            )

        # Sort steps by onset temperature (ascending)
        steps.sort(key=lambda s: s.onset_temperature)
        self._steps = steps
        return self

    def process(
        self,
        smooth_method: str = "savgol",
        smooth_dtg: bool = True,
        prominence: Optional[float] = None,
        min_mass_loss: float = 0.5,
        **kwargs,
    ) -> TGAResult:
        """
        Run the complete TGA processing pipeline in a single call.

        Equivalent to calling :meth:`smooth`, :meth:`compute_dtg`, and
        :meth:`detect_steps` in sequence.

        Parameters
        ----------
        smooth_method : str, default 'savgol'
            Smoothing method forwarded to :meth:`smooth`.
        smooth_dtg : bool, default True
            Whether to additionally smooth the DTG curve.
        prominence : float, optional
            DTG peak prominence threshold forwarded to :meth:`detect_steps`.
        min_mass_loss : float, default 0.5
            Minimum mass-loss filter forwarded to :meth:`detect_steps`.
        **kwargs
            Additional keyword arguments forwarded to :meth:`smooth` and
            :meth:`detect_steps`.

        Returns
        -------
        TGAResult
            Fully populated result dataclass.
        """
        self.smooth(method=smooth_method, **kwargs)
        self.compute_dtg(smooth_dtg=smooth_dtg, **kwargs)
        self.detect_steps(prominence=prominence, min_mass_loss=min_mass_loss, **kwargs)
        return self.get_result()

    def get_result(self) -> TGAResult:
        """
        Assemble and return the :class:`TGAResult` from the current pipeline state.

        Returns
        -------
        TGAResult

        Raises
        ------
        RuntimeError
            If the pipeline has not been run (at minimum :meth:`smooth` and
            :meth:`compute_dtg` must have been called).
        """
        if self._smoothed is None or self._dtg is None:
            raise RuntimeError(
                "Pipeline has not been executed.  Call process() or the individual "
                "stage methods (smooth -> compute_dtg -> detect_steps) first."
            )

        smoothed = self._smoothed
        total_mass_loss = float(smoothed[0] - smoothed[-1])
        residue = float(smoothed[-1])

        self._result = TGAResult(
            steps=self._steps or [],
            dtg_peaks=self._dtg_peaks or [],
            dtg_signal=self._dtg,
            smoothed_signal=smoothed,
            total_mass_loss_percent=total_mass_loss,
            residue_percent=residue,
            metadata=self._metadata,
        )
        return self._result
