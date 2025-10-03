"""Core music generation and rendering utilities for LofiSymphony."""

from __future__ import annotations

import io
import os
import random
import subprocess
import tempfile
from typing import Iterable, List, Sequence

import numpy as np
import pretty_midi
from music21 import chord, key as m21key, pitch as m21pitch
from pydub import AudioSegment
from pydub.generators import WhiteNoise

__all__ = [
    "generate_lofi_midi",
    "midi_to_audio",
    "TYPE_PROGRESSIONS",
    "TYPE_INSTRUMENTS",
    "MOOD_TEMPO",
    "AVAILABLE_INSTRUMENTS",
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
) -> io.BytesIO:
    """Generate a LoFi MIDI track and return the raw bytes."""

    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    key_obj = m21key.Key(key, scale)
    progression = random.choice(TYPE_PROGRESSIONS.get(lofi_type, TYPE_PROGRESSIONS["Chillhop"]))

    selected_instruments: Iterable[str] = instruments or AVAILABLE_INSTRUMENTS

    for instrument_name in selected_instruments:
        if instrument_name == "Bass":
            inst = pretty_midi.Instrument(program=INSTRUMENT_PROGRAMS["Bass"])
            for bar in range(n_bars):
                chord_roman = progression[bar % len(progression)]
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
                chord_roman = progression[bar % len(progression)]
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


def midi_to_audio(midi_bytes: io.BytesIO, *, soundfont: str | None = None, add_vinyl_fx: bool = True) -> AudioSegment:
    """Render a MIDI byte stream to audio using FluidSynth."""

    if soundfont and not os.path.exists(soundfont):
        raise FileNotFoundError(f"Soundfont not found at {soundfont}")

    env_soundfont = os.getenv("LOFI_SYMPHONY_SOUNDFONT")
    default_soundfonts: List[str] = [
        soundfont,
        env_soundfont,
        "/usr/share/sounds/sf2/FluidR3_GM.sf2",
        "/usr/share/soundfonts/default.sf2",
        os.path.join(os.getcwd(), "default.sf2"),
    ]
    soundfont_path = next((path for path in default_soundfonts if path and os.path.exists(path)), None)

    if soundfont_path is None:
        raise RuntimeError(
            "No soundfont found. Install FluidSynth and a compatible .sf2 soundfont to enable audio rendering."
        )

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as midi_file:
        midi_file.write(midi_bytes.getvalue())
        midi_path = midi_file.name

    wav_path = midi_path.replace(".mid", ".wav")
    cmd = ["fluidsynth", "-ni", soundfont_path, midi_path, "-F", wav_path, "-r", "44100"]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        audio = AudioSegment.from_file(wav_path)
        if add_vinyl_fx:
            audio = _add_fx_layer(audio)
        return audio
    finally:
        if os.path.exists(midi_path):
            os.remove(midi_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)
