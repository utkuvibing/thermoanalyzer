"""Shared processing-preset controls for analysis pages."""

from __future__ import annotations

import streamlit as st

from core.preset_store import (
    MAX_PRESETS_PER_ANALYSIS,
    PresetLimitError,
    PresetStoreError,
    count_presets,
    delete_preset,
    list_presets,
    load_preset,
    save_preset,
)
from utils.i18n import tx


def render_processing_preset_panel(
    *,
    analysis_type: str,
    state: dict,
    key_prefix: str,
    workflow_select_key: str | None = None,
) -> None:
    """Render save/apply/delete controls for processing presets."""
    normalized_type = str(analysis_type or "").strip().upper()
    none_label = tx("-- Preset seç --", "-- Select preset --")
    panel_title = tx("Ayar Presetleri", "Processing Presets")

    with st.expander(panel_title, expanded=False):
        try:
            presets = list_presets(normalized_type)
            preset_count = count_presets(normalized_type)
        except Exception as exc:
            st.error(
                tx(
                    "Preset listesi alınamadı: {error}",
                    "Could not load presets: {error}",
                    error=str(exc),
                )
            )
            return

        preset_names = [item["preset_name"] for item in presets]
        st.caption(
            tx(
                "{analysis_type} presetleri: {count}/{max_count}",
                "{analysis_type} presets: {count}/{max_count}",
                analysis_type=normalized_type,
                count=preset_count,
                max_count=MAX_PRESETS_PER_ANALYSIS,
            )
        )
        selected_name = st.selectbox(
            tx("Kayıtlı Preset", "Saved Preset"),
            [none_label] + preset_names,
            key=f"{key_prefix}_selected",
        )

        action_cols = st.columns(2)
        with action_cols[0]:
            if st.button(
                tx("Preseti Uygula", "Apply Preset"),
                key=f"{key_prefix}_apply",
                disabled=selected_name == none_label,
            ):
                payload = load_preset(normalized_type, selected_name)
                if payload is None:
                    st.warning(tx("Preset bulunamadı.", "Preset not found."))
                else:
                    state["processing"] = payload["processing"]
                    if workflow_select_key and payload.get("workflow_template_id"):
                        st.session_state[workflow_select_key] = payload["workflow_template_id"]
                    st.success(
                        tx(
                            "{preset} uygulandı.",
                            "{preset} applied.",
                            preset=selected_name,
                        )
                    )
                    st.rerun()

        with action_cols[1]:
            if st.button(
                tx("Preseti Sil", "Delete Preset"),
                key=f"{key_prefix}_delete",
                disabled=selected_name == none_label,
            ):
                deleted = delete_preset(normalized_type, selected_name)
                if deleted:
                    st.success(
                        tx(
                            "{preset} silindi.",
                            "{preset} deleted.",
                            preset=selected_name,
                        )
                    )
                    st.rerun()
                else:
                    st.warning(tx("Preset bulunamadı.", "Preset not found."))

        save_name = st.text_input(
            tx("Yeni Preset Adı", "New Preset Name"),
            value="",
            key=f"{key_prefix}_save_name",
        )
        if st.button(tx("Mevcut Ayarları Kaydet", "Save Current Settings"), key=f"{key_prefix}_save"):
            try:
                processing_payload = {
                    "workflow_template_id": (state.get("processing") or {}).get("workflow_template_id"),
                    "processing": state.get("processing") or {},
                }
                saved = save_preset(
                    normalized_type,
                    save_name,
                    processing_payload,
                )
                st.success(
                    tx(
                        "{preset} kaydedildi ({template}).",
                        "{preset} saved ({template}).",
                        preset=saved["preset_name"],
                        template=saved["workflow_template_id"],
                    )
                )
                st.rerun()
            except PresetLimitError:
                st.warning(
                    tx(
                        "{analysis_type} için maksimum {max_count} preset kaydedebilirsiniz. Yeni kayıt için önce bir preset silin.",
                        "You can save up to {max_count} presets for {analysis_type}. Delete one before saving a new preset.",
                        analysis_type=normalized_type,
                        max_count=MAX_PRESETS_PER_ANALYSIS,
                    )
                )
            except PresetStoreError as exc:
                st.warning(
                    tx(
                        "Preset kaydedilemedi: {error}",
                        "Could not save preset: {error}",
                        error=str(exc),
                    )
                )
            except Exception as exc:
                st.error(
                    tx(
                        "Preset kaydı başarısız oldu: {error}",
                        "Preset save failed: {error}",
                        error=str(exc),
                    )
                )
