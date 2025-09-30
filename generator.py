import random
import numpy as np
import pretty_midi
import io
from music21 import chord, key as m21key, scale as m21scale
from pydub import AudioSegment
from pydub.generators import WhiteNoise

# Map type/mood to progressions, rhythms, instrument defaults
TYPE_PROGRESSIONS = {
    'Chillhop': [["i7", "iv7", "bVII7", "i7"], ["i7", "VI7", "III7", "VII7"]],
    'Jazzhop': [["ii7", "V7", "Imaj7", "vi7"], ["Imaj7", "vi7", "ii7", "V7"]],
    'Boom Bap': [["i", "bVII", "bVI", "bVII"], ["i", "v", "i", "bVII"]],
    'Dreamy': [["Imaj7", "vi7", "IVmaj7", "V7"], ["Imaj7", "IVmaj7", "V7", "vi7"]],
    'Classic LoFi': [["i7", "bVII7", "iv7", "V7"]],
    'Ambient': [["i", "iv", "bVI", "v"]],
}
TYPE_INSTRUMENTS = {
    'Chillhop': ['Rhodes', 'Bass', 'Drums', 'FX'],
    'Jazzhop': ['Piano', 'Bass', 'Drums', 'Guitar'],
    'Boom Bap': ['Piano', 'Bass', 'Drums'],
    'Dreamy': ['Synth', 'Rhodes', 'FX'],
    'Classic LoFi': ['Piano', 'Bass', 'Drums'],
    'Ambient': ['Synth', 'FX'],
}
MOOD_TEMPO = {
    'Chill': 72,
    'Happy': 92,
    'Sad': 68,
    'Nostalgic': 74,
    'Energetic': 108,
    'Melancholic': 62
}
INSTRUMENT_PROGRAMS = {
    'Piano': 0, 'Rhodes': 4, 'Synth': 81, 'Guitar': 25, 'Bass': 33
}

def get_chord_notes(roman, k):
    c = chord.Chord(k.romanNumeral(roman).pitches)
    return [p.nameWithOctave for p in c.pitches]

def humanize(t, amount=0.03):
    return float(t) + np.random.uniform(-amount, amount)

def add_drum_track(pm, n_bars, tempo, rhythm):
    drum_inst = pretty_midi.Instrument(program=0, is_drum=True)
    swing = 0.12 if rhythm == 'Swing' else 0
    for bar in range(n_bars):
        start_beat = bar * 2
        # Kick on 1, Snare on 3, Hats on 1/8 notes with optional swing
        drum_inst.notes.append(pretty_midi.Note(80, 36, start_beat, start_beat + 0.12))
        drum_inst.notes.append(pretty_midi.Note(75, 38, start_beat + 1, start_beat + 1.12))
        for i in range(4):
            offset = (0.5 * i) + (swing if i % 2 == 1 else 0)
            drum_inst.notes.append(pretty_midi.Note(50, 42, start_beat + offset, start_beat + offset + 0.09))
    pm.instruments.append(drum_inst)

def generate_lofi_midi(
    key="C",
    scale="minor",
    tempo=72,
    lofi_type="Chillhop",
    rhythm="Straight",
    mood="Chill",
    instruments=None,
    n_bars=8
):
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    key_obj = m21key.Key(key, scale)
    progression = random.choice(TYPE_PROGRESSIONS.get(lofi_type, [["i7", "iv7", "bVII7", "i7"]]))

    # Chords, melody, bass, etc.
    for inst_name in (instruments or []):
        if inst_name == 'Bass':
            inst = pretty_midi.Instrument(program=INSTRUMENT_PROGRAMS['Bass'])
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
        elif inst_name in INSTRUMENT_PROGRAMS:
            inst = pretty_midi.Instrument(program=INSTRUMENT_PROGRAMS[inst_name])
            scale_notes = key_obj.getPitches()
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
                # Simple melody
                for beat in range(4):
                    if random.random() < 0.7:
                        pitch = random.choice(scale_notes)
                        n = pretty_midi.Note(
                            velocity=random.randint(50, 75),
                            pitch=pretty_midi.note_name_to_number(pitch.nameWithOctave[:-1] + str(random.choice([4,5]))),
                            start=bar*2 + humanize(beat*0.5),
                            end=bar*2 + humanize(beat*0.5 + 0.4)
                        )
                        inst.notes.append(n)
            pm.instruments.append(inst)
        elif inst_name == 'Drums':
            add_drum_track(pm, n_bars, tempo, rhythm)
        elif inst_name == 'FX':
            # FX will be added in audio layer if needed
            pass

    midi_bytes = io.BytesIO()
    pm.write(midi_bytes)
    midi_bytes.seek(0)
    return midi_bytes

def midi_to_audio(midi_bytes):
    import tempfile
    import subprocess
    import os

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as midi_file:
        midi_file.write(midi_bytes.read())
        midi_file.flush()
        midi_path = midi_file.name

    wav_path = midi_path.replace(".mid", ".wav")
    soundfont = "/usr/share/sounds/sf2/FluidR3_GM.sf2"
    if not os.path.exists(soundfont):
        soundfont = "default.sf2"
    cmd = [
        "fluidsynth", "-ni", soundfont, midi_path, "-F", wav_path, "-r", "44100"
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        audio = AudioSegment.from_file(wav_path)
        # Optional: add vinyl noise
        noise = WhiteNoise().to_audio_segment(duration=len(audio), volume=-30)
        audio = audio.overlay(noise)
        return audio
    finally:
        os.remove(midi_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)