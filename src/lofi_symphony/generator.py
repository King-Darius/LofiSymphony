"""Core music generation and rendering utilities for LofiSymphony."""

from __future__ import annotations

import io
import os
import random
import subprocess
import tempfile
import warnings
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np
import pretty_midi
from music21 import chord, key as m21key, pitch as m21pitch
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError
from pydub.generators import WhiteNoise

from .fluidsynth_assets import (
    SOUNDFONT_ENV_VAR,
    resolve_fluidsynth_executable,
    resolve_soundfont_path,
)

__all__ = [
    "generate_lofi_midi",
    "generate_structured_song",
    "midi_to_audio",
    "TYPE_PROGRESSIONS",
    "TYPE_INSTRUMENTS",
    "MOOD_TEMPO",
    "AVAILABLE_INSTRUMENTS",
    "SectionArrangement",
]

TYPE_PROGRESSIONS = {
    "Chillhop": [["i7", "iv7", "bVII7", "i7"], ["i7", "VI7", "III7", "VII7"]],
    "Jazzhop": [["ii7", "V7", "Imaj7", "vi7"], ["Imaj7", "vi7", "ii7", "V7"]],
    "Boom Bap": [["i", "bVII", "bVI", "bVII"], ["i", "v", "i", "bVII"]],
    "Dreamy": [["Imaj7", "vi7", "IVmaj7", "V7"], ["Imaj7", "IVmaj7", "V7", "vi7"]],
    "Classic LoFi": [["i7", "bVII7", "iv7", "V7"]],
    "Ambient": [["i", "iv", "bVI", "v"]],
}

TYPE_INSTRUMENTS = {
    "Chillhop": ["Rhodes", "Bass", "Drums", "FX"],
    "Jazzhop": ["Piano", "Bass", "Drums", "Guitar"],
    "Boom Bap": ["Piano", "Bass", "Drums"],
    "Dreamy": ["Synth", "Rhodes", "FX"],
    "Classic LoFi": ["Piano", "Bass", "Drums"],
    "Ambient": ["Synth", "FX"],
}

MOOD_TEMPO = {
    "Chill": 72,
    "Happy": 92,
    "Sad": 68,
    "Nostalgic": 74,
    "Energetic": 108,
    "Melancholic": 62,
}

AVAILABLE_INSTRUMENTS = ["Piano", "Rhodes", "Synth", "Guitar", "Bass", "Drums", "FX"]

INSTRUMENT_PROGRAMS = {
    "Piano": 0,
    "Rhodes": 4,
    "Synth": 81,
    "Guitar": 25,
    "Bass": 33,
}

DRUM_NOTE_MAP = {
    "kick": 36,
    "snare": 38,
    "hat_closed": 42,
}


@dataclass(frozen=True)
class SectionArrangement:
    """Descriptor for an arranged section rendered by :func:`generate_structured_song`."""

    name: str
    start_bar: int
    n_bars: int
    progression: Sequence[str]
    instruments: Sequence[str]
    has_hook: bool
    hook_motif: Sequence[str]

    def to_dict(self) -> dict[str, Sequence[str] | int | str | bool]:
        return {
            "name": self.name,
            "start_bar": self.start_bar,
            "n_bars": self.n_bars,
            "progression": list(self.progression),
            "instruments": list(self.instruments),
            "has_hook": self.has_hook,
            "hook_motif": list(self.hook_motif),
        }


def _dedupe_instruments(instruments: Sequence[str]) -> List[str]:
    """Return instruments filtered to project availability preserving order."""

    seen: set[str] = set()
    filtered: List[str] = []
    for name in instruments:
        if name not in AVAILABLE_INSTRUMENTS:
            continue
        if name in seen:
            continue
        seen.add(name)
        filtered.append(name)
    return filtered


def _scale_note_names(musical_key: m21key.Key) -> List[str]:
    names = [_pitch_to_pretty_name(p).rstrip("0123456789") for p in musical_key.getPitches()]
    return names or ["C", "E", "G", "Bb"]


def _generate_hook_motif(musical_key: m21key.Key, *, octave: int = 5) -> List[str]:
    """Create a short melodic motif highlighting the tonic triad."""

    scale_notes = _scale_note_names(musical_key)
    start_index = random.randint(0, len(scale_notes) - 1)
    pattern = [0, 2, 4, 2]
    motif: List[str] = []
    for offset in pattern:
        degree = (start_index + offset) % len(scale_notes)
        octave_offset = (start_index + offset) // len(scale_notes)
        note = f"{scale_notes[degree]}{octave + octave_offset}"
        motif.append(note)
    return motif


@dataclass(frozen=True)
class _SectionBlueprint:
    name: str
    n_bars: int
    progression: Sequence[str]
    instruments: Sequence[str]
    has_hook: bool = False


def _build_arrangement_plan(
    *,
    lofi_type: str,
    base_instruments: Sequence[str],
    progression_pool: Sequence[Sequence[str]],
) -> List[_SectionBlueprint]:
    """Generate a high-level arrangement plan given palette preferences."""

    if not progression_pool:
        progression_pool = TYPE_PROGRESSIONS["Chillhop"]

    primary = random.choice(progression_pool)
    secondary_candidates = [prog for prog in progression_pool if prog != primary]
    secondary = random.choice(secondary_candidates or [primary])

    base_palette = _dedupe_instruments(base_instruments) or TYPE_INSTRUMENTS.get(lofi_type, ["Piano", "Bass", "Drums"])

    intro_palette = _dedupe_instruments([inst for inst in base_palette if inst != "Drums"] + (["FX"] if "FX" in AVAILABLE_INSTRUMENTS else []))
    if not intro_palette:
        intro_palette = base_palette

    chorus_palette = _dedupe_instruments(list(base_palette) + ["Synth", "Drums"])
    hook_palette = _dedupe_instruments(["Synth", "Drums", "FX"] + list(base_palette))
    outro_palette = _dedupe_instruments([inst for inst in base_palette if inst != "Drums"] + (["FX"] if "FX" in AVAILABLE_INSTRUMENTS else []))
    if not outro_palette:
        outro_palette = base_palette

    return [
        _SectionBlueprint(name="Intro", n_bars=4, progression=primary, instruments=intro_palette),
        _SectionBlueprint(name="Verse", n_bars=8, progression=primary, instruments=base_palette),
        _SectionBlueprint(name="Chorus", n_bars=8, progression=secondary, instruments=chorus_palette, has_hook=True),
        _SectionBlueprint(name="Verse 2", n_bars=8, progression=primary, instruments=base_palette),
        _SectionBlueprint(name="Hook", n_bars=4, progression=secondary, instruments=hook_palette, has_hook=True),
        _SectionBlueprint(name="Outro", n_bars=4, progression=primary, instruments=outro_palette),
    ]


def _apply_hook_layer(pm: pretty_midi.PrettyMIDI, n_bars: int, motif: Sequence[str]) -> None:
    if not motif:
        return

    program = INSTRUMENT_PROGRAMS.get("Synth", 81)
    hook_instrument = pretty_midi.Instrument(program=program, name="Hook Lead")
    bar_duration = 2.0
    step_duration = max(0.25, bar_duration / max(len(motif), 1))

    for bar in range(n_bars):
        for idx, note_name in enumerate(motif):
            start = bar * bar_duration + idx * step_duration
            start = max(0.0, _humanize(start, amount=0.02))
            end = start + step_duration * 0.85
            pitch = pretty_midi.note_name_to_number(note_name)
            hook_instrument.notes.append(
                pretty_midi.Note(
                    velocity=random.randint(70, 88),
                    pitch=pitch,
                    start=start,
                    end=end,
                )
            )

    pm.instruments.append(hook_instrument)


def _pitch_to_pretty_name(pitch_obj: m21pitch.Pitch) -> str:
    """Return a pretty_midi-compatible name for a music21 pitch."""

    return pretty_midi.note_number_to_name(int(round(pitch_obj.midi)))


def _get_chord_pitches(roman: str, musical_key: m21key.Key) -> List[str]:
    chord_obj = chord.Chord(musical_key.romanNumeral(roman).pitches)
    return [_pitch_to_pretty_name(p) for p in chord_obj.pitches]


def _humanize(value: float, amount: float = 0.03) -> float:
    return float(value) + np.random.uniform(-amount, amount)


def _add_drum_track(pm: pretty_midi.PrettyMIDI, n_bars: int, rhythm: str) -> None:
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True)
    swing_offset = 0.12 if rhythm == "Swing" else 0.0

    for bar in range(n_bars):
        start_beat = bar * 2
        drum_inst.notes.append(
            pretty_midi.Note(velocity=80, pitch=DRUM_NOTE_MAP["kick"], start=start_beat, end=start_beat + 0.12)
        )
        drum_inst.notes.append(
            pretty_midi.Note(velocity=75, pitch=DRUM_NOTE_MAP["snare"], start=start_beat + 1, end=start_beat + 1.12)
        )

        for step in range(4):
            offset = (0.5 * step) + (swing_offset if step % 2 else 0.0)
            drum_inst.notes.append(
                pretty_midi.Note(
                    velocity=55,
                    pitch=DRUM_NOTE_MAP["hat_closed"],
                    start=start_beat + offset,
                    end=start_beat + offset + 0.09,
                )
            )

    pm.instruments.append(drum_inst)


def _add_fx_layer(audio: AudioSegment) -> AudioSegment:
    noise = WhiteNoise().to_audio_segment(duration=len(audio), volume=-32)
    vinyl = noise.low_pass_filter(3000)
    return audio.overlay(vinyl)


def _placeholder_audio_from_midi(midi_payload: bytes) -> AudioSegment:
    """Generate a silent audio placeholder that matches the MIDI length."""

    try:
        midi_stream = io.BytesIO(midi_payload)
        midi_stream.seek(0)
        midi_data = pretty_midi.PrettyMIDI(midi_stream)
        duration_ms = int(max(midi_data.get_end_time(), 0.5) * 1000)
    except Exception:
        duration_ms = 2000
    duration_ms = max(duration_ms, 500)
    return AudioSegment.silent(duration=duration_ms)


def generate_lofi_midi(
    *,
    key: str = "C",
    scale: str = "minor",
    tempo: int = 72,
    lofi_type: str = "Chillhop",
    rhythm: str = "Straight",
    mood: str = "Chill",
    instruments: Sequence[str] | None = None,
    n_bars: int = 8,
    progression: Sequence[str] | None = None,
) -> io.BytesIO:
    """Generate a LoFi MIDI track and return the raw bytes."""

    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    key_obj = m21key.Key(key, scale)
    if progression is None:
        progression_sequence = random.choice(TYPE_PROGRESSIONS.get(lofi_type, TYPE_PROGRESSIONS["Chillhop"]))
    else:
        progression_sequence = list(progression)

    selected_instruments: Iterable[str] = instruments or AVAILABLE_INSTRUMENTS

    for instrument_name in selected_instruments:
        if instrument_name == "Bass":
            inst = pretty_midi.Instrument(program=INSTRUMENT_PROGRAMS["Bass"])
            for bar in range(n_bars):
                chord_roman = progression_sequence[bar % len(progression_sequence)]
                root_note = _get_chord_pitches(chord_roman, key_obj)[0]
                root_name = root_note.rstrip("0123456789")
                note = pretty_midi.Note(
                    velocity=random.randint(55, 75),
                    pitch=pretty_midi.note_name_to_number(f"{root_name}2"),
                    start=bar * 2 + _humanize(0),
                    end=bar * 2 + _humanize(1.6),
                )
                inst.notes.append(note)
            pm.instruments.append(inst)
            continue

        if instrument_name in INSTRUMENT_PROGRAMS:
            inst = pretty_midi.Instrument(program=INSTRUMENT_PROGRAMS[instrument_name])
            scale_notes = [
                _pitch_to_pretty_name(p).rstrip("0123456789") for p in key_obj.getPitches()
            ]
            for bar in range(n_bars):
                chord_roman = progression_sequence[bar % len(progression_sequence)]
                chord_pitches = _get_chord_pitches(chord_roman, key_obj)
                for pitch_name in chord_pitches:
                    note = pretty_midi.Note(
                        velocity=random.randint(60, 85),
                        pitch=pretty_midi.note_name_to_number(pitch_name),
                        start=bar * 2 + _humanize(0),
                        end=bar * 2 + _humanize(1.8),
                    )
                    inst.notes.append(note)

                for beat in range(4):
                    if random.random() < 0.7:
                        pitch_choice = random.choice(scale_notes)
                        octave = random.choice([4, 5])
                        note = pretty_midi.Note(
                            velocity=random.randint(50, 75),
                            pitch=pretty_midi.note_name_to_number(f"{pitch_choice}{octave}"),
                            start=bar * 2 + _humanize(beat * 0.5),
                            end=bar * 2 + _humanize(beat * 0.5 + 0.4),
                        )
                        inst.notes.append(note)
            pm.instruments.append(inst)
            continue

        if instrument_name == "Drums":
            _add_drum_track(pm, n_bars=n_bars, rhythm=rhythm)

    midi_bytes = io.BytesIO()
    pm.write(midi_bytes)
    midi_bytes.seek(0)
    return midi_bytes


def generate_structured_song(
    *,
    key: str = "C",
    scale: str = "minor",
    tempo: int = 72,
    lofi_type: str = "Chillhop",
    rhythm: str = "Straight",
    mood: str = "Chill",
    instruments: Sequence[str] | None = None,
) -> tuple[io.BytesIO, List[SectionArrangement]]:
    """Generate a multi-section arrangement with an optional hook motif."""

    progression_pool = TYPE_PROGRESSIONS.get(lofi_type, TYPE_PROGRESSIONS["Chillhop"])
    base_instruments = instruments or TYPE_INSTRUMENTS.get(lofi_type, AVAILABLE_INSTRUMENTS)
    key_obj = m21key.Key(key, scale)
    plan = _build_arrangement_plan(
        lofi_type=lofi_type,
        base_instruments=base_instruments,
        progression_pool=progression_pool,
    )
    hook_motif = _generate_hook_motif(key_obj)
    master_midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    sections: List[SectionArrangement] = []
    bar_duration = 2.0
    current_bar = 0

    for section in plan:
        section_midi_bytes = generate_lofi_midi(
            key=key,
            scale=scale,
            tempo=tempo,
            lofi_type=lofi_type,
            rhythm=rhythm,
            mood=mood,
            instruments=section.instruments,
            n_bars=section.n_bars,
            progression=section.progression,
        )
        section_pm = pretty_midi.PrettyMIDI(io.BytesIO(section_midi_bytes.getvalue()))
        if section.has_hook:
            _apply_hook_layer(section_pm, section.n_bars, hook_motif)

        for instrument in section_pm.instruments:
            for note in instrument.notes:
                note.start += current_bar * bar_duration
                note.end += current_bar * bar_duration
        master_midi.instruments.extend(section_pm.instruments)

        sections.append(
            SectionArrangement(
                name=section.name,
                start_bar=current_bar,
                n_bars=section.n_bars,
                progression=section.progression,
                instruments=section.instruments,
                has_hook=section.has_hook,
                hook_motif=hook_motif if section.has_hook else [],
            )
        )

        current_bar += section.n_bars

    midi_bytes = io.BytesIO()
    master_midi.write(midi_bytes)
    midi_bytes.seek(0)
    return midi_bytes, sections


def midi_to_audio(
    midi_bytes: io.BytesIO,
    *,
    soundfont: str | None = None,
    add_vinyl_fx: bool = False,
) -> AudioSegment:
    """Render a MIDI byte stream to audio using FluidSynth when available."""

    midi_bytes.seek(0)
    midi_payload = midi_bytes.getvalue()

    if soundfont and not os.path.exists(soundfont):
        raise FileNotFoundError(f"Soundfont not found at {soundfont}")

    def _fallback(reason: str) -> AudioSegment:
        warnings.warn(
            (
                f"{reason} Falling back to a silent preview – install FluidSynth and a soundfont "
                "for full audio rendering."
            ),
            RuntimeWarning,
            stacklevel=2,
        )
        placeholder = _placeholder_audio_from_midi(midi_payload)
        return _add_fx_layer(placeholder) if add_vinyl_fx else placeholder

    soundfont_path = resolve_soundfont_path(soundfont)

    if soundfont_path is None:
        return _fallback(
            "No soundfont found. "
            f"Set {SOUNDFONT_ENV_VAR} or place a General MIDI .sf2 next to the app."
        )

    fluidsynth_exec = resolve_fluidsynth_executable()
    if fluidsynth_exec is None:
        return _fallback("FluidSynth executable not available.")

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as midi_file:
        midi_file.write(midi_payload)
        midi_path = midi_file.name

    wav_path = midi_path.replace(".mid", ".wav")
    cmd = [fluidsynth_exec, "-ni", soundfont_path, midi_path, "-F", wav_path, "-r", "44100"]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        audio = AudioSegment.from_file(wav_path)
        if add_vinyl_fx:
            audio = _add_fx_layer(audio)
        return audio
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, CouldntDecodeError) as exc:
        return _fallback(f"FluidSynth rendering failed ({exc}).")
    finally:
        if os.path.exists(midi_path):
            os.remove(midi_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)
