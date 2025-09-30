import random
import numpy as np
import pretty_midi
from music21 import chord, stream, note, key, meter

# Choose a key and tempo
KEY = "C"
SCALE = "minor"
TEMPO = 72  # bpm

# Chord progressions (jazz/lofi inspired)
PROGRESSIONS = [
    ["i7", "iv7", "bVII7", "i7"],
    ["i7", "VI7", "III7", "VII7"],
    ["i7", "bVII7", "iv7", "V7"],
]

def get_chord_notes(roman, k):
    c = chord.Chord(k.romanNumeral(roman).pitches)
    return [p.nameWithOctave for p in c.pitches]

def humanize(t, amount=0.03):
    return t + np.random.uniform(-amount, amount)

def generate_chord_track(pm, key_obj, progression, n_bars, instrument=0):
    inst = pretty_midi.Instrument(program=instrument)  # Acoustic Grand Piano
    for bar in range(n_bars):
        chord_roman = progression[bar % len(progression)]
        pitches = get_chord_notes(chord_roman, key_obj)
        for pitch in pitches:
            n = pretty_midi.Note(
                velocity=random.randint(60, 85),
                pitch=pretty_midi.note_name_to_number(pitch),
                start=bar*2 + humanize(0),
                end=bar*2 + humanize(1.8)
            )
            inst.notes.append(n)
    pm.instruments.append(inst)

def generate_bass_track(pm, key_obj, progression, n_bars, instrument=33):
    inst = pretty_midi.Instrument(program=instrument)  # Acoustic Bass
    for bar in range(n_bars):
        chord_roman = progression[bar % len(progression)]
        root = get_chord_notes(chord_roman, key_obj)[0]
        n = pretty_midi.Note(
            velocity=random.randint(55, 75),
            pitch=pretty_midi.note_name_to_number(root[:-1] + "2"),
            start=bar*2 + humanize(0),
            end=bar*2 + humanize(1.6)
        )
        inst.notes.append(n)
    pm.instruments.append(inst)

def generate_melody(pm, key_obj, progression, n_bars, instrument=81):
    inst = pretty_midi.Instrument(program=instrument)  # Lead
    scale = key_obj.getPitches()
    for bar in range(n_bars):
        for beat in range(4):
            if random.random() < 0.7:
                pitch = random.choice(scale)
                n = pretty_midi.Note(
                    velocity=random.randint(50, 75),
                    pitch=pretty_midi.note_name_to_number(pitch.nameWithOctave[:-1] + str(random.choice([4,5]))),
                    start=bar*2 + humanize(beat*0.5),
                    end=bar*2 + humanize(beat*0.5 + 0.4)
                )
                inst.notes.append(n)
    pm.instruments.append(inst)

def generate_lofi_track(filename="lofi.mid"):
    pm = pretty_midi.PrettyMIDI(initial_tempo=TEMPO)
    key_obj = key.Key(KEY, SCALE)
    progression = random.choice(PROGRESSIONS)
    n_bars = 8

    generate_chord_track(pm, key_obj, progression, n_bars)
    generate_bass_track(pm, key_obj, progression, n_bars)
    generate_melody(pm, key_obj, progression, n_bars)

    pm.write(filename)
    print(f"Generated {filename} - import into a DAW or use a MIDI player for playback!")

if __name__ == "__main__":
    generate_lofi_track()