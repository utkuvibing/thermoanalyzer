"""
Physical constants and unit conversion factors for thermal analysis.

All values follow SI base units unless otherwise noted.
"""

# ---------------------------------------------------------------------------
# Fundamental physical constants
# ---------------------------------------------------------------------------

# Universal gas constant [J / (mol * K)]
GAS_CONSTANT_R = 8.314462

# Boltzmann constant [J / K]
BOLTZMANN_KB = 1.380649e-23


# ---------------------------------------------------------------------------
# Temperature conversions
# ---------------------------------------------------------------------------

def celsius_to_kelvin(celsius: float) -> float:
    """Convert degrees Celsius to Kelvin."""
    return celsius + 273.15


def kelvin_to_celsius(kelvin: float) -> float:
    """Convert Kelvin to degrees Celsius."""
    return kelvin - 273.15


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert degrees Celsius to degrees Fahrenheit."""
    return celsius * 9.0 / 5.0 + 32.0


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert degrees Fahrenheit to degrees Celsius."""
    return (fahrenheit - 32.0) * 5.0 / 9.0


# Additive offset used in all C <-> K conversions [K]
CELSIUS_TO_KELVIN_OFFSET = 273.15


# ---------------------------------------------------------------------------
# Energy conversions
# ---------------------------------------------------------------------------

# 1 calorie (thermochemical) in joules
JOULES_PER_CALORIE = 4.184

# 1 joule in calories (thermochemical)
CALORIES_PER_JOULE = 1.0 / JOULES_PER_CALORIE

# 1 milliwatt in watts
WATTS_PER_MILLIWATT = 1.0e-3

# 1 watt in milliwatts
MILLIWATTS_PER_WATT = 1.0e3


def joules_to_calories(joules: float) -> float:
    """Convert joules to thermochemical calories."""
    return joules * CALORIES_PER_JOULE


def calories_to_joules(calories: float) -> float:
    """Convert thermochemical calories to joules."""
    return calories * JOULES_PER_CALORIE


def milliwatts_to_watts(mw: float) -> float:
    """Convert milliwatts to watts."""
    return mw * WATTS_PER_MILLIWATT


def watts_to_milliwatts(w: float) -> float:
    """Convert watts to milliwatts."""
    return w * MILLIWATTS_PER_WATT


# ---------------------------------------------------------------------------
# Mass conversions
# ---------------------------------------------------------------------------

# 1 milligram in grams
GRAMS_PER_MILLIGRAM = 1.0e-3

# 1 gram in milligrams
MILLIGRAMS_PER_GRAM = 1.0e3


def milligrams_to_grams(mg: float) -> float:
    """Convert milligrams to grams."""
    return mg * GRAMS_PER_MILLIGRAM


def grams_to_milligrams(g: float) -> float:
    """Convert grams to milligrams."""
    return g * MILLIGRAMS_PER_GRAM


# ---------------------------------------------------------------------------
# Common experimental parameters
# ---------------------------------------------------------------------------

# Typical heating rates used in DSC / TGA experiments [K/min]
COMMON_HEATING_RATES = [1, 2, 5, 10, 15, 20, 25, 30, 40, 50]


# ---------------------------------------------------------------------------
# Signal unit options
# ---------------------------------------------------------------------------

# Accepted unit strings for DSC heat-flow signals
DSC_HEAT_FLOW_UNITS = [
    "mW",
    "W",
    "mW/mg",
    "W/g",
    "mW/g",
    "uV/mg",
    "mV",
]

# Accepted unit strings for TGA mass / mass-loss signals
TGA_MASS_UNITS = [
    "mg",
    "g",
    "%",
    "% (mass)",
    "norm.",
]

# Accepted unit strings for temperature axes
TEMPERATURE_UNITS = [
    "C",
    "degC",
    "Celsius",
    "K",
    "Kelvin",
    "F",
    "Fahrenheit",
]

# Accepted unit strings for time axes
TIME_UNITS = [
    "s",
    "sec",
    "seconds",
    "min",
    "minutes",
]


# ---------------------------------------------------------------------------
# Column name patterns for automatic column detection (regex)
# ---------------------------------------------------------------------------
# Each key maps to a list of regex patterns (case-insensitive) that are tried
# in order when guessing which DataFrame column represents that quantity.

COLUMN_PATTERNS = {
    "temperature": [
        r"temp(?:erature)?",
        r"t(?:emp)?[\s_\-]?[\[\(]?(?:c|celsius|k|kelvin|f|fahrenheit)[\]\)]?",
        r"^t$",
        r"probe[\s_]?temp",
        r"sample[\s_]?temp",
    ],
    "time": [
        r"time",
        r"t(?:ime)?[\s_\-]?[\[\(]?(?:s|sec|min|minutes?)[\]\)]?",
        r"^t$",
        r"elapsed",
        r"duration",
    ],
    "heat_flow": [
        r"heat[\s_]?flow",
        r"heatflow",
        r"dsc[\s_]?signal",
        r"heat[\s_]?flux",
        r"q[\s_]?dot",
        r"(?:m)?w(?:\/(?:m)?g)?",
        r"exo(?:therm)?",
        r"endo(?:therm)?",
    ],
    "mass": [
        r"mass",
        r"weight",
        r"tga[\s_]?signal",
        r"sample[\s_]?mass",
        r"sample[\s_]?weight",
        r"mg|gram",
        r"m(?:ass)?[\s_\-]?[\[\(]?(?:mg|g|%)[\]\)]?",
        r"(?:mass|weight)[\s_]?(?:loss|change|percent)",
    ],
}
