"""Streamlit creative workstation for LofiSymphony."""

from __future__ import annotations

import io
import json
import time
from typing import Sequence

import pandas as pd
import plotly.graph_objects as go
import pretty_midi
import streamlit as st

from .audiocraft_integration import (
    AudiocraftSettings,
    AudiocraftUnavailable,
    generate_musicgen_backing,
    render_musicgen,
)
from .generator import AVAILABLE_INSTRUMENTS, MOOD_TEMPO, TYPE_INSTRUMENTS, generate_lofi_midi, midi_to_audio
from .midi_input import MidiBackendUnavailable, MidiInputManager, MidiMessage
from .timeline import Timeline, TimelineEvent, dataframe_for_display


KEYBOARD_NOTES = [
    "C3",
    "C#3",
    "D3",
    "D#3",
    "E3",
    "F3",
    "F#3",
    "G3",
    "G#3",
    "A3",
    "A#3",
    "B3",
    "C4",
    "C#4",
    "D4",
    "D#4",
    "E4",
    "F4",
    "F#4",
    "G4",
    "G#4",
    "A4",
    "A#4",
    "B4",
]


def _render_css() -> None:
    custom_css = """
    <style>
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 20% 20%, #1f2937 0%, #030712 55%, #02040a 100%);
        color: #f8fafc;
    }
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(14px);
    }
    [data-testid="stHeader"] {background: rgba(0,0,0,0);}
    .lofi-card {
        border-radius: 20px;
        padding: 1.75rem;
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.88), rgba(15, 23, 42, 0.88));
        border: 1px solid rgba(148, 163, 184, 0.12);
        box-shadow: 0 25px 45px rgba(15, 23, 42, 0.45);
        margin-bottom: 1.25rem;
    }
    .metric-pill {
        background: linear-gradient(135deg, rgba(167, 139, 250, 0.35), rgba(56, 189, 248, 0.35));
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
        padding: 0.75rem 1.6rem;
        font-weight: 600;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .stDownloadButton button:hover, .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 14px 28px rgba(99, 102, 241, 0.3);
    }
    .keyboard {
        display: flex;
        gap: 0.2rem;
        justify-content: center;
        padding: 1rem;
    }
    .keyboard button {
        width: 3rem !important;
        height: 9rem;
        border-radius: 12px;
        border: none;
        font-weight: 500;
    }
    .keyboard .white-key {
        background: linear-gradient(180deg, #f8fafc, #e2e8f0);
        color: #020617;
    }
    .keyboard .black-key {
        background: linear-gradient(180deg, #0f172a, #1e293b);
        color: #f8fafc;
        margin-left: -1.5rem;
        margin-right: -1.5rem;
        z-index: 2;
    }
    .timeline-container {
        padding: 1rem;
        border-radius: 18px;
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(148, 163, 184, 0.18);
        box-shadow: inset 0 0 20px rgba(15, 23, 42, 0.35);
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def _render_header() -> None:
    st.markdown(
        """
        <div class="lofi-card">
            <div class="metric-pill">🎛️ Performance-ready creative suite</div>
            <h1 style="margin-top: 0.5rem;">LofiSymphony Studio</h1>
            <p style="font-size: 1.1rem; color: #cbd5f5; max-width: 760px;">
                Sculpt lush beats, improvise with a reactive keyboard, capture USB MIDI in real-time,
                and arrange your story on a tactile timeline. Render instant audiocraft previews or export
                polished stems ready for your DAW.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _initialise_state() -> None:
    if "timeline" not in st.session_state:
        st.session_state.timeline = Timeline()
    if "recording" not in st.session_state:
        st.session_state.recording = False
    if "record_instrument" not in st.session_state:
        st.session_state.record_instrument = "Piano"
    if "keyboard_cursor" not in st.session_state:
        st.session_state.keyboard_cursor = 0.0
    if "midi_manager" not in st.session_state:
        try:
            st.session_state.midi_manager = MidiInputManager()
            st.session_state.midi_status = "Disconnected"
        except MidiBackendUnavailable:
            st.session_state.midi_manager = None
            st.session_state.midi_status = "Backend unavailable"
    if "midi_note_starts" not in st.session_state:
        st.session_state.midi_note_starts = {}
    if "record_start" not in st.session_state:
        st.session_state.record_start = 0.0


def _settings_panel() -> tuple[str, str, str, str, int, str, Sequence[str]]:
    st.sidebar.markdown("## Session DNA")
    selected_key = st.sidebar.selectbox("Key", ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"], index=0)
    selected_scale = st.sidebar.selectbox("Scale/Mode", ["minor", "major", "dorian", "mixolydian"], index=0)
    selected_type = st.sidebar.selectbox("Palette", list(TYPE_INSTRUMENTS.keys()), index=0)

    moods = list(MOOD_TEMPO.keys())
    selected_mood = st.sidebar.selectbox("Mood", moods, index=0)
    tempo_default = MOOD_TEMPO[selected_mood]
    selected_tempo = st.sidebar.slider("Tempo (BPM)", min_value=60, max_value=120, value=tempo_default, step=1)
    selected_rhythm = st.sidebar.selectbox("Groove", ["Straight", "Swing", "Shuffle", "Triplet"], index=0)

    suggested_instruments = TYPE_INSTRUMENTS.get(selected_type, AVAILABLE_INSTRUMENTS)
    selected_instruments = st.sidebar.multiselect(
        "Instruments",
        options=AVAILABLE_INSTRUMENTS,
        default=suggested_instruments,
        help="Start from the recommended palette and shape your own texture.",
    )
    st.sidebar.divider()
    st.sidebar.markdown(
        """
        <small style="color: #94a3b8;">
        💡 Tip: The timeline editor mirrors your DAW. Quantize clips, blend MusicGen stems, or export to
        MIDI and WAV without leaving the browser.
        </small>
        """,
        unsafe_allow_html=True,
    )

    return (
        selected_key,
        selected_scale,
        selected_type,
        selected_mood,
        selected_tempo,
        selected_rhythm,
        selected_instruments,
    )


def _note_to_midi(note_name: str) -> int:
    return pretty_midi.note_name_to_number(note_name)


def _ingest_midi_into_timeline(midi_payload: bytes) -> None:
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_payload))
    events: list[TimelineEvent] = []
    for instrument in midi.instruments:
        instrument_name = "Drums" if instrument.is_drum else pretty_midi.program_to_instrument_name(instrument.program)
        for note in instrument.notes:
            events.append(
                TimelineEvent(
                    start=float(note.start),
                    duration=float(note.end - note.start),
                    pitch=int(note.pitch),
                    velocity=int(note.velocity),
                    instrument=instrument_name,
                )
            )
    if events:
        st.session_state.timeline.extend(events)


def _register_keyboard_note(note_name: str, tempo: int) -> None:
    pitch = _note_to_midi(note_name)
    instrument = st.session_state.record_instrument
    velocity = 95

    if st.session_state.recording:
        elapsed = time.time() - st.session_state.record_start
        beats = elapsed * tempo / 60.0
        event = TimelineEvent(start=beats, duration=0.5, pitch=pitch, velocity=velocity, instrument=instrument)
        st.session_state.timeline.add_event(event)
    else:
        cursor = st.session_state.keyboard_cursor
        event = TimelineEvent(start=cursor, duration=0.5, pitch=pitch, velocity=velocity, instrument=instrument)
        st.session_state.timeline.add_event(event)
        st.session_state.keyboard_cursor = cursor + 0.5


def _handle_midi_message(message: MidiMessage, tempo: int) -> None:
    if message.velocity > 0:
        st.session_state.midi_note_starts[message.note] = message.timestamp
        return

    start_time = st.session_state.midi_note_starts.pop(message.note, None)
    if start_time is None:
        return

    elapsed = start_time - st.session_state.record_start
    start_beats = max(0.0, elapsed * tempo / 60.0)
    duration_beats = max(0.25, (message.timestamp - start_time) * tempo / 60.0)
    instrument = st.session_state.record_instrument
    event = TimelineEvent(
        start=start_beats,
        duration=duration_beats,
        pitch=message.note,
        velocity=max(20, message.velocity),
        instrument=instrument,
    )
    st.session_state.timeline.add_event(event)


def _keyboard_block(tempo: int) -> None:
    st.markdown("### On-screen keys")
    st.markdown("Tap notes to sketch ideas or use the record toggle to capture them in time.")

    keyboard_cols = st.columns(len(KEYBOARD_NOTES))
    for col, note_name in zip(keyboard_cols, KEYBOARD_NOTES):
        is_sharp = "#" in note_name
        button_style = (
            "background: linear-gradient(180deg, #0f172a, #1e293b); color: #f8fafc; box-shadow: inset 0 -6px 0 rgba(15,23,42,0.8);"
            if is_sharp
            else "background: linear-gradient(180deg, #f8fafc, #e2e8f0); color: #020617; box-shadow: inset 0 -6px 0 rgba(148, 163, 184, 0.6);"
        )
        with col:
            if st.button(note_name, key=f"keyboard-{note_name}", help=f"Add note {note_name}", use_container_width=True):
                _register_keyboard_note(note_name, tempo)
        st.markdown(
            f"<style>div[data-testid='stButton'][key='keyboard-{note_name}'] button {{{button_style} border-radius: 14px; height: 120px;}}</style>",
            unsafe_allow_html=True,
        )


def _midi_block(tempo: int) -> None:
    st.markdown("### USB MIDI input")
    manager: MidiInputManager | None = st.session_state.midi_manager

    if manager is None:
        st.info("Install `mido` and `python-rtmidi` to unlock USB MIDI capture.")
        return

    ports = list(manager.list_input_ports())
    selected_port = st.selectbox("Available ports", ports or ["None detected"], disabled=not ports)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Connect", disabled=not ports or st.session_state.midi_status == "Connected"):
            manager.start_listening(selected_port)
            st.session_state.midi_status = "Connected"
    with col2:
        if st.button("Disconnect", disabled=st.session_state.midi_status != "Connected"):
            manager.stop_listening()
            st.session_state.midi_status = "Disconnected"

    st.caption(f"Status: {st.session_state.midi_status}")

    if st.session_state.midi_status == "Connected":
        manager.drain(lambda msg: _handle_midi_message(msg, tempo))


def _recording_controls(tempo: int) -> None:
    st.markdown("### Performance capture")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.session_state.record_instrument = st.selectbox("Instrument for takes", AVAILABLE_INSTRUMENTS, index=0)
    with col2:
        if st.button("Reset cursor"):
            st.session_state.keyboard_cursor = 0.0

    record_label = "⏺️ Start recording" if not st.session_state.recording else "⏹️ Stop recording"
    if st.button(record_label):
        if not st.session_state.recording:
            st.session_state.recording = True
            st.session_state.record_start = time.time()
            st.toast("Recording started – play from your MIDI keyboard or the on-screen keys.")
        else:
            st.session_state.recording = False
            st.session_state.midi_note_starts.clear()
            st.toast("Recording stopped – notes landed on the timeline.")

    st.caption(
        "Recording writes directly into the timeline. Use Quantize in the Timeline tab to tighten grooves."
    )


def _timeline_plot(timeline: Timeline) -> go.Figure:
    fig = go.Figure()
    if len(timeline.events) == 0:
        fig.add_annotation(text="No clips yet", showarrow=False, font=dict(color="#94a3b8", size=18))
        fig.update_layout(height=220, xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    instruments = sorted({event.instrument for event in timeline.events})
    palette = ["#a855f7", "#f472b6", "#38bdf8", "#34d399", "#facc15", "#fb7185"]

    for idx, event in enumerate(timeline.events):
        color = palette[idx % len(palette)]
        fig.add_trace(
            go.Bar(
                x=[event.duration],
                y=[event.instrument],
                base=[event.start],
                orientation="h",
                marker=dict(color=color, opacity=0.85),
                name=f"{event.instrument} ({event.pitch})",
                hovertemplate="Instrument: %{y}<br>Start: %{base} beats<br>Length: %{x} beats<br>Pitch: %{text}",
                text=[event.pitch],
                showlegend=False,
            )
        )

    fig.update_layout(
        height=340,
        bargap=0.2,
        template="plotly_dark",
        xaxis_title="Beats",
        yaxis_title="Instrument",
        plot_bgcolor="rgba(15,23,42,0.6)",
        paper_bgcolor="rgba(15,23,42,0)",
    )
    return fig


def _timeline_tab(settings: tuple[str, str, str, str, int, str, Sequence[str]]) -> None:
    tempo = settings[4]
    timeline: Timeline = st.session_state.timeline

    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("Timeline editor", divider="rainbow")
    st.markdown("Tune takes, quantize and render your arrangement.")

    display_df = dataframe_for_display(timeline)
    with st.form("timeline-editor-form"):
        edited = st.data_editor(display_df, key="timeline-editor", num_rows="dynamic")
        apply = st.form_submit_button("Apply edits")
    if apply and isinstance(edited, pd.DataFrame):
        st.session_state.timeline.update_from_dataframe(edited)

    col1, col2, col3 = st.columns(3)
    with col1:
        grid_options = [0.25, 0.5, 1.0]
        grid_labels = {0.25: "16th notes", 0.5: "8th notes", 1.0: "Quarter notes"}
        grid = st.selectbox("Quantize grid", grid_options, format_func=lambda v: grid_labels[v])
        if st.button("Quantize"):
            st.session_state.timeline.quantize(grid)
            st.rerun()
    with col2:
        if st.button("Clear timeline"):
            st.session_state.timeline = Timeline()
            st.rerun()
    with col3:
        if st.button("Duplicate last bar") and timeline.events:
            last_end = max(event.start + event.duration for event in timeline.events)
            new_events = [
                TimelineEvent(
                    start=event.start + last_end,
                    duration=event.duration,
                    pitch=event.pitch,
                    velocity=event.velocity,
                    instrument=event.instrument,
                )
                for event in timeline.events
            ]
            st.session_state.timeline.extend(new_events)
            st.rerun()

    st.plotly_chart(_timeline_plot(st.session_state.timeline), use_container_width=True)

    if not st.session_state.timeline.events:
        st.info("Add clips via the generator or performance desk to render the timeline.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    midi_obj = st.session_state.timeline.to_pretty_midi(tempo)
    midi_bytes = io.BytesIO()
    midi_obj.write(midi_bytes)
    midi_bytes.seek(0)
    st.download_button("Download timeline MIDI", midi_bytes, file_name="timeline.mid", mime="audio/midi")

    audio_segment = midi_to_audio(io.BytesIO(midi_bytes.getvalue()))
    audio_buffer = io.BytesIO()
    audio_segment.export(audio_buffer, format="wav")
    audio_buffer.seek(0)
    st.audio(audio_buffer)
    st.download_button(
        "Download timeline WAV",
        data=audio_buffer.getvalue(),
        file_name="timeline.wav",
        mime="audio/wav",
    )

    json_payload = json.dumps([event.to_dict() for event in st.session_state.timeline.events], indent=2).encode("utf-8")
    st.download_button(
        "Download timeline JSON",
        data=json_payload,
        file_name="timeline.json",
        mime="application/json",
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _performance_tab(settings: tuple[str, str, str, str, int, str, Sequence[str]]) -> None:
    tempo = settings[4]
    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("Performance desk", divider="rainbow")
    _recording_controls(tempo)
    st.divider()
    _keyboard_block(tempo)
    st.divider()
    _midi_block(tempo)
    st.markdown("</div>", unsafe_allow_html=True)


def _generator_tab(settings: tuple[str, str, str, str, int, str, Sequence[str]]) -> None:
    (selected_key, selected_scale, selected_type, selected_mood, selected_tempo, selected_rhythm, selected_instruments) = settings
    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("AI-assisted ideas", divider="rainbow")

    col1, col2 = st.columns([0.6, 0.4])
    with col1:
        st.markdown("### Generate MIDI scaffold")
        if st.button("🎶 Generate progression"):
            midi_bytes = generate_lofi_midi(
                key=selected_key,
                scale=selected_scale,
                tempo=selected_tempo,
                lofi_type=selected_type,
                rhythm=selected_rhythm,
                mood=selected_mood,
                instruments=selected_instruments,
            )
            midi_payload = midi_bytes.getvalue()
            st.session_state.generated_midi = midi_payload
            _ingest_midi_into_timeline(midi_payload)
            st.session_state.timeline.quantize(0.25)
            audio_segment = midi_to_audio(io.BytesIO(midi_payload))
            audio_buffer = io.BytesIO()
            audio_segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)
            st.audio(audio_buffer)
            st.download_button(
                "Download generated WAV",
                data=audio_buffer.getvalue(),
                file_name="lofi_idea.wav",
                mime="audio/wav",
            )
            st.success("Fresh MIDI idea generated and added to the timeline.")
    with col2:
        st.markdown("### MusicGen preview")
        prompt = st.text_area("Prompt", value="A dusty lofi beat with warm chords and vinyl crackle")
        duration = st.slider("Duration", min_value=8.0, max_value=30.0, value=12.0, step=1.0)
        if st.button("✨ Render with MusicGen"):
            try:
                audio_path = render_musicgen(AudiocraftSettings(prompt=prompt, duration=duration))
                st.audio(str(audio_path))
                st.session_state.musicgen_path = audio_path
            except AudiocraftUnavailable as exc:
                st.warning(str(exc))

    st.divider()
    st.markdown("### Blend MusicGen with MIDI")
    with st.form("musicgen-blend"):
        blend_prompt = st.text_input("Blend prompt", value="Lo-fi beat with mellow keys and gentle sidechain pumping")
        submitted = st.form_submit_button("Create hybrid render")
        if submitted:
            try:
                blended = generate_musicgen_backing(
                    prompt=blend_prompt,
                    key=selected_key,
                    scale=selected_scale,
                    tempo=selected_tempo,
                    instruments=selected_instruments,
                )
                st.audio(str(blended))
                st.download_button("Download blend", data=open(blended, "rb"), file_name="musicgen_blend.wav", mime="audio/wav")
            except AudiocraftUnavailable as exc:
                st.warning(str(exc))

    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="LofiSymphony Studio", page_icon="🎵", layout="wide")

    _initialise_state()
    _render_css()
    _render_header()

    settings = _settings_panel()

    generator_tab, performance_tab, timeline_tab = st.tabs(["Generator", "Performance", "Timeline"])
    with generator_tab:
        _generator_tab(settings)
    with performance_tab:
        _performance_tab(settings)
    with timeline_tab:
        _timeline_tab(settings)

    footer = """
    <div style=\"margin-top: 2.5rem; text-align: center; color: #94a3b8;\">
        Open source ❤️ • Share your creations with #LofiSymphony
    </div>
    """
    st.markdown(footer, unsafe_allow_html=True)


if __name__ == "__main__":  # pragma: no cover
    main()
