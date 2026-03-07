import numpy as np

from core.kinetics import compute_conversion


def test_compute_conversion_tga_mode_uses_mass_drop_fraction():
    temperature = np.array([25.0, 100.0, 200.0, 300.0])
    mass = np.array([100.0, 95.0, 70.0, 60.0])

    alpha = compute_conversion(temperature, mass, mode="tga")

    np.testing.assert_allclose(alpha, [0.0, 0.125, 0.75, 1.0], atol=1e-8)
