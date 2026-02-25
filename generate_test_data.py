"""
Generate realistic thermal analysis test data based on well-known literature values.
These mimic real experimental data with realistic noise, drift, and instrument artifacts.
"""

import numpy as np
import pandas as pd
import os

np.random.seed(2024)
OUT_DIR = os.path.join(os.path.dirname(__file__), "test_data")
os.makedirs(OUT_DIR, exist_ok=True)


def sigmoid(T, center, width):
    return 1.0 / (1.0 + np.exp(-(T - center) / width))


def gaussian(T, center, sigma, amplitude):
    return amplitude * np.exp(-0.5 * ((T - center) / sigma) ** 2)


# =========================================================================
# 1. DSC - PET (Polyethylene Terephthalate) - Amorphous quenched sample
#    Literature: Tg~78°C, Tc~130°C (ΔHc~-25 J/g), Tm~255°C (ΔHm~45 J/g)
#    Heating rate: 10°C/min, sample mass: 8.5 mg
# =========================================================================
print("1. Generating PET DSC data...")
T_pet = np.arange(25, 300.01, 0.5)
time_pet = (T_pet - 25) / 10  # min

baseline_pet = -0.42 + 0.00035 * (T_pet - 25)  # slight baseline drift (exo up)

# Glass transition at 78°C (step ~0.12 mW/mg, width ~8°C)
tg_step = 0.12 * sigmoid(T_pet, 78, 3.5)

# Cold crystallization exotherm at 130°C (exo = negative for heat flow convention endo up)
beta = 10  # °C/min
sigma_cc = 7.0
Hc = 25.0  # J/g
A_cc = (Hc * beta / 60) / (sigma_cc * np.sqrt(2 * np.pi))
cold_cryst = -gaussian(T_pet, 130, sigma_cc, A_cc)

# Melting endotherm at 255°C (endo = positive)
sigma_m = 6.0
Hm = 45.0
A_m = (Hm * beta / 60) / (sigma_m * np.sqrt(2 * np.pi))
melting = gaussian(T_pet, 255, sigma_m, A_m)

# Small pre-melting shoulder at 245°C (recrystallization artifact)
shoulder = gaussian(T_pet, 247, 3.0, A_m * 0.15)

hf_pet = baseline_pet + tg_step + cold_cryst + melting + shoulder
hf_pet += np.random.normal(0, 0.008, len(T_pet))  # realistic noise

df_pet = pd.DataFrame({
    "Temperature (°C)": T_pet,
    "Time (min)": np.round(time_pet, 4),
    "Heat Flow (mW/mg)": np.round(hf_pet, 5),
})
df_pet.to_csv(os.path.join(OUT_DIR, "dsc_PET_amorphous_10Kmin.csv"), index=False)
print(f"   PET DSC: {len(T_pet)} points, Tg~78C, Tc~130C, Tm~255C")

# =========================================================================
# 2. DSC - HDPE (High Density Polyethylene)
#    Literature: Tm~133°C (ΔHm~200 J/g for 100% crystalline, ~140 J/g typical)
#    No Tg visible (below RT), strong sharp melting peak
#    Heating rate: 10°C/min, mass: 5.2 mg
# =========================================================================
print("2. Generating HDPE DSC data...")
T_hdpe = np.arange(30, 200.01, 0.5)
time_hdpe = (T_hdpe - 30) / 10

baseline_hdpe = 0.85 + 0.0004 * (T_hdpe - 30)
sigma_hdpe = 4.5
Hm_hdpe = 140.0
A_hdpe = (Hm_hdpe * 10 / 60) / (sigma_hdpe * np.sqrt(2 * np.pi))
melting_hdpe = gaussian(T_hdpe, 133, sigma_hdpe, A_hdpe)

hf_hdpe = baseline_hdpe + melting_hdpe
hf_hdpe += np.random.normal(0, 0.012, len(T_hdpe))

df_hdpe = pd.DataFrame({
    "Temp_C": T_hdpe,
    "Time_min": np.round(time_hdpe, 4),
    "HeatFlow_mW": np.round(hf_hdpe * 5.2, 4),  # Not normalized - in mW (mass=5.2mg)
})
df_hdpe.to_csv(os.path.join(OUT_DIR, "dsc_HDPE_melting_10Kmin.csv"), index=False)
print(f"   HDPE DSC: {len(T_hdpe)} points, Tm~133C, dHm~140 J/g")

# =========================================================================
# 3. TGA - CaCO3 (Calcium Carbonate) decomposition
#    Literature: CaCO3 → CaO + CO2 at ~600-850°C
#    Mass loss: 44% (CO2), residue: 56% (CaO)
#    Single step, well-characterized
# =========================================================================
print("3. Generating CaCO3 TGA data...")
T_caco3 = np.arange(30, 950.01, 1.0)
time_caco3 = (T_caco3 - 30) / 10

mass_caco3 = 100.0 - 44.0 * sigmoid(T_caco3, 720, 22)
mass_caco3 += np.random.normal(0, 0.08, len(T_caco3))

df_caco3 = pd.DataFrame({
    "Temperature (°C)": T_caco3,
    "Time (min)": np.round(time_caco3, 3),
    "Mass (%)": np.round(mass_caco3, 3),
})
df_caco3.to_csv(os.path.join(OUT_DIR, "tga_CaCO3_decomposition.csv"), index=False)
print(f"   CaCO3 TGA: {len(T_caco3)} points, single step ~720C, 44% loss")

# =========================================================================
# 4. TGA - PMMA (Polymethyl methacrylate) degradation
#    Literature: Two-step degradation
#    Step 1: ~280-320°C, ~5% (chain-end unzipping)
#    Step 2: ~350-420°C, ~93% (main chain decomposition)
#    Residue: ~2%
# =========================================================================
print("4. Generating PMMA TGA data...")
T_pmma = np.arange(25, 550.01, 0.5)
time_pmma = (T_pmma - 25) / 20  # 20°C/min

mass_pmma = (100.0
             - 5.0 * sigmoid(T_pmma, 300, 8)
             - 93.0 * sigmoid(T_pmma, 380, 12))
mass_pmma += np.random.normal(0, 0.06, len(T_pmma))

df_pmma = pd.DataFrame({
    "Temperature/°C": T_pmma,
    "Time/min": np.round(time_pmma, 4),
    "TG/%": np.round(mass_pmma, 3),
})
df_pmma.to_csv(os.path.join(OUT_DIR, "tga_PMMA_degradation_20Kmin.csv"), index=False)
print(f"   PMMA TGA: {len(T_pmma)} points, 2-step degradation")

# =========================================================================
# 5. DSC - Indium melting (calibration standard)
#    Literature: Tm = 156.6°C, ΔHm = 28.45 J/g (very sharp peak)
#    This is the standard calibration test
# =========================================================================
print("5. Generating Indium calibration DSC data...")
T_in = np.arange(140, 175.01, 0.1)
time_in = (T_in - 140) / 10

baseline_in = -0.05 + 0.0001 * (T_in - 140)
sigma_in = 0.8  # Very sharp peak
A_in = (28.45 * 10 / 60) / (sigma_in * np.sqrt(2 * np.pi))
melting_in = gaussian(T_in, 156.6, sigma_in, A_in)

hf_in = baseline_in + melting_in
hf_in += np.random.normal(0, 0.005, len(T_in))

df_in = pd.DataFrame({
    "Temperature (°C)": T_in,
    "Time (min)": np.round(time_in, 4),
    "Heat Flow (mW/mg)": np.round(hf_in, 5),
})
df_in.to_csv(os.path.join(OUT_DIR, "dsc_Indium_calibration.csv"), index=False)
print(f"   Indium DSC: {len(T_in)} points, Tm=156.6C, dHm=28.45 J/g")

# =========================================================================
# 6. TGA - Copper Sulfate Pentahydrate (CuSO4·5H2O)
#    Classic 3-step dehydration:
#    Step 1: ~60-100°C → CuSO4·3H2O (lose 2H2O, 14.4%)
#    Step 2: ~100-150°C → CuSO4·H2O (lose 2H2O, 14.4%)
#    Step 3: ~200-275°C → CuSO4 (lose 1H2O, 7.2%)
#    Total water loss: 36.0%, residue 64.0%
# =========================================================================
print("6. Generating CuSO4-5H2O TGA data...")
T_cuso4 = np.arange(25, 350.01, 0.5)
time_cuso4 = (T_cuso4 - 25) / 10

mass_cuso4 = (100.0
              - 14.4 * sigmoid(T_cuso4, 80, 5)
              - 14.4 * sigmoid(T_cuso4, 125, 6)
              - 7.2 * sigmoid(T_cuso4, 240, 8))
mass_cuso4 += np.random.normal(0, 0.05, len(T_cuso4))

df_cuso4 = pd.DataFrame({
    "Temperature (°C)": T_cuso4,
    "Time (min)": np.round(time_cuso4, 4),
    "Mass (%)": np.round(mass_cuso4, 3),
})
df_cuso4.to_csv(os.path.join(OUT_DIR, "tga_CuSO4_5H2O_dehydration.csv"), index=False)
print(f"   CuSO4-5H2O TGA: {len(T_cuso4)} points, 3-step dehydration, 36% total loss")

# =========================================================================
# 7. DSC - Epoxy curing (exothermic reaction)
#    Uncured epoxy-amine system
#    Tg_uncured ~ -5°C, cure exotherm peak ~120°C, ΔH ~ 350 J/g
#    Multi-rate for Kissinger: 5, 10, 15, 20 °C/min
#    Peak shifts: ~108, 120, 128, 134 °C
# =========================================================================
print("7. Generating Epoxy curing multi-rate DSC data...")
T_epoxy = np.arange(0, 250.01, 0.5)
rates_epoxy = [5, 10, 15, 20]
peak_temps = [108, 120, 128, 134]  # Gives Ea ~ 55 kJ/mol

data_epoxy = {"Temperature (°C)": T_epoxy}
for rate, Tp in zip(rates_epoxy, peak_temps):
    sigma_e = 12 * np.sqrt(rate / 10)
    A_e = (350 * rate / 60) / (sigma_e * np.sqrt(2 * np.pi))
    # Exothermic = negative (endo up convention)
    hf = -gaussian(T_epoxy, Tp, sigma_e, A_e) + 0.01 * (T_epoxy - 0) * 0.001
    hf += np.random.normal(0, 0.01, len(T_epoxy))
    data_epoxy[f"HeatFlow_{rate}Kmin (mW/mg)"] = np.round(hf, 5)

df_epoxy = pd.DataFrame(data_epoxy)
df_epoxy.to_csv(os.path.join(OUT_DIR, "dsc_Epoxy_curing_multirate.csv"), index=False)
print(f"   Epoxy DSC: {len(T_epoxy)} points × 4 rates, peaks at {peak_temps}")

# =========================================================================
# 8. DTA - Kaolin (kaolinite Al2Si2O5(OH)4)
#    Literature thermal events:
#    - Endotherm ~510°C: dehydroxylation
#    - Exotherm ~980°C: mullite formation (sharp spike)
# =========================================================================
print("8. Generating Kaolin DTA data...")
T_kaolin = np.arange(25, 1100.01, 1.0)
time_kaolin = (T_kaolin - 25) / 10

baseline_kaolin = 0.5 + 0.0002 * (T_kaolin - 25)

# Dehydroxylation endotherm
endo_kaolin = gaussian(T_kaolin, 510, 18, 15)

# Mullite exotherm (sharp)
exo_kaolin = -gaussian(T_kaolin, 980, 5, 25)

signal_kaolin = baseline_kaolin + endo_kaolin + exo_kaolin
signal_kaolin += np.random.normal(0, 0.3, len(T_kaolin))

df_kaolin = pd.DataFrame({
    "Temperature (°C)": T_kaolin,
    "Time (min)": np.round(time_kaolin, 3),
    "DTA Signal (µV)": np.round(signal_kaolin, 3),
})
df_kaolin.to_csv(os.path.join(OUT_DIR, "dta_Kaolin_dehydroxylation.csv"), index=False)
print(f"   Kaolin DTA: {len(T_kaolin)} points, endo~510C, exo~980C")

# =========================================================================
# 9. Tab-separated file (simulating NETZSCH export format)
#    DSC - Nylon 6 (PA6)
#    Tg ~ 47°C, Tm ~ 220°C (ΔHm ~ 70 J/g for 100% cryst, ~45 J/g typical)
# =========================================================================
print("9. Generating Nylon 6 DSC (TSV format)...")
T_pa6 = np.arange(0, 270.01, 0.5)
time_pa6 = (T_pa6 - 0) / 10

baseline_pa6 = 0.3 + 0.00025 * T_pa6
tg_pa6 = 0.08 * sigmoid(T_pa6, 47, 3)
sigma_pa6 = 8.0
Hm_pa6 = 45.0
A_pa6 = (Hm_pa6 * 10 / 60) / (sigma_pa6 * np.sqrt(2 * np.pi))
melting_pa6 = gaussian(T_pa6, 220, sigma_pa6, A_pa6)

hf_pa6 = baseline_pa6 + tg_pa6 + melting_pa6
hf_pa6 += np.random.normal(0, 0.006, len(T_pa6))

df_pa6 = pd.DataFrame({
    "Furnace Temperature /°C": T_pa6,
    "Time /min": np.round(time_pa6, 4),
    "DSC /(mW/mg)": np.round(hf_pa6, 5),
})
df_pa6.to_csv(os.path.join(OUT_DIR, "dsc_Nylon6_PA6_NETZSCH.txt"), index=False, sep="\t")
print(f"   Nylon 6 DSC: {len(T_pa6)} points (TSV), Tg~47C, Tm~220C")

# =========================================================================
# 10. Excel file - TGA Multi-material comparison
#     PLA, ABS, Nylon on separate sheets
# =========================================================================
print("10. Generating multi-material TGA Excel file...")
T_multi = np.arange(25, 600.01, 1.0)

# PLA: single step ~300-380°C, ~98% loss
mass_pla = 100.0 - 98.0 * sigmoid(T_multi, 340, 12) + np.random.normal(0, 0.08, len(T_multi))

# ABS: two steps, ~350°C and ~430°C
mass_abs = (100.0
            - 60.0 * sigmoid(T_multi, 370, 10)
            - 38.0 * sigmoid(T_multi, 430, 8)
            + np.random.normal(0, 0.08, len(T_multi)))

# Nylon 6: single step ~400-480°C
mass_nylon = 100.0 - 97.0 * sigmoid(T_multi, 440, 14) + np.random.normal(0, 0.08, len(T_multi))

xlsx_path = os.path.join(OUT_DIR, "tga_polymers_comparison.xlsx")
with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
    pd.DataFrame({"Temperature (°C)": T_multi, "Mass (%)": np.round(mass_pla, 3)}).to_excel(
        writer, sheet_name="PLA", index=False)
    pd.DataFrame({"Temperature (°C)": T_multi, "Mass (%)": np.round(mass_abs, 3)}).to_excel(
        writer, sheet_name="ABS", index=False)
    pd.DataFrame({"Temperature (°C)": T_multi, "Mass (%)": np.round(mass_nylon, 3)}).to_excel(
        writer, sheet_name="Nylon6", index=False)
print(f"   Multi-TGA Excel: PLA/ABS/Nylon6, {len(T_multi)} points each")

print(f"\n=== Generated {len(os.listdir(OUT_DIR))} test data files in {OUT_DIR} ===")
for f in sorted(os.listdir(OUT_DIR)):
    size = os.path.getsize(os.path.join(OUT_DIR, f))
    print(f"  {f:45s} {size/1024:.1f} KB")
