# LofiSymphony

LofiSymphony is a polished Streamlit experience for generating instant LoFi inspiration. Dial in your key, mood and groove, then export playable MIDI or WAV stems in seconds.

## ✨ Highlights
- Sleek, neon-inspired Streamlit UI with responsive layout.
- Real-time performance desk featuring an on-screen keyboard, USB MIDI capture and take recorder.
- Arrange sections in a tactile timeline editor, quantise grooves and export stems instantly.
- Import MIDI or previously exported JSON timelines directly into the arranger.
- Optional Audiocraft MusicGen integration for text-to-music ideas and MIDI/MusicGen hybrid renders.
- Genre-aware chord palettes, melodies and bass lines powered by `pretty_midi` and `music21`.
- Humanised rhythms, drum grooves and optional vinyl texture overlay.
- One-click MIDI export plus FluidSynth-powered audio rendering (when available).
- Packaged for simple installation – ship it as a tool or embed in your workflow.

## 🚀 Installation
Clone the repository (or install from a package index in the future) and install the project in editable mode. This pulls in every Python dependency automatically.

```bash
pip install -e .
```

> **Tip:** Add the optional audio extras to bundle a Python FluidSynth binding alongside the core dependencies:
>
> ```bash
> pip install -e .[audio]
> ```

### System requirements for audio rendering
To convert MIDI to audio you still need the `fluidsynth` binary and at least one General MIDI soundfont (e.g. `FluidR3_GM.sf2`). On Debian/Ubuntu:

```bash
sudo apt-get install fluidsynth fluid-soundfont-gm
```

Place any custom soundfonts alongside the project or update the environment variable `LOFI_SYMPHONY_SOUNDFONT` to point to it.

### Audiocraft (MusicGen) support
MusicGen generation requires `audiocraft`, `torch` and `torchaudio`. CPU inference works, though a GPU dramatically reduces render time. Install CUDA-enabled PyTorch if you plan to use a GPU. If these packages are missing, the UI will gracefully offer installation hints instead of failing.

## 🧪 Running the app
Launch the web UI with either the console entry point installed by the package or the classic Streamlit command:

```bash
# Via the packaged console script
lofi-symphony

# or manually
streamlit run lofi_symphony/app.py
```

The interface opens in your browser. Use the **Generator** tab for structured MIDI ideas, **Performance** for live capture, and **Timeline** to polish or export the arrangement. Hit **Generate progression** to seed the session, improvise with the keyboard or a USB MIDI controller, then audition and download the resulting stems.

### Importing existing material
Bring in ideas you've sketched elsewhere by using the new import controls at the top of the **Timeline** tab. Upload a JSON file that was exported from LofiSymphony to restore the full arrangement, or drop in a MIDI file to merge its clips with your current session.

### Automated smoke test
Continuous integration or local checks can exercise the Streamlit script without keeping a server running by invoking the bundled smoke test:

```bash
lofi-symphony --smoke-test
```

The command loads the Streamlit script in headless mode using `streamlit.testing`. If it exits with a non-zero status, inspect the printed component tree to diagnose the failure. When running the full server via `streamlit run`, remember to stop the process manually (e.g. with `Ctrl+C`) once you've finished testing, otherwise external tooling such as `timeout` will terminate it with exit code `124`.

## 🛠️ Development
- `src/lofi_symphony/generator.py` – MIDI creation and audio rendering utilities.
- `src/lofi_symphony/app.py` – Streamlit UI.
- `app.py` – lightweight launcher for local development.

Pull requests are welcome! Share screenshots, new progressions, or improvements to the visual design.

## ❓ Troubleshooting
- **Audio preview unavailable** – confirm `fluidsynth` and a soundfont are installed, then restart the app.
- **Missing dependencies** – ensure you ran `pip install -e .` (the editable install wires up the bundled requirements).

Enjoy crafting mellow vibes with **LofiSymphony**. 🎧
