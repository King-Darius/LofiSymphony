"""Streamlit creative workstation for LofiSymphony."""

from __future__ import annotations

import io
import json
import sys
import importlib
import importlib.util
import random
import time
from collections import defaultdict
from dataclasses import dataclass, replace as dataclass_replace
from typing import Any, Sequence


if __package__ in {None, ""}:  # pragma: no cover - defensive import guard
    # Allow running ``python -m streamlit run lofi_symphony/app.py`` without
    # installation by deriving the package context from the file location. The
    # resolved path stays within the current process and is never exposed
    # externally.
    from pathlib import Path
    from types import ModuleType

    module = sys.modules[__name__]
    package_dir = Path(__file__).resolve().parent

    package_parts: list[str] = []
    search_root = package_dir
    while (search_root / "__init__.py").exists():
        package_parts.append(search_root.name)
        search_root = search_root.parent

    if not package_parts:
        package_name = package_dir.name
    else:
        package_name = ".".join(reversed(package_parts))

    sys_path_entry = str(search_root)
    if sys_path_entry not in sys.path:
        sys.path.insert(0, sys_path_entry)

    module.__package__ = package_name

    canonical_name = f"{package_name}.app"
    spec = importlib.util.spec_from_file_location(canonical_name, __file__)
    if spec is not None:
        module.__spec__ = spec
        if spec.loader is not None:
            module.__loader__ = spec.loader

    sys.modules.setdefault(canonical_name, module)

    if package_name not in sys.modules:
        try:
            importlib.import_module(package_name)
        except ImportError:
            fallback = ModuleType(package_name)
            fallback.__file__ = str(package_dir / "__init__.py")
            fallback.__package__ = package_name
            fallback.__path__ = [str(package_dir)]
            fallback_spec = importlib.util.spec_from_loader(
                package_name, loader=None, origin=fallback.__file__
            )
            if fallback_spec is not None:
                fallback_spec.submodule_search_locations = list(fallback.__path__)
                fallback.__spec__ = fallback_spec
            sys.modules[package_name] = fallback

    package_module = sys.modules.get(package_name)
    if package_module is not None and not hasattr(package_module, "app"):
        try:
            setattr(package_module, "app", module)
        except Exception:
            pass

import pandas as pd
import plotly.graph_objects as go
import pretty_midi
import streamlit as st

from lofi_symphony.audiocraft_integration import (
    AudiocraftSettings,
    AudiocraftUnavailable,
    generate_musicgen_backing,
    render_musicgen,
)
from lofi_symphony.generator import (
    AVAILABLE_INSTRUMENTS,
    MOOD_TEMPO,
    TYPE_INSTRUMENTS,
    TYPE_PROGRESSIONS,
    SectionArrangement,
    generate_lofi_midi,
    generate_structured_song,
    midi_to_audio,
)
from lofi_symphony.midi_input import MidiBackendUnavailable, MidiInputManager, MidiMessage
from lofi_symphony.timeline import Timeline, TimelineEvent, dataframe_for_display


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


WORKFLOW_GUIDE_STEPS = [
    {
        "title": "Generator",
        "highlight": "Dial in key, scale, palette and mood to seed harmonic DNA.",
        "details": "Use the quick actions to drop MIDI ideas on the timeline or to spin up a full arrangement draft.",
    },
    {
        "title": "Performance",
        "highlight": "Capture takes with the on-screen keyboard or a USB MIDI controller.",
        "details": "Layer improvisations on top of generated material and keep an eye on the live capture counter.",
    },
    {
        "title": "Arranger",
        "highlight": "Shape sections, balance tracks and audition hooks before committing to exports.",
        "details": "The new Arranger tab mirrors the design mockups and will evolve into the full timeline mixer.",
    },
    {
        "title": "Timeline",
        "highlight": "Quantize, edit clips directly and render polished stems.",
        "details": "Export MIDI, WAV and JSON when you are happy with the structure.",
    },
]


DEFAULT_ARRANGER_TRACKS = [
    {
        "name": "Chords",
        "role": "Harmonic bed",
        "instrument": "Rhodes",
        "enabled": True,
        "volume": 82,
        "pan": 0,
        "color": "#a855f7",
    },
    {
        "name": "Melody",
        "role": "Lead phrases",
        "instrument": "Synth",
        "enabled": True,
        "volume": 74,
        "pan": -8,
        "color": "#22d3ee",
    },
    {
        "name": "Bass",
        "role": "Low-end groove",
        "instrument": "Bass",
        "enabled": True,
        "volume": 78,
        "pan": 6,
        "color": "#ec4899",
    },
    {
        "name": "Drums",
        "role": "Rhythm kit",
        "instrument": "Drums",
        "enabled": True,
        "volume": 70,
        "pan": 0,
        "color": "#f97316",
    },
    {
        "name": "Textures",
        "role": "FX layers",
        "instrument": "FX",
        "enabled": False,
        "volume": 52,
        "pan": 18,
        "color": "#c084fc",
    },
]


EFFECT_PRESETS = [
    "Tape Warmth",
    "Vinyl Crackle",
    "Lush Chorus",
    "Stereo Spread",
    "Dusty Reverb",
    "Lo-Fi Delay",
]


ARRANGER_AUTOMATION_DEFAULT = 100
BEATS_PER_BAR = 2.0


MUSICGEN_AVAILABLE = importlib.util.find_spec("audiocraft") is not None


@dataclass(frozen=True)
class SessionSettings:
    """Bundle the musical DNA of the active session for UI consumption."""

    key: str
    scale: str
    palette: str
    mood: str
    tempo: int
    rhythm: str
    instruments: Sequence[str]

    def tonality(self) -> str:
        return f"{self.key} {self.scale.title()}"

    def instruments_label(self) -> str:
        return ", ".join(self.instruments) if self.instruments else "None"


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
    .status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .status-card {
        padding: 1.1rem 1.25rem;
        border-radius: 18px;
        background: linear-gradient(155deg, rgba(30, 41, 59, 0.92), rgba(17, 24, 39, 0.88));
        border: 1px solid rgba(168, 85, 247, 0.22);
        box-shadow: 0 18px 32px rgba(15, 23, 42, 0.35);
    }
    .status-card h4 {
        margin: 0;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
        color: #cbd5f5;
        text-transform: uppercase;
    }
    .status-card .status-value {
        font-size: 1.6rem;
        margin-top: 0.35rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .status-card .status-footnote {
        margin-top: 0.45rem;
        color: #94a3b8;
        font-size: 0.85rem;
    }
    .progression-card {
        padding: 1.25rem;
        border-radius: 20px;
        background: linear-gradient(140deg, rgba(99, 102, 241, 0.12), rgba(168, 85, 247, 0.08));
        border: 1px solid rgba(99, 102, 241, 0.35);
        margin-bottom: 1rem;
    }
    .arrangement-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.75rem;
    }
    .arrangement-table th, .arrangement-table td {
        padding: 0.6rem 0.75rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.18);
        font-size: 0.85rem;
        color: #e2e8f0;
    }
    .arrangement-table th {
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
        color: #94a3b8;
    }
    .arrangement-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.3rem 0.65rem;
        border-radius: 999px;
        background: rgba(59, 130, 246, 0.25);
        color: #bfdbfe;
        font-size: 0.75rem;
    }
    .arrangement-motif {
        margin-top: 0.9rem;
        font-size: 0.85rem;
        color: #cbd5f5;
    }
    .progression-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
    }
    .progression-title {
        font-weight: 600;
        color: #f5f3ff;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }
    .progression-meta {
        font-size: 0.85rem;
        color: #bfdbfe;
    }
    .progression-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    .progression-chip {
        padding: 0.45rem 0.75rem;
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(148, 163, 184, 0.35);
        font-weight: 600;
        color: #e2e8f0;
        letter-spacing: 0.03em;
    }
    .instrument-tag {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.35rem 0.7rem;
        border-radius: 999px;
        background: rgba(14, 116, 144, 0.3);
        color: #cffafe;
        font-size: 0.8rem;
    }
    .workflow-panel {
        margin-top: 0.85rem;
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.6), rgba(15, 23, 42, 0.65));
        border: 1px solid rgba(148, 163, 184, 0.18);
        padding: 1rem 1.25rem;
    }
    .workflow-step {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        padding: 0.65rem 0.75rem;
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(148, 163, 184, 0.12);
        margin-bottom: 0.55rem;
    }
    .workflow-step h4 {
        margin: 0;
        font-size: 1rem;
        color: #c4b5fd;
        letter-spacing: 0.02em;
    }
    .workflow-step span {
        font-size: 0.95rem;
        color: #bfdbfe;
    }
    .workflow-step p {
        margin: 0;
        color: #e2e8f0;
        opacity: 0.85;
        font-size: 0.9rem;
    }
    .arranger-summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: 1rem;
        margin-top: 1.1rem;
    }
    .arranger-summary-card {
        border-radius: 18px;
        padding: 1rem 1.1rem;
        background: linear-gradient(160deg, rgba(30, 64, 175, 0.55), rgba(14, 165, 233, 0.3));
        border: 1px solid rgba(125, 211, 252, 0.3);
        box-shadow: 0 18px 34px rgba(14, 165, 233, 0.16);
        transition: transform 0.2s ease, opacity 0.2s ease;
    }
    .arranger-summary-card.muted {
        opacity: 0.55;
        background: linear-gradient(160deg, rgba(79, 70, 229, 0.25), rgba(14, 165, 233, 0.15));
        border-color: rgba(148, 163, 184, 0.25);
    }
    .arranger-summary-card h4 {
        margin: 0;
        font-size: 1.05rem;
        color: #ede9fe;
    }
    .arranger-role {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #f5f3ff;
        opacity: 0.8;
    }
    .arranger-meter {
        margin-top: 0.75rem;
        height: 8px;
        width: 100%;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.65);
        overflow: hidden;
    }
    .arranger-meter-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, rgba(224, 231, 255, 0.9), rgba(96, 165, 250, 0.95));
    }
    .arranger-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        padding: 0.3rem 0.65rem;
        border-radius: 999px;
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(148, 163, 184, 0.25);
        font-size: 0.8rem;
        color: #bfdbfe;
    }
    .arranger-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.65rem;
    }
    .arranger-table th,
    .arranger-table td {
        border: 1px solid rgba(148, 163, 184, 0.2);
        padding: 0.55rem 0.65rem;
        text-align: left;
        font-size: 0.9rem;
        color: #e2e8f0;
        background: rgba(15, 23, 42, 0.55);
    }
    .arranger-table th {
        background: rgba(30, 41, 59, 0.75);
        text-transform: uppercase;
        font-size: 0.8rem;
        letter-spacing: 0.05em;
        color: #c4b5fd;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)


def _workflow_guide() -> None:
    st.markdown(
        """
        <div class="workflow-panel">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap;">
                <div style="display: flex; align-items: center; gap: 0.65rem;">
                    <div style="width: 40px; height: 40px; border-radius: 14px; background: linear-gradient(135deg, rgba(167, 139, 250, 0.45), rgba(56, 189, 248, 0.45)); display: grid; place-items: center; font-size: 1.25rem;">🎛️</div>
                    <div>
                        <div style="font-weight: 600; color: #e0e7ff; letter-spacing: 0.05em;">Workflow guide</div>
                        <div style="font-size: 0.85rem; color: #cbd5f5;">Mirror the GUI mockups inside Streamlit while the interactive features land.</div>
                    </div>
                </div>
                <span class="arranger-chip">Design parity roadmap</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for step in WORKFLOW_GUIDE_STEPS:
        st.markdown(
            f"""
            <div class="workflow-step">
                <h4>{step["title"]}</h4>
                <span>{step["highlight"]}</span>
                <p>{step["details"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _arranger_section_names(sections: Sequence[dict[str, Any]] | None) -> list[str]:
    if not sections:
        return ["Global"]
    ordered = sorted(sections, key=lambda item: item.get("start_bar", 0))
    return [item.get("name", f"Section {index + 1}") for index, item in enumerate(ordered)]


def _initialise_arranger_state(
    sections: Sequence[dict[str, Any]] | None = None,
    *,
    reset_lanes: bool = False,
) -> None:
    """Ensure arranger track state, automation and lane metadata exist."""

    if "arranger_tracks" not in st.session_state:
        st.session_state.arranger_tracks = []
        for template in DEFAULT_ARRANGER_TRACKS:
            st.session_state.arranger_tracks.append(
                {
                    **template,
                    "solo": False,
                    "effects": [],
                    "automation": {},
                }
            )

    if sections is None:
        sections = st.session_state.get("arrangement_sections") or []

    timeline: Timeline = st.session_state.get("timeline", Timeline())
    existing_instruments = {track["instrument"] for track in st.session_state.arranger_tracks}
    discovered_instruments = sorted({event.instrument for event in getattr(timeline, "events", [])})
    for instrument in discovered_instruments:
        if instrument not in existing_instruments:
            st.session_state.arranger_tracks.append(
                {
                    "name": instrument,
                    "role": "Imported",
                    "instrument": instrument,
                    "enabled": True,
                    "volume": 80,
                    "pan": 0,
                    "color": "#38bdf8",
                    "solo": False,
                    "effects": [],
                    "automation": {},
                }
            )
            existing_instruments.add(instrument)

    _sync_arranger_from_sections(sections)

    if reset_lanes or "arranger_lanes" not in st.session_state:
        st.session_state.arranger_lanes = _build_arranger_lane_records(sections)


def _sync_arranger_from_sections(sections: Sequence[dict[str, Any]] | None) -> None:
    tracks = st.session_state.get("arranger_tracks")
    if not tracks:
        return

    section_names = _arranger_section_names(sections)
    for track in tracks:
        automation = track.setdefault("automation", {})
        for name in section_names:
            automation.setdefault(name, ARRANGER_AUTOMATION_DEFAULT)
        obsolete = [name for name in automation if name not in section_names]
        for name in obsolete:
            automation.pop(name, None)
    st.session_state.arranger_tracks = tracks


def _build_arranger_lane_records(sections: Sequence[dict[str, Any]] | None) -> list[dict[str, Any]]:
    tracks = st.session_state.get("arranger_tracks", [])
    lanes: list[dict[str, Any]] = []
    order_counter = 0

    if sections:
        ordered_sections = sorted(sections, key=lambda item: item.get("start_bar", 0))
        for section in ordered_sections:
            start = section.get("start_bar", 0) * BEATS_PER_BAR
            length = section.get("n_bars", 4) * BEATS_PER_BAR
            instruments = section.get("instruments") or [track["instrument"] for track in tracks]
            for instrument in instruments:
                lanes.append(
                    {
                        "Order": order_counter,
                        "Section": section.get("name", f"Section {order_counter + 1}"),
                        "Instrument": instrument,
                        "Start (beats)": round(start, 2),
                        "Length (beats)": round(length, 2),
                    }
                )
                order_counter += 1
    else:
        for track in tracks:
            lanes.append(
                {
                    "Order": order_counter,
                    "Section": "Global",
                    "Instrument": track["instrument"],
                    "Start (beats)": 0.0,
                    "Length (beats)": 8.0,
                }
            )
            order_counter += 1

    return lanes


def _section_for_start(start: float, sections: Sequence[dict[str, Any]] | None) -> str | None:
    if not sections:
        return None
    ordered = sorted(sections, key=lambda item: item.get("start_bar", 0))
    for section in ordered:
        section_start = section.get("start_bar", 0) * BEATS_PER_BAR
        section_length = section.get("n_bars", 4) * BEATS_PER_BAR
        section_end = section_start + section_length
        if section_start <= start < section_end:
            return section.get("name")
    return None


def _arranger_tracks_map() -> dict[str, dict[str, Any]]:
    tracks = st.session_state.get("arranger_tracks", [])
    return {track["instrument"]: track for track in tracks}


def _active_arranger_tracks() -> dict[str, dict[str, Any]]:
    tracks = st.session_state.get("arranger_tracks", [])
    if not tracks:
        return {}

    solo_active = any(track.get("solo") for track in tracks)
    active: dict[str, dict[str, Any]] = {}
    for track in tracks:
        instrument = track["instrument"]
        if solo_active:
            if track.get("solo"):
                active[instrument] = track
        else:
            if track.get("enabled", True):
                active[instrument] = track
    if not active:
        return {}
    return active


def _update_sections_from_lanes(lanes: list[dict[str, Any]]) -> None:
    if not lanes:
        return

    previous_sections = st.session_state.get("arrangement_sections") or []
    if not previous_sections:
        return

    previous_map = {section["name"]: dict(section) for section in previous_sections if section.get("name")}

    section_accumulator: dict[str, dict[str, float]] = defaultdict(lambda: {"start": None, "end": None})
    for lane in lanes:
        section_name = lane.get("Section")
        start = float(lane.get("Start (beats)", 0.0))
        length = float(lane.get("Length (beats)", BEATS_PER_BAR * 4))
        end = start + length
        stats = section_accumulator[section_name]
        stats["start"] = start if stats["start"] is None else min(stats["start"], start)
        stats["end"] = end if stats["end"] is None else max(stats["end"], end)

    delta_map: dict[str, float] = {}
    updated_sections: list[dict[str, Any]] = []
    for section_name, stats in section_accumulator.items():
        start_beats = stats["start"] or 0.0
        end_beats = stats["end"] or (start_beats + BEATS_PER_BAR * 4)
        length_beats = max(BEATS_PER_BAR, end_beats - start_beats)
        start_bar = int(round(start_beats / BEATS_PER_BAR))
        n_bars = max(1, int(round(length_beats / BEATS_PER_BAR)))

        previous = previous_map.get(section_name)
        if previous:
            old_start_beats = previous.get("start_bar", 0) * BEATS_PER_BAR
            delta_map[section_name] = start_beats - old_start_beats
        else:
            delta_map[section_name] = 0.0

        updated_sections.append(
            {
                "name": section_name,
                "start_bar": start_bar,
                "n_bars": n_bars,
                "progression": (previous or {}).get("progression", []),
                "instruments": (previous or {}).get("instruments", []),
                "has_hook": (previous or {}).get("has_hook", False),
                "hook_motif": (previous or {}).get("hook_motif", []),
            }
        )

    updated_sections.sort(key=lambda item: item.get("start_bar", 0))
    _shift_timeline_sections(previous_sections, delta_map)
    st.session_state.arrangement_sections = updated_sections
    _sync_arranger_from_sections(updated_sections)


def _shift_timeline_sections(previous_sections: Sequence[dict[str, Any]], delta_map: dict[str, float]) -> None:
    if not previous_sections or not delta_map:
        return

    timeline: Timeline = st.session_state.timeline
    if not timeline.events:
        return

    section_ranges = []
    for section in previous_sections:
        name = section.get("name")
        start = section.get("start_bar", 0) * BEATS_PER_BAR
        end = start + section.get("n_bars", 4) * BEATS_PER_BAR
        section_ranges.append((name, start, end))

    adjusted_events: list[TimelineEvent] = []
    for event in timeline.events:
        section_name = None
        for name, start, end in section_ranges:
            if start <= event.start < end:
                section_name = name
                break
        delta = delta_map.get(section_name, 0.0)
        adjusted_events.append(
            dataclass_replace(
                event,
                start=max(0.0, event.start + delta),
            )
        )

    st.session_state.timeline = Timeline(adjusted_events)


def _arranger_filtered_timeline(timeline: Timeline) -> Timeline:
    active_tracks = _active_arranger_tracks()
    if not active_tracks:
        return Timeline([])

    sections = st.session_state.get("arrangement_sections") or []
    filtered_events: list[TimelineEvent] = []

    for event in timeline.events:
        track = active_tracks.get(event.instrument)
        if not track:
            continue

        volume_factor = track.get("volume", 100) / 100.0
        if volume_factor <= 0:
            continue

        section_name = _section_for_start(event.start, sections)
        automation_map = track.get("automation", {})
        automation_value = automation_map.get(section_name or "Global", ARRANGER_AUTOMATION_DEFAULT)
        automation_factor = automation_value / 100.0

        velocity = int(round(event.velocity * volume_factor * automation_factor))
        velocity = int(_clamp(velocity, 1, 127))

        filtered_events.append(
            dataclass_replace(
                event,
                velocity=velocity,
            )
        )

    return Timeline(filtered_events)


def _apply_arranger_midi_mix(midi_obj: pretty_midi.PrettyMIDI) -> None:
    if not midi_obj.instruments:
        return

    track_map = _arranger_tracks_map()
    if not track_map:
        return

    for instrument in midi_obj.instruments:
        name = instrument.name or ""
        base_name = name.split(" (", 1)[0] if name else ""
        track = track_map.get(name) or track_map.get(base_name)
        if not track:
            continue

        volume_cc = int(round(track.get("volume", 100) / 100.0 * 127))
        pan_value = track.get("pan", 0)
        pan_cc = int(round(((pan_value + 50) / 100.0) * 127))

        instrument.control_changes = [
            cc for cc in instrument.control_changes if cc.control not in (7, 10)
        ]
        instrument.control_changes.insert(0, pretty_midi.ControlChange(control=7, value=volume_cc, time=0.0))
        instrument.control_changes.insert(0, pretty_midi.ControlChange(control=10, value=pan_cc, time=0.0))

        effects = track.get("effects") or []
        if effects:
            instrument.name = f"{track['instrument']} ({', '.join(effects)})"
        else:
            instrument.name = track["instrument"]
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
    _workflow_guide()


def _render_session_overview(settings: SessionSettings) -> None:
    timeline: Timeline = st.session_state.timeline
    total_events = len(timeline.events)
    timeline_instruments = sorted({event.instrument for event in timeline.events})
    max_end = max((event.start + event.duration) for event in timeline.events) if timeline.events else 0.0

    st.markdown(
        f"""
        <div class="status-grid">
            <div class="status-card">
                <h4>Tonality</h4>
                <div class="status-value">{settings.tonality()}</div>
                <div class="status-footnote">Mood • {settings.mood}</div>
            </div>
            <div class="status-card">
                <h4>Tempo</h4>
                <div class="status-value">{settings.tempo} BPM</div>
                <div class="status-footnote">Groove • {settings.rhythm}</div>
            </div>
            <div class="status-card">
                <h4>Palette</h4>
                <div class="status-value">{settings.palette}</div>
                <div class="status-footnote">Instruments • {settings.instruments_label()}</div>
            </div>
            <div class="status-card">
                <h4>Timeline</h4>
                <div class="status-value">{total_events} clips</div>
                <div class="status-footnote">{len(timeline_instruments)} instruments • {max_end:.1f} beats</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_progression_summary(metadata: dict[str, Any]) -> None:
    chords: Sequence[str] = metadata.get("progression", [])
    chord_html = "".join(f"<span class='progression-chip'>{roman}</span>" for roman in chords)
    palette = metadata.get("palette", "")
    mood = metadata.get("mood", "")
    tempo = metadata.get("tempo", 0)
    tonality = f"{metadata.get('key', '')} {str(metadata.get('scale', '')).title()}".strip()
    instrument_tags = metadata.get("instruments", [])
    tags_html = "".join(f"<span class='instrument-tag'>🎚️ {name}</span>" for name in instrument_tags)

    st.markdown(
        f"""
        <div class="progression-card">
            <div class="progression-header">
                <span class="progression-title">Latest progression</span>
                <span class="progression-meta">{tonality} • {tempo} BPM • {mood}</span>
            </div>
            <div class="progression-chips">{chord_html}</div>
            <div style="margin-top: 0.9rem; display: flex; flex-wrap: wrap; gap: 0.4rem;">
                <span class="progression-meta">Palette • {palette}</span>
                {tags_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_arrangement_overview(sections: Sequence[dict[str, Any]]) -> None:
    if not sections:
        return

    rows: list[str] = []
    for section in sections:
        start_bar = int(section.get("start_bar", 0)) + 1
        length = int(section.get("n_bars", 0))
        end_bar = start_bar + max(length, 1) - 1
        chord_html = " – ".join(section.get("progression", []))
        instruments = ", ".join(section.get("instruments", []))
        hook_badge = (
            "<span class='arrangement-badge'>🎣 Hook</span>" if section.get("has_hook") else "—"
        )
        rows.append(
            """
            <tr>
                <td>{name}</td>
                <td>Bars {start}-{end}</td>
                <td>{chords}</td>
                <td>{instruments}</td>
                <td>{badge}</td>
            </tr>
            """.format(
                name=section.get("name", "Section"),
                start=start_bar,
                end=end_bar,
                chords=chord_html,
                instruments=instruments or "—",
                badge=hook_badge,
            )
        )

    table_html = """
        <table class='arrangement-table'>
            <thead>
                <tr>
                    <th>Section</th>
                    <th>Range</th>
                    <th>Progression</th>
                    <th>Instruments</th>
                    <th>Highlights</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    """.format(rows="".join(rows))

    hook_motif = next(
        (section.get("hook_motif", []) for section in sections if section.get("has_hook") and section.get("hook_motif")),
        [],
    )
    motif_html = "".join(f"<span class='progression-chip'>{note}</span>" for note in hook_motif)
    motif_block = (
        f"<div class='arrangement-motif'>Hook motif • <div class='progression-chips'>{motif_html}</div></div>"
        if motif_html
        else ""
    )

    st.markdown(
        f"""
        <div class='progression-card'>
            <div class='progression-header'>
                <span class='progression-title'>Song arrangement</span>
                <span class='progression-meta'>Automated verse/chorus layout</span>
            </div>
            {table_html}
            {motif_block}
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
    if "generated_midi" not in st.session_state:
        st.session_state.generated_midi = None
    if "generated_audio" not in st.session_state:
        st.session_state.generated_audio = None
    if "generator_metadata" not in st.session_state:
        st.session_state.generator_metadata = None
    if "musicgen_path" not in st.session_state:
        st.session_state.musicgen_path = None
    if "arrangement_sections" not in st.session_state:
        st.session_state.arrangement_sections = None
    _initialise_arranger_state(st.session_state.arrangement_sections)


def _settings_panel() -> SessionSettings:
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

    return SessionSettings(
        key=selected_key,
        scale=selected_scale,
        palette=selected_type,
        mood=selected_mood,
        tempo=selected_tempo,
        rhythm=selected_rhythm,
        instruments=selected_instruments,
    )


def _note_to_midi(note_name: str) -> int:
    return pretty_midi.note_name_to_number(note_name)


def _update_timeline_cursor() -> None:
    """Nudge the timeline cursor to the end of the current arrangement."""

    timeline: Timeline = st.session_state.timeline
    if not timeline.events:
        st.session_state.keyboard_cursor = 0.0
        return

    max_end = max(event.start + event.duration for event in timeline.events)
    st.session_state.keyboard_cursor = max_end


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
        _update_timeline_cursor()


def _register_keyboard_note(note_name: str, tempo: int) -> None:
    pitch = _note_to_midi(note_name)
    instrument = st.session_state.record_instrument
    velocity = 95

    if st.session_state.recording:
        elapsed = time.time() - st.session_state.record_start
        beats = elapsed * tempo / 60.0
        event = TimelineEvent(start=beats, duration=0.5, pitch=pitch, velocity=velocity, instrument=instrument)
        st.session_state.timeline.add_event(event)
        _update_timeline_cursor()
    else:
        cursor = st.session_state.keyboard_cursor
        event = TimelineEvent(start=cursor, duration=0.5, pitch=pitch, velocity=velocity, instrument=instrument)
        st.session_state.timeline.add_event(event)
        _update_timeline_cursor()
        st.session_state.keyboard_cursor = cursor + 0.5


def _handle_midi_message(message: MidiMessage, tempo: int) -> None:
    if not st.session_state.recording:
        if message.velocity <= 0:
            st.session_state.midi_note_starts.pop(message.note, None)
        return

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
    _update_timeline_cursor()


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


def _timeline_tab(settings: SessionSettings) -> None:
    tempo = settings.tempo
    timeline: Timeline = st.session_state.timeline

    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("Timeline editor", divider="rainbow")
    st.markdown("Tune takes, quantize and render your arrangement.")

    import_json_col, import_midi_col = st.columns(2)
    with import_json_col:
        uploaded_timeline = st.file_uploader(
            "Restore timeline from JSON",
            type=["json"],
            key="timeline-json-upload",
            help="Load a timeline exported from LofiSymphony or another compatible tool.",
        )
        if uploaded_timeline is not None:
            try:
                payload = json.loads(uploaded_timeline.getvalue().decode("utf-8"))
                events = [TimelineEvent.from_dict(event) for event in payload]
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                st.error(f"Unable to import timeline JSON: {exc}.")
            else:
                st.session_state.timeline = Timeline(events)
                _update_timeline_cursor()
                st.session_state.generated_midi = None
                st.session_state.generated_audio = None
                st.session_state.generator_metadata = None
                st.session_state.arrangement_sections = None
                _initialise_arranger_state(None, reset_lanes=True)
                st.session_state["timeline-json-upload"] = None
                st.success("Timeline restored from JSON.")
                st.rerun()

    with import_midi_col:
        uploaded_midi = st.file_uploader(
            "Import clips from MIDI",
            type=["mid", "midi"],
            key="timeline-midi-upload",
            help="Convert a MIDI file into timeline clips and merge it with the current session.",
        )
        if uploaded_midi is not None:
            try:
                _ingest_midi_into_timeline(uploaded_midi.getvalue())
            except Exception as exc:  # pretty_midi raises a variety of exceptions
                st.error(f"Unable to read MIDI file: {exc}.")
            else:
                st.session_state["timeline-midi-upload"] = None
                st.session_state.arrangement_sections = None
                _initialise_arranger_state(None, reset_lanes=True)
                st.success("MIDI file ingested into the timeline.")
                st.rerun()

    if timeline.events:
        timeline_instruments = sorted({event.instrument for event in timeline.events})
        max_end = max(event.start + event.duration for event in timeline.events)
        st.markdown(
            f"""
            <div class="progression-card" style="margin-top: 0.75rem;">
                <div class="progression-header">
                    <span class="progression-title">Session timeline</span>
                    <span class="progression-meta">{len(timeline.events)} clips • {max_end:.1f} beats</span>
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                    {''.join(f"<span class='instrument-tag'>🎚️ {name}</span>" for name in timeline_instruments)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    display_df = dataframe_for_display(timeline)
    with st.form("timeline-editor-form"):
        edited = st.data_editor(display_df, key="timeline-editor", num_rows="dynamic")
        apply = st.form_submit_button("Apply edits")
    if apply and isinstance(edited, pd.DataFrame):
        st.session_state.timeline.update_from_dataframe(edited)
        st.session_state.arrangement_sections = None

    col1, col2, col3 = st.columns(3)
    with col1:
        grid_options = [0.25, 0.5, 1.0]
        grid_labels = {0.25: "16th notes", 0.5: "8th notes", 1.0: "Quarter notes"}
        grid = st.selectbox("Quantize grid", grid_options, format_func=lambda v: grid_labels[v])
        if st.button("Quantize"):
            st.session_state.timeline.quantize(grid)
            st.session_state.arrangement_sections = None
            st.rerun()
    with col2:
        if st.button("Clear timeline"):
            st.session_state.timeline = Timeline()
            _update_timeline_cursor()
            st.session_state.arrangement_sections = None
            st.session_state.arranger_lanes = []
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
            _update_timeline_cursor()
            st.session_state.arrangement_sections = None
            st.rerun()

    st.plotly_chart(_timeline_plot(st.session_state.timeline), use_container_width=True)

    if not st.session_state.timeline.events:
        st.info("Add clips via the generator or performance desk to render the timeline.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    playback_timeline = _arranger_filtered_timeline(st.session_state.timeline)
    if not playback_timeline.events:
        st.warning("All tracks are muted or soloed away; nothing to render. Enable a track to export audio.")
    else:
        midi_obj = playback_timeline.to_pretty_midi(tempo)
        _apply_arranger_midi_mix(midi_obj)
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


def _performance_tab(settings: SessionSettings) -> None:
    tempo = settings.tempo
    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("Performance desk", divider="rainbow")
    _recording_controls(tempo)
    st.divider()
    _keyboard_block(tempo)
    st.divider()
    _midi_block(tempo)
    st.markdown("</div>", unsafe_allow_html=True)


def _arranger_tab(settings: SessionSettings) -> None:
    sections = st.session_state.get("arrangement_sections") or []
    _initialise_arranger_state(sections)
    tracks = st.session_state.arranger_tracks
    timeline: Timeline = st.session_state.timeline
    metadata = st.session_state.get("generator_metadata") or {}

    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("Arranger desk", divider="rainbow")
    st.caption(
        "Balance stems, automate sections and reshuffle clip lanes. These controls feed directly into playback and exports."
    )

    if metadata:
        chords = metadata.get("progression", [])
        palette = metadata.get("palette", settings.palette)
        tempo = metadata.get("tempo", settings.tempo)
        tonality = f"{metadata.get('key', settings.key)} {str(metadata.get('scale', settings.scale)).title()}"
        chord_html = "".join(f"<span class='progression-chip'>{chord}</span>" for chord in chords)
        st.markdown(
            f"""
            <div class="progression-card" style="margin-bottom: 1rem;">
                <div class="progression-header">
                    <span class="progression-title">Session palette</span>
                    <span class="progression-meta">{tonality} �?� {tempo} BPM �?� {palette}</span>
                </div>
                <div class="progression-chips">{chord_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    section_names = _arranger_section_names(sections)

    st.markdown("### Mixer controls")
    solo_active = any(track.get("solo") for track in tracks)
    for idx, track in enumerate(tracks):
        track_key = f"{track['name'].lower().replace(' ', '-')}-{idx}"
        container = st.container()
        with container:
            st.markdown(f"#### {track['name']} <small style='color:#94a3b8;'>({track['instrument']})</small>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1.1, 1.2, 1.7])

            mute_key = f"arranger-mute-{track_key}"
            solo_key = f"arranger-solo-{track_key}"
            volume_key = f"arranger-volume-{track_key}"
            pan_key = f"arranger-pan-{track_key}"
            fx_key = f"arranger-fx-{track_key}"

            mute_default = not track.get("enabled", True)
            solo_default = track.get("solo", False)
            volume_default = track.get("volume", 100)
            pan_default = track.get("pan", 0)
            effects_default = track.get("effects", [])

            mute = col1.toggle("Mute", value=mute_default, key=mute_key)
            solo = col1.toggle("Solo", value=solo_default, key=solo_key)

            volume = col2.slider("Volume", min_value=0, max_value=120, value=volume_default, key=volume_key)
            pan = col2.slider("Pan", min_value=-50, max_value=50, value=pan_default, format="%d", key=pan_key)

            effects = col3.multiselect(
                "Effects rack",
                EFFECT_PRESETS,
                default=effects_default,
                key=fx_key,
                help="Add flavour to this track. The playlist metadata carries these labels into exports.",
            )

            automation_key_prefix = f"arranger-automation-{track_key}"
            automation_map = track.get("automation", {})
            with col3.expander("Automation by section"):
                for section_name in section_names:
                    slider_key = f"{automation_key_prefix}-{section_name}"
                    default_value = automation_map.get(section_name, ARRANGER_AUTOMATION_DEFAULT)
                    automation_value = st.slider(
                        section_name,
                        min_value=0,
                        max_value=127,
                        value=default_value,
                        key=slider_key,
                        help="Adjust relative intensity per section (applied to MIDI velocity).",
                    )
                    automation_map[section_name] = automation_value

            track["enabled"] = not mute
            track["solo"] = solo
            track["volume"] = volume
            track["pan"] = pan
            track["effects"] = effects
            track["automation"] = automation_map

            if effects:
                fx_html = "".join(f"<span class='arranger-chip'>{effect}</span>" for effect in effects)
                st.markdown(f"<div style='margin-top:0.4rem;'>Active FX: {fx_html}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='margin-top:0.4rem; color:#64748b;'>Active FX: None</div>", unsafe_allow_html=True)

    st.session_state.arranger_tracks = tracks

    if solo_active:
        st.info("Solo mode enabled — muted tracks are still available but excluded from playback until solo is cleared.")

    st.markdown("### Clip lanes")
    _sync_arranger_from_sections(sections)
    lanes = list(st.session_state.get("arranger_lanes", []))
    track_map = _arranger_tracks_map()

    if lanes:
        prepared_records: list[dict[str, Any]] = []
        for record in lanes:
            base = dict(record)
            effects = track_map.get(base.get("Instrument", ""), {}).get("effects", [])
            base["Effects"] = ", ".join(effects) if effects else "—"
            prepared_records.append(base)
        lane_df = pd.DataFrame(prepared_records).sort_values("Order").reset_index(drop=True)
        st.caption("Drag row handles to reorder lanes. Edit start/length to reshape sections across instruments.")
        column_config = {
            "Order": st.column_config.NumberColumn("Order", disabled=True),
            "Section": st.column_config.SelectboxColumn("Section", options=section_names),
            "Instrument": st.column_config.SelectboxColumn("Instrument", options=list(track_map.keys())),
            "Start (beats)": st.column_config.NumberColumn("Start (beats)", min_value=0.0, step=0.25),
            "Length (beats)": st.column_config.NumberColumn("Length (beats)", min_value=0.5, step=0.5),
            "Effects": st.column_config.TextColumn("Effects", disabled=True),
        }
        edited_df = st.data_editor(
            lane_df,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            column_config=column_config,
            key="arranger-lanes-editor",
        )

        if isinstance(edited_df, pd.DataFrame):
            updated_records = edited_df.to_dict("records")
            # Normalise order and strip derived columns
            normalised_records: list[dict[str, Any]] = []
            for order, record in enumerate(updated_records):
                normalised_records.append(
                    {
                        "Order": order,
                        "Section": record.get("Section", "Global"),
                        "Instrument": record.get("Instrument"),
                        "Start (beats)": float(record.get("Start (beats)", 0.0)),
                        "Length (beats)": float(record.get("Length (beats)", BEATS_PER_BAR * 4)),
                    }
                )
            if normalised_records != st.session_state.arranger_lanes:
                st.session_state.arranger_lanes = normalised_records
                _update_sections_from_lanes(normalised_records)
                st.toast("Arranger lanes updated")
    else:
        st.info("No lane metadata yet. Create a structured arrangement or add clips to the timeline to seed lanes.")

    current_sections = st.session_state.get("arrangement_sections") or []
    if current_sections:
        rows = []
        for section in current_sections:
            start = section.get("start_bar", 0)
            n_bars = section.get("n_bars", 0)
            instruments = ", ".join(section.get("instruments", [])) or "None"
            hook_flag = "Yes" if section.get("has_hook") else "No"
            rows.append(
                f"<tr><td>{section.get('name')}</td><td>{start}</td><td>{n_bars}</td><td>{instruments}</td><td>{hook_flag}</td></tr>"
            )
        st.markdown(
            f"""
            <div style="margin-top: 1.5rem;">
                <h4 style="color: #cbd5f5; margin-bottom: 0.35rem;">Arrangement roadmap</h4>
                <table class="arranger-table">
                    <thead>
                        <tr>
                            <th>Section</th>
                            <th>Start bar</th>
                            <th>Length</th>
                            <th>Instruments</th>
                            <th>Hook</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if timeline.events:
        st.success(f"{len(timeline.events)} timeline clips active. Timeline playback honours the mixer settings above.")
    else:
        st.info("Generate a progression or record a take to populate the arranger.")

    st.markdown("</div>", unsafe_allow_html=True)


def _generator_tab(settings: SessionSettings) -> None:
    selected_key = settings.key
    selected_scale = settings.scale
    selected_type = settings.palette
    selected_mood = settings.mood
    selected_tempo = settings.tempo
    selected_rhythm = settings.rhythm
    selected_instruments = settings.instruments
    st.markdown("<div class='lofi-card'>", unsafe_allow_html=True)
    st.subheader("AI-assisted ideas", divider="rainbow")

    st.caption("Pair curated MIDI seeds with Audiocraft layers to sketch tracks in minutes.")

    col1, col2 = st.columns([0.58, 0.42])
    with col1:
        st.markdown("### Generate MIDI scaffold")
        st.caption("Roll harmonic DNA tailored to your palette and drop it straight on the timeline.")
        if st.button("🎶 Generate progression", use_container_width=True):
            progression_pool = TYPE_PROGRESSIONS.get(selected_type, TYPE_PROGRESSIONS["Chillhop"])
            progression_choice = random.choice(progression_pool)
            midi_bytes = generate_lofi_midi(
                key=selected_key,
                scale=selected_scale,
                tempo=selected_tempo,
                lofi_type=selected_type,
                rhythm=selected_rhythm,
                mood=selected_mood,
                instruments=selected_instruments,
                progression=progression_choice,
            )
            midi_payload = midi_bytes.getvalue()
            st.session_state.generated_midi = midi_payload
            st.session_state.generator_metadata = {
                "progression": progression_choice,
                "palette": selected_type,
                "mood": selected_mood,
                "tempo": selected_tempo,
                "key": selected_key,
                "scale": selected_scale,
                "instruments": list(selected_instruments),
            }
            st.session_state.arrangement_sections = None
            _ingest_midi_into_timeline(midi_payload)
            st.session_state.timeline.quantize(0.25)
            audio_segment = midi_to_audio(io.BytesIO(midi_payload))
            audio_buffer = io.BytesIO()
            audio_segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)
            st.session_state.generated_audio = audio_buffer.getvalue()
            _initialise_arranger_state(st.session_state.arrangement_sections, reset_lanes=True)
            st.toast("MIDI idea injected into the timeline ✨")

        if st.button("🧱 Generate full arrangement", use_container_width=True):
            sections: list[SectionArrangement]
            midi_stream, sections = generate_structured_song(
                key=selected_key,
                scale=selected_scale,
                tempo=selected_tempo,
                lofi_type=selected_type,
                rhythm=selected_rhythm,
                mood=selected_mood,
                instruments=selected_instruments,
            )
            midi_payload = midi_stream.getvalue()
            st.session_state.timeline = Timeline()
            _ingest_midi_into_timeline(midi_payload)
            st.session_state.timeline.quantize(0.25)
            st.session_state.generated_midi = midi_payload
            st.session_state.arrangement_sections = [section.to_dict() for section in sections]
            st.session_state.generator_metadata = {
                "progression": sections[0].progression if sections else [],
                "palette": selected_type,
                "mood": selected_mood,
                "tempo": selected_tempo,
                "key": selected_key,
                "scale": selected_scale,
                "instruments": list(selected_instruments),
                "arrangement": st.session_state.arrangement_sections,
                "hook_motif": next(
                    (section["hook_motif"] for section in st.session_state.arrangement_sections if section["has_hook"] and section["hook_motif"]),
                    [],
                ),
            }
            audio_segment = midi_to_audio(io.BytesIO(midi_payload))
            audio_buffer = io.BytesIO()
            audio_segment.export(audio_buffer, format="wav")
            audio_buffer.seek(0)
            st.session_state.generated_audio = audio_buffer.getvalue()
            _initialise_arranger_state(st.session_state.arrangement_sections, reset_lanes=True)
            st.toast("Structured arrangement added to the timeline 🎼")

        metadata = st.session_state.generator_metadata
        if metadata:
            _render_progression_summary(metadata)
        arrangement_sections = st.session_state.arrangement_sections
        if arrangement_sections:
            _render_arrangement_overview(arrangement_sections)

        audio_bytes = st.session_state.generated_audio
        midi_bytes_payload = st.session_state.generated_midi
        if audio_bytes:
            st.audio(io.BytesIO(audio_bytes))
            st.download_button(
                "Download generated WAV",
                data=audio_bytes,
                file_name="lofi_idea.wav",
                mime="audio/wav",
                key="download-generated-wav",
            )
        if midi_bytes_payload:
            st.download_button(
                "Download generated MIDI",
                data=midi_bytes_payload,
                file_name="lofi_idea.mid",
                mime="audio/midi",
                key="download-generated-midi",
            )

    with col2:
        st.markdown("### MusicGen preview")
        st.caption("Send evocative prompts to craft shimmering textures and atmospheres.")
        if not MUSICGEN_AVAILABLE:
            st.info(
                "MusicGen extras are not installed. Run `python launcher.py --with-musicgen` "
                "in the project folder to enable text-to-music rendering."
            )
        prompt = st.text_area(
            "Prompt",
            value="A dusty lofi beat with warm chords and vinyl crackle",
            key="musicgen-prompt",
        )
        duration = st.slider(
            "Duration",
            min_value=8.0,
            max_value=30.0,
            value=12.0,
            step=1.0,
            key="musicgen-duration",
        )
        if st.button("✨ Render with MusicGen", use_container_width=True):
            try:
                with st.spinner("Rendering with Audiocraft..."):
                    audio_path = render_musicgen(AudiocraftSettings(prompt=prompt, duration=duration))
                st.session_state.musicgen_path = audio_path
                st.success("MusicGen render ready for audition.")
            except AudiocraftUnavailable as exc:
                st.warning(str(exc))

        musicgen_path = st.session_state.musicgen_path
        if musicgen_path:
            st.audio(str(musicgen_path))
            try:
                with open(musicgen_path, "rb") as handle:
                    musicgen_bytes = handle.read()
                st.download_button(
                    "Download MusicGen WAV",
                    data=musicgen_bytes,
                    file_name="musicgen_preview.wav",
                    mime="audio/wav",
                    key="download-musicgen-wav",
                )
            except FileNotFoundError:
                st.info("Generated preview not found on disk – rerun to regenerate.")

    st.divider()
    st.markdown("### Blend MusicGen with MIDI")
    st.caption("Fuse symbolic MIDI with generative audio for instant hybrid stems.")
    with st.form("musicgen-blend"):
        blend_prompt = st.text_input(
            "Blend prompt",
            value="Lo-fi beat with mellow keys and gentle sidechain pumping",
        )
        submitted = st.form_submit_button("Create hybrid render")
        if submitted:
            try:
                with st.spinner("Sculpting hybrid stem..."):
                    blended = generate_musicgen_backing(
                        prompt=blend_prompt,
                        key=selected_key,
                        scale=selected_scale,
                        tempo=selected_tempo,
                        instruments=selected_instruments,
                    )
                st.audio(str(blended))
                with open(blended, "rb") as handle:
                    blend_bytes = handle.read()
                st.download_button(
                    "Download blend",
                    data=blend_bytes,
                    file_name="musicgen_blend.wav",
                    mime="audio/wav",
                )
            except AudiocraftUnavailable as exc:
                st.warning(str(exc))

    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="LofiSymphony Studio", page_icon="🎵", layout="wide")

    _initialise_state()
    _render_css()
    _render_header()

    settings = _settings_panel()
    _render_session_overview(settings)

    generator_tab, performance_tab, arranger_tab, timeline_tab = st.tabs(
        ["Generator", "Performance", "Arranger", "Timeline"]
    )
    with generator_tab:
        _generator_tab(settings)
    with performance_tab:
        _performance_tab(settings)
    with arranger_tab:
        _arranger_tab(settings)
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
