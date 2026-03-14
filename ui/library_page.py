"""Global reference-library management page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.reference_library import get_reference_library_manager
from ui.components.chrome import render_page_header
from utils.i18n import tx


def render() -> None:
    render_page_header(
        tx("Referans Kütüphanesi", "Reference Library"),
        tx(
            "Global FTIR, Raman ve XRD referans paketlerini senkronize et, cache durumunu izle ve aktif provider kapsamını denetle.",
            "Sync global FTIR, Raman, and XRD reference packages, monitor cache state, and inspect active provider coverage.",
        ),
        badge=tx("M002 Library Platform", "M002 Library Platform"),
    )
    lang = st.session_state.get("ui_language", "tr")
    license_state = st.session_state.get("license_state") or {}
    manager = get_reference_library_manager()
    status = manager.status()
    catalog = manager.catalog()
    installed = manager.installed_packages()
    st.session_state["library_status"] = status

    sync_col, refresh_col, info_col = st.columns([1, 1, 2])
    if sync_col.button(tx("Kütüphaneyi Senkronize Et", "Sync Library"), key="library_sync_btn", use_container_width=True):
        try:
            status = manager.sync(license_state=license_state, force=False)
            st.session_state["library_status"] = status
            st.success(tx("Library paketleri güncellendi.", "Library packages were updated."))
            st.rerun()
        except Exception as exc:
            st.error(f"{tx('Library sync başarısız', 'Library sync failed')}: {exc}")
    if refresh_col.button(tx("Manifesti Yenile", "Refresh Manifest"), key="library_manifest_refresh_btn", use_container_width=True):
        try:
            status = manager.check_manifest(license_state=license_state, force=True)
            st.session_state["library_status"] = status
            st.success(tx("Manifest güncellendi.", "Manifest refreshed."))
            st.rerun()
        except Exception as exc:
            st.error(f"{tx('Manifest yenileme başarısız', 'Manifest refresh failed')}: {exc}")

    info_col.caption(
        tx(
            "Feed erişimi signed license payload ile korunur. Warm cache varsa ağ kesildiğinde arama cached read-only modda devam eder.",
            "Feed access is protected by a signed license payload. If the cache is warm, search continues in cached read-only mode when the network is unavailable.",
        )
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(tx("Sync Modu", "Sync Mode"), _label(status.get("sync_mode"), lang))
    m2.metric(tx("Cache", "Cache"), _label(status.get("cache_status"), lang))
    m3.metric(tx("Kurulu Paket", "Installed Packages"), str(status.get("installed_package_count", 0)))
    m4.metric(tx("Kurulu Referans", "Installed References"), str(status.get("installed_entry_count", 0)))

    n1, n2, n3 = st.columns(3)
    n1.metric(tx("Katalog Paketleri", "Catalog Packages"), str(status.get("available_package_count", 0)))
    n2.metric(tx("Provider", "Providers"), str(status.get("available_provider_count", 0)))
    n3.metric(tx("Update Bekleyen", "Updates Available"), str(status.get("update_available_count", 0)))

    if not status.get("feed_configured"):
        st.warning(
            tx(
                "Library feed yapılandırılmamış. `THERMOANALYZER_LIBRARY_FEED_URL` veya repo içi mirror gerekir.",
                "The library feed is not configured. Set `THERMOANALYZER_LIBRARY_FEED_URL` or provide the bundled mirror.",
            )
        )
    elif status.get("cache_status") == "cold":
        st.warning(
            tx(
                "Cache cold durumda. İlk sync tamamlanana kadar global library eşleştirme devreye girmez.",
                "The cache is cold. Global library matching stays unavailable until the first sync completes.",
            )
        )
    elif status.get("sync_mode") == "cached_read_only":
        st.warning(
            tx(
                "Cached read-only mod aktif. Son senkronize paketlerle çalışılıyor; yeni update'ler alınmıyor.",
                "Cached read-only mode is active. The app is using previously synced packages and is not receiving new updates.",
            )
        )

    if status.get("last_error"):
        st.error(f"{tx('Son hata', 'Last error')}: {status['last_error']}")

    st.caption(
        f"{tx('Feed', 'Feed')}: `{status.get('feed_source') or 'N/A'}`  |  "
        f"{tx('Son manifest kontrolü', 'Last manifest check')}: `{status.get('manifest_checked_at') or 'N/A'}`  |  "
        f"{tx('Son sync', 'Last sync')}: `{status.get('last_sync_at') or 'N/A'}`"
    )

    installed_tab, catalog_tab = st.tabs(
        [tx("Kurulu Paketler", "Installed Packages"), tx("Katalog", "Catalog")]
    )

    with installed_tab:
        if installed:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            tx("Analiz", "Analysis"): item.analysis_type,
                            tx("Provider", "Provider"): item.provider,
                            tx("Paket", "Package"): item.package_id,
                            tx("Versiyon", "Version"): item.version,
                            tx("Referans", "Entries"): item.entry_count,
                            tx("Güncelleme", "Update"): tx("Var", "Yes") if item.update_available else tx("Yok", "No"),
                            tx("Lisans", "License"): item.license_name or "N/A",
                            tx("Attribution", "Attribution"): item.attribution or "N/A",
                        }
                        for item in installed
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(tx("Henüz kurulu library paketi yok.", "No library packages are installed yet."))

    with catalog_tab:
        if catalog:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            tx("Analiz", "Analysis"): item.get("analysis_type"),
                            tx("Provider", "Provider"): item.get("provider"),
                            tx("Paket", "Package"): item.get("package_id"),
                            tx("Versiyon", "Version"): item.get("version"),
                            tx("Referans", "Entries"): item.get("entry_count"),
                            tx("Kurulu", "Installed"): tx("Evet", "Yes") if item.get("installed") else tx("Hayır", "No"),
                            tx("Update", "Update"): tx("Var", "Yes") if item.get("update_available") else tx("Yok", "No"),
                            tx("Lisans", "License"): item.get("license_name") or "N/A",
                            tx("Attribution", "Attribution"): item.get("attribution") or "N/A",
                        }
                        for item in catalog
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(tx("Manifest henüz yüklenmedi.", "The manifest has not been loaded yet."))


def _label(value: object, lang: str) -> str:
    mapping = {
        "not_synced": "Senkronize Değil" if lang == "tr" else "Not Synced",
        "online_sync": "Online Sync" if lang == "tr" else "Online Sync",
        "cached_read_only": "Cache Salt Okunur" if lang == "tr" else "Cached Read-Only",
        "cold": "Soğuk" if lang == "tr" else "Cold",
        "warm": "Hazır" if lang == "tr" else "Warm",
    }
    token = str(value or "")
    return mapping.get(token, token or "N/A")
