import streamlit as st
from generator import generate_lofi_midi, midi_to_audio
import tempfile

# App settings
st.set_page_config(page_title="LofiSymphony 🎵", page_icon="🎵", layout="centered")
st.title("LofiSymphony 🎵")
st.markdown("A powerful, modern, one-click LoFi music generator. Tweak your vibe and click **Generate**!")

# Option controls
KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
SCALES = ['minor', 'major', 'dorian', 'mixolydian']
TEMPOS = list(range(60, 121, 2))
TYPES = ['Chillhop', 'Jazzhop', 'Boom Bap', 'Dreamy', 'Classic LoFi', 'Ambient']
RHYTHMS = ['Straight', 'Swing', 'Shuffle', 'Triplet']
MOODS = ['Chill', 'Happy', 'Sad', 'Nostalgic', 'Energetic', 'Melancholic']
INSTRUMENTS = [
    'Piano', 'Rhodes', 'Synth', 'Guitar', 'Bass', 'Drums', 'FX'
]

with st.form("settings_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_key = st.selectbox("Key", KEYS, index=0)
        selected_scale = st.selectbox("Scale/Mode", SCALES, index=0)
        selected_tempo = st.slider("Tempo (BPM)", min_value=min(TEMPOS), max_value=max(TEMPOS), value=72, step=1)
    with col2:
        selected_type = st.selectbox("Type", TYPES, index=0)
        selected_rhythm = st.selectbox("Rhythm", RHYTHMS, index=0)
    with col3:
        selected_mood = st.selectbox("Feeling", MOODS, index=0)
        selected_instruments = st.multiselect("Instruments", INSTRUMENTS, default=INSTRUMENTS)

    submitted = st.form_submit_button("🎶 Generate LoFi Track")

if submitted:
    st.info("Generating track... This may take a few seconds.")
    midi_bytes = generate_lofi_midi(
        key=selected_key,
        scale=selected_scale,
        tempo=selected_tempo,
        lofi_type=selected_type,
        rhythm=selected_rhythm,
        mood=selected_mood,
        instruments=selected_instruments
    )
    st.download_button(
        label="Download MIDI",
        data=midi_bytes,
        file_name="lofi.mid",
        mime="audio/midi"
    )

    with st.spinner("Rendering audio preview..."):
        try:
            audio = midi_to_audio(midi_bytes)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                audio.export(f.name, format="wav")
            st.audio(f.name, format="audio/wav")
            st.download_button(
                label="Download WAV",
                data=open(f.name, "rb"),
                file_name="lofi.wav",
                mime="audio/wav"
            )
        except Exception as e:
            st.warning("Audio preview failed. Please ensure FluidSynth and a soundfont are installed.")

    st.success("Track generated! Download or play it in your DAW.")

st.caption("Want more features? Open an issue or PR on GitHub!")