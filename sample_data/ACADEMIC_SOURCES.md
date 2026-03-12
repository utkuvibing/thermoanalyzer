# Academic Data Sources (Added 2026-03-12)

This project now includes additional DTA and XRD sample/test datasets derived from academic repositories.

## DTA Source

- Repository: Mendeley Data
- DOI: `10.17632/3rdjkjfydp.1`
- Landing page: https://data.mendeley.com/datasets/3rdjkjfydp/1
- License: CC BY 4.0 (as listed on the dataset page)
- Raw download used: `https://data.mendeley.com/public-api/zip/3rdjkjfydp/download/1`

Extracted files were `TGA-TNAA@*.txt` (UTF-16). The cleaned DTA datasets were generated from:

- `temperature` = instrument `Sig2` (`Temperature (degC)`)
- `signal` = instrument `Sig6` (`Temperature Difference (uV)`)

Generated files:

- `sample_data/dta_tnaa_5c_mendeley.csv`
- `sample_data/dta_tnaa_10c_mendeley.csv`
- `test_data/dta_tnaa_2p5c_mendeley.csv`
- `test_data/dta_tnaa_7p5c_mendeley.csv`

## FTIR Source

- Repository: Figshare
- DOI: `10.6084/m9.figshare.29484818.v1`
- Landing page: https://figshare.com/articles/dataset/Particleboard_properties/29484818
- Raw file used: `ftir.csv`

The source file has a multi-column FTIR table. Cleaned files were generated as:

- `temperature` = Wave number (`cm^-1`)
- `signal` = selected transmittance column

Generated files:

- `sample_data/ftir_particleboard_50g_figshare.csv`
- `test_data/ftir_particleboard_100g_figshare.csv`

## Raman Source

- Repository: Figshare
- DOI: `10.6084/m9.figshare.28477127.v1`
- Landing page: https://figshare.com/articles/dataset/Q-switched_Mode-locking_in_Er_ZBLAN_fiber_lasers_using_Carbon_Nanotube_saturable_absorber_and_GaAs-based_SESAM/28477127
- Raw file used: `Raman.txt`

The cleaned Raman files were generated as:

- `temperature` = Raman shift (`cm^-1`)
- `signal` = normalized intensity (`a.u.`)

Generated files:

- `sample_data/raman_cnt_figshare.csv`
- `test_data/raman_cnt_figshare_sparse.csv`

## XRD Sources

- Repository: Zenodo
- Record DOIs:
  - `10.5281/zenodo.15557954`
  - `10.5281/zenodo.15557940`
  - `10.5281/zenodo.15557974`
  - `10.5281/zenodo.15557982`
  - `10.5281/zenodo.15558000`
- Raw files used: `2024-0304.csv`, `2024-0303.csv`, `2024-1613.csv`, `2024-1784.csv`, `2024-2097.csv`

Each raw Zenodo CSV includes metadata blocks and a `[Scan points]` section.
Cleaned XRD files were produced with:

- `temperature` = first scan-point column (`Angle`)
- `signal` = third scan-point column (`Intensity`)

Generated files:

- `sample_data/xrd_2024_0304_zenodo.csv`
- `sample_data/xrd_2024_1613_zenodo.csv`
- `test_data/xrd_2024_0303_zenodo.csv`
- `test_data/xrd_2024_1784_zenodo.csv`
- `test_data/xrd_2024_2097_zenodo.csv`
