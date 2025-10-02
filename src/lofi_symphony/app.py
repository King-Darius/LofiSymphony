"""Streamlit front-end for the LofiSymphony generator."""

from __future__ import annotations

import os
import tempfile
from typing import Iterable

import streamlit as st

from lofi_symphony.generator import (
    AVAILABLE_INSTRUMENTS,
    MOOD_TEMPO,
    TYPE_INSTRUMENTS,
    generate_lofi_midi,
    midi_to_audio,
)


def _render_css() -> None:
    custom_css = """
    <style>
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at top left, #131a26 0%, #04070d 40%, #03050a 100%);
        color: #f8fafc;
    }
    [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    .lofi-card {
        border-radius: 18px;
        padding: 2rem;
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.15);
        box-shadow: 0 20px 40px rgba(15, 23, 42, 0.45);
    }
    .metric-pill {
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.25), rgba(59, 130, 246, 0.25));
        border-radius: 999px;
        padding: 0.35rem 0.9rem;
        font-size: 0.85rem;
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        color: #e0f2fe;
    }
    .stDownloadButton button, .stButton button {
        border-radius: 999px;
        background: linear-gradient(135deg, #a855f7, #6366f1);
        color: white;
        border: none;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .stDownloadButton button:hover, .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 25px rgba(99, 102, 241, 0.25);
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def _render_header() -> None:
    st.markdown(
        """
        <div class="lofi-card" style="margin-bottom: 1.5rem;">
            <div class="metric-pill">✨ Generate immersive LoFi ideas in seconds</div>
            <h1 style="margin-top: 0.5rem;">LofiSymphony 🎵</h1>
            <p style="font-size: 1.1rem; color: #cbd5f5; max-width: 680px;">
                Craft chilled-out progressions, dreamy melodies and vinyl-textured grooves. Pick your vibe, hit
                <strong>Generate</strong>, and jump straight into producing.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _settings_panel() -> tuple[str, str, str, str, int, str, Iterable[str]]:
    with st.container():
        st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
        st.subheader("Track designer", divider="rainbow")

        col1, col2 = st.columns(2)
        with col1:
            selected_key = st.selectbox("Key", ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"], index=0)
            selected_scale = st.selectbox("Scale/Mode", ["minor", "major", "dorian", "mixolydian"], index=0)
            selected_type = st.selectbox("Palette", list(TYPE_INSTRUMENTS.keys()), index=0)
        with col2:
            moods = list(MOOD_TEMPO.keys())
            selected_mood = st.selectbox("Mood", moods, index=0)
            tempo_default = MOOD_TEMPO[selected_mood]
            selected_tempo = st.slider("Tempo (BPM)", min_value=60, max_value=120, value=tempo_default, step=1)
            selected_rhythm = st.selectbox("Groove", ["Straight", "Swing", "Shuffle", "Triplet"], index=0)

        suggested_instruments = TYPE_INSTRUMENTS.get(selected_type, AVAILABLE_INSTRUMENTS)
        selected_instruments = st.multiselect(
            "Instruments",
            options=AVAILABLE_INSTRUMENTS,
            default=suggested_instruments,
            help="Start from the recommended palette and shape your own texture.",
        )

        st.markdown("<hr style='opacity: 0.1;'>", unsafe_allow_html=True)
        generate_clicked = st.button("🎶 Generate track", use_container_width=True)

        st.markdown("</div>", unsafe_allow_html=True)

    return (
        selected_key,
        selected_scale,
        selected_type,
        selected_mood,
        selected_tempo,
        selected_rhythm,
        selected_instruments,
    ), generate_clicked


def _preview_panel():
    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("Session output", divider="rainbow")
    placeholder = st.empty()
    download_holder = st.container()
    st.markdown("</div>", unsafe_allow_html=True)
    return placeholder, download_holder


def main() -> None:
    st.set_page_config(page_title="LofiSymphony", page_icon="🎵", layout="wide")

    _render_css()
    _render_header()

    settings_col, preview_col = st.columns([1.1, 0.9], gap="large")

    with settings_col:
        (settings, generate_clicked) = _settings_panel()

    with preview_col:
        placeholder, download_holder = _preview_panel()

    if not generate_clicked:
        footer = """
        <div style=\"margin-top: 3rem; text-align: center; color: #94a3b8;\">
            Open source ❤️ • Share your creations with #LofiSymphony
        </div>
        """
        st.markdown(footer, unsafe_allow_html=True)
        return

    (selected_key, selected_scale, selected_type, selected_mood, selected_tempo, selected_rhythm, selected_instruments) = settings

    with placeholder:
        st.info("Building your progression, melodies and grooves. This can take a moment…")

    midi_bytes = generate_lofi_midi(
        key=selected_key,
        scale=selected_scale,
        tempo=selected_tempo,
        lofi_type=selected_type,
        rhythm=selected_rhythm,
        mood=selected_mood,
        instruments=selected_instruments,
    )

    with download_holder:
        st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
        st.markdown("### Downloads", unsafe_allow_html=True)
        midi_bytes.seek(0)
        st.download_button("Download MIDI", data=midi_bytes, file_name="lofi.mid", mime="audio/midi")

        try:
            with st.spinner("Rendering lush audio preview with FluidSynth"):
                audio = midi_to_audio(midi_bytes)
                midi_bytes.seek(0)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
                    audio.export(temp_audio.name, format="wav")
                    wav_path = temp_audio.name

            st.audio(wav_path, format="audio/wav")
            st.download_button(
                "Download WAV",
                data=open(wav_path, "rb"),
                file_name="lofi.wav",
                mime="audio/wav",
            )
        except Exception as exc:  # pragma: no cover - visual feedback
            st.warning(
                "Audio preview unavailable. Install FluidSynth and a General MIDI soundfont to enable WAV rendering."
            )
            st.exception(exc)
        finally:
            if "wav_path" in locals():
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

        st.markdown("</div>", unsafe_allow_html=True)

    footer = """
    <div style=\"margin-top: 3rem; text-align: center; color: #94a3b8;\">
        Open source ❤️ • Share your creations with #LofiSymphony
    </div>
    """
    st.markdown(footer, unsafe_allow_html=True)


if __name__ == "__main__":  # pragma: no cover
    main()
