"""Global reference-library management page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.library_cloud_client import get_library_cloud_client
from core.reference_library import get_reference_library_manager
from ui.components.chrome import render_page_header
from utils.i18n import tx


def render() -> None:
    render_page_header(
        tx("Referans Kütüphanesi", "Reference Library"),
        tx(
            "Cloud-first managed library erişimini izle; limited fallback cache sağlığını doğrula.",
            "Monitor cloud-first managed library access and verify limited fallback cache health.",
        ),
        badge=tx("M005 Managed Cloud Library", "M005 Managed Cloud Library"),
    )
    lang = st.session_state.get("ui_language", "tr")
    license_state = st.session_state.get("license_state") or {}
    manager = get_reference_library_manager()
    status = manager.status()
    catalog = manager.catalog()
    installed = manager.installed_packages()
    st.session_state["library_status"] = status
    cloud_client = get_library_cloud_client()
    cloud_coverage_payload: dict | None = None
    hosted_provider_rows: list[dict] = []

    if cloud_client.configured:
        coverage_payload = cloud_client.coverage()
        if isinstance(coverage_payload, dict):
            cloud_coverage_payload = coverage_payload
            coverage = coverage_payload.get("coverage") or {}
            seen_providers: dict[str, dict] = {}
            provider_label = tx("Provider", "Provider")
            modalities_label = tx("Modaliteler", "Modalities")
            candidates_label = tx("Aday", "Candidates")
            deduped_label = tx("Deduped", "Deduped")
            dataset_label = tx("Veri Seti", "Dataset")
            freshness_label = tx("Tazelik", "Freshness")
            published_label = tx("Yayınlandı", "Published")
            for modality, details in coverage.items():
                if not isinstance(details, dict):
                    continue
                for provider_id, provider_row in (details.get("providers") or {}).items():
                    payload = dict(provider_row or {})
                    key = str(provider_id)
                    item = seen_providers.setdefault(
                        key,
                        {
                            provider_label: payload.get("provider") or key,
                            modalities_label: [],
                            candidates_label: 0,
                            deduped_label: 0,
                            dataset_label: {},
                            freshness_label: {},
                            published_label: {},
                        },
                    )
                    item[candidates_label] = int(item.get(candidates_label, 0)) + int(payload.get("candidate_count") or 0)
                    item[deduped_label] = int(item.get(deduped_label, 0)) + int(payload.get("deduped_candidate_count") or 0)
                    item[modalities_label].append(str(modality))
                    item[dataset_label][str(modality)] = payload.get("dataset_version") or "N/A"
                    item[freshness_label][str(modality)] = payload.get("freshness_state") or "unknown"
                    item[published_label][str(modality)] = payload.get("published_at") or "N/A"
            hosted_provider_rows = []
            for row in seen_providers.values():
                hosted_provider_rows.append(
                    {
                        provider_label: row[provider_label],
                        modalities_label: ", ".join(sorted(set(row[modalities_label]))),
                        candidates_label: row[candidates_label],
                        deduped_label: row[deduped_label],
                        dataset_label: " | ".join(
                            f"{modality}:{version}"
                            for modality, version in sorted(row[dataset_label].items())
                        ),
                        freshness_label: " | ".join(
                            f"{modality}:{state}"
                            for modality, state in sorted(row[freshness_label].items())
                        ),
                        published_label: " | ".join(
                            f"{modality}:{published}"
                            for modality, published in sorted(row[published_label].items())
                        ),
                    }
                )
            provider_count = len(hosted_provider_rows)
            manager.record_cloud_lookup(success=True, provider_count=provider_count)
            status = manager.status()
            st.session_state["library_status"] = status
        elif cloud_client.last_error:
            manager.record_cloud_lookup(success=False, error=cloud_client.last_error)
            status = manager.status()
            st.session_state["library_status"] = status

    sync_col, refresh_col, info_col = st.columns([1, 1, 2])
    if sync_col.button(tx("Fallback Cache Sync", "Sync Fallback Cache"), key="library_sync_btn", width="stretch"):
        try:
            status = manager.sync(license_state=license_state, force=False)
            st.session_state["library_status"] = status
            st.success(tx("Fallback paket cache güncellendi.", "Fallback package cache was updated."))
            st.rerun()
        except Exception as exc:
            st.error(f"{tx('Library sync başarısız', 'Library sync failed')}: {exc}")
    if refresh_col.button(tx("Fallback Manifesti Yenile", "Refresh Fallback Manifest"), key="library_manifest_refresh_btn", width="stretch"):
        try:
            status = manager.check_manifest(license_state=license_state, force=True)
            st.session_state["library_status"] = status
            st.success(tx("Manifest güncellendi.", "Manifest refreshed."))
            st.rerun()
        except Exception as exc:
            st.error(f"{tx('Manifest yenileme başarısız', 'Manifest refresh failed')}: {exc}")

    info_col.caption(
        tx(
            "Birincil çalışma yolu cloud_full_access modudur. Feed/mirror sync yalnızca limited fallback cache paketlerini güncel tutmak içindir.",
            "The primary runtime path is cloud_full_access. Feed/mirror sync is used only to maintain limited fallback cache packages.",
        )
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(tx("Library Modu", "Library Mode"), _label(status.get("library_mode"), lang))
    m2.metric(
        tx("Cloud Erişimi", "Cloud Access"),
        tx("Açık", "Enabled") if status.get("cloud_access_enabled") else tx("Kapalı", "Disabled"),
    )
    m3.metric(tx("Fallback Paket", "Fallback Packages"), str(status.get("fallback_package_count", 0)))
    m4.metric(tx("Fallback Referans", "Fallback References"), str(status.get("fallback_entry_count", 0)))

    p1, p2, p3, p4 = st.columns(4)
    p1.metric(tx("Sync Modu", "Sync Mode"), _label(status.get("sync_mode"), lang))
    p2.metric(tx("Cache", "Cache"), _label(status.get("cache_status"), lang))
    p3.metric(tx("Kurulu Paket", "Installed Packages"), str(status.get("installed_package_count", 0)))
    p4.metric(tx("Kurulu Referans", "Installed References"), str(status.get("installed_entry_count", 0)))

    n1, n2, n3 = st.columns(3)
    n1.metric(tx("Katalog Paketleri", "Catalog Packages"), str(status.get("available_package_count", 0)))
    n2.metric(tx("Katalog Provider", "Catalog Providers"), str(status.get("available_provider_count", 0)))
    n3.metric(tx("Katalog Update", "Catalog Updates"), str(status.get("update_available_count", 0)))

    cloud_last_lookup = status.get("last_cloud_lookup_at") or "N/A"
    cloud_last_error = str(status.get("last_cloud_error") or "").strip()
    c1, c2, c3 = st.columns(3)
    c1.metric(tx("Cloud Provider", "Cloud Providers"), str(status.get("cloud_provider_count", 0)))
    c2.metric(tx("Son cloud sorgu", "Last cloud lookup"), cloud_last_lookup)
    c3.metric(tx("Son cloud hata", "Last cloud error"), cloud_last_error or tx("Yok", "None"))

    mode = str(status.get("library_mode") or "")
    if mode == "not_configured":
        st.warning(
            tx(
                "Cloud erişimi kapalı ve kullanılabilir fallback cache yok. Qualitative library sonuçları için cloud endpoint veya limited fallback cache yapılandırın.",
                "Cloud access is disabled and no fallback cache is available. Configure cloud endpoints or limited fallback cache for qualitative library results.",
            )
        )
    elif mode == "limited_cached_fallback":
        st.warning(
            tx(
                "Limited cached fallback modu aktif. Bu mod reduced capability sağlar; sonuçları screening amaçlı yorumlayın.",
                "Limited cached fallback mode is active. This mode does not provide full provider coverage; treat results as screening output.",
            )
        )
    elif mode == "cloud_full_access":
        st.success(
            tx(
                "Cloud full access aktif. Fallback cache bu modda yalnızca kesinti dayanıklılığı için ikincil yoldur.",
                "Cloud full access is active. Fallback cache is a secondary resilience path in this mode.",
            )
        )

    if not status.get("feed_configured"):
        if mode == "cloud_full_access":
            st.info(
                tx(
                    "Fallback feed yapılandırılmamış. Cloud full access etkilenmez; yalnızca local fallback cache sync devre dışı kalır.",
                    "Fallback feed is not configured. Cloud full access is unaffected; only local fallback cache sync is unavailable.",
                )
            )
        else:
            st.warning(
                tx(
                    "Fallback feed yapılandırılmamış. Sync için `THERMOANALYZER_LIBRARY_FEED_URL` veya `THERMOANALYZER_LIBRARY_MIRROR_ROOT` ayarla.",
                    "Fallback feed is not configured. Set `THERMOANALYZER_LIBRARY_FEED_URL` or `THERMOANALYZER_LIBRARY_MIRROR_ROOT` for sync.",
                )
            )
    elif status.get("cache_status") == "cold":
        if mode != "cloud_full_access":
            st.warning(
                tx(
                    "Fallback cache cold durumda. İlk fallback sync tamamlanana kadar local fallback eşleştirme sınırlı kalır.",
                    "Fallback cache is cold. Local fallback matching remains limited until the first fallback sync completes.",
                )
            )
    elif status.get("sync_mode") == "cached_read_only":
        message = tx(
            "Fallback cache cached read-only modunda. Son senkronize paketler kullanılıyor; yeni fallback update'leri alınmıyor.",
            "Fallback cache is in cached read-only mode. Previously synced packages are used and new fallback updates are not being pulled.",
        )
        if mode == "cloud_full_access":
            st.info(message)
        else:
            st.warning(message)

    if status.get("last_error"):
        st.error(f"{tx('Son hata', 'Last error')}: {status['last_error']}")
    if status.get("last_cloud_error"):
        st.warning(f"{tx('Cloud hata', 'Cloud error')}: {status['last_cloud_error']}")

    st.caption(
        f"{tx('Fallback Feed', 'Fallback Feed')}: `{status.get('feed_source') or 'N/A'}`  |  "
        f"{tx('Manifest üretildi', 'Manifest generated')}: `{status.get('manifest_generated_at') or 'N/A'}`  |  "
        f"{tx('Son manifest kontrolü', 'Last manifest check')}: `{status.get('manifest_checked_at') or 'N/A'}`  |  "
        f"{tx('Son sync', 'Last sync')}: `{status.get('last_sync_at') or 'N/A'}`"
    )

    installed_tab, catalog_tab = st.tabs(
        [tx("Kurulu Paketler", "Installed Packages"), tx("Katalog", "Catalog")]
    )

    if cloud_coverage_payload:
        st.subheader(tx("Hosted Cloud Coverage", "Hosted Cloud Coverage"))
        coverage_rows = []
        for modality, details in (cloud_coverage_payload.get("coverage") or {}).items():
            if not isinstance(details, dict):
                continue
            coverage_rows.append(
                {
                    tx("Analiz", "Analysis"): modality,
                    tx("Toplam Aday", "Total Candidates"): int(details.get("total_candidate_count") or 0),
                    tx("Deduped", "Deduped"): int(details.get("deduped_candidate_count") or 0),
                    tx("Tazelik", "Freshness"): details.get("freshness_state") or "unknown",
                    tx("Veri Seti Yayını", "Dataset Publish"): details.get("published_at") or "N/A",
                    tx("Son Başarılı Ingest", "Last Successful Ingest"): details.get("last_successful_ingest_at") or "N/A",
                    tx("Başarısız Ingest", "Failed Ingests"): int(details.get("failed_ingest_count") or 0),
                    tx("Providerlar", "Providers"): ", ".join(sorted((details.get("providers") or {}).keys())),
                }
            )
        if coverage_rows:
            st.dataframe(pd.DataFrame(coverage_rows), width="stretch", hide_index=True)
        if hosted_provider_rows:
            st.caption(tx("Hosted provider görünümü aktif dataset version + freshness bilgisini gösterir.", "Hosted provider view shows active dataset version and freshness metadata."))
            st.dataframe(pd.DataFrame(hosted_provider_rows), width="stretch", hide_index=True)

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
                            tx("Yayınlandı", "Published"): item.published_at or "N/A",
                            tx("Üretildi", "Generated"): item.generated_at or "N/A",
                            tx("Veri Seti", "Dataset"): item.provider_dataset_version or "N/A",
                            tx("Build", "Build"): item.builder_version or "N/A",
                            tx("Referans", "Entries"): item.entry_count,
                            tx("Güncelleme", "Update"): tx("Var", "Yes") if item.update_available else tx("Yok", "No"),
                            tx("Lisans", "License"): item.license_name or "N/A",
                            tx("Attribution", "Attribution"): item.attribution or "N/A",
                        }
                        for item in installed
                    ]
                ),
                width="stretch",
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
                            tx("Yayınlandı", "Published"): item.get("published_at") or "N/A",
                            tx("Üretildi", "Generated"): item.get("generated_at") or "N/A",
                            tx("Veri Seti", "Dataset"): item.get("provider_dataset_version") or "N/A",
                            tx("Build", "Build"): item.get("builder_version") or "N/A",
                            tx("Şema", "Schema"): item.get("normalized_schema_version") or "N/A",
                            tx("Referans", "Entries"): item.get("entry_count"),
                            tx("Kurulu", "Installed"): tx("Evet", "Yes") if item.get("installed") else tx("Hayır", "No"),
                            tx("Update", "Update"): tx("Var", "Yes") if item.get("update_available") else tx("Yok", "No"),
                            tx("Teslim Katmanı", "Delivery Tier"): item.get("delivery_tier") or "limited_fallback",
                            tx("Lisans", "License"): item.get("license_name") or "N/A",
                            tx("Attribution", "Attribution"): item.get("attribution") or "N/A",
                        }
                        for item in catalog
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info(
                tx(
                    "Manifest henüz yüklenmedi veya feed yapılandırılmadı.",
                    "The manifest has not been loaded yet or the feed is not configured.",
                )
            )


def _label(value: object, lang: str) -> str:
    mapping = {
        "not_synced": "Senkronize Değil" if lang == "tr" else "Not Synced",
        "online_sync": "Online Sync" if lang == "tr" else "Online Sync",
        "cached_read_only": "Cache Salt Okunur" if lang == "tr" else "Cached Read-Only",
        "cold": "Soğuk" if lang == "tr" else "Cold",
        "warm": "Hazır" if lang == "tr" else "Warm",
        "cloud_full_access": "Cloud Tam Erişim" if lang == "tr" else "Cloud Full Access",
        "limited_cached_fallback": "Sınırlı Fallback" if lang == "tr" else "Limited Cached Fallback",
        "not_configured": "Yapılandırılmadı" if lang == "tr" else "Not Configured",
    }
    token = str(value or "")
    return mapping.get(token, token or "N/A")

