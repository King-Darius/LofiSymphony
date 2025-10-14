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

## 🚀 Quick start (no terminal required)
Download a release zip (or clone the repo) and launch the bundled helper:

1. **Windows** – double-click `Start Lofi Symphony.bat`.
2. **macOS** – double-click `Start Lofi Symphony.command` (run `chmod +x` once if macOS marks it as downloaded from the web).
3. **Linux / power users** – run `python launcher.py` from the project folder.

The launcher creates an isolated `.lofi_venv` virtual environment, installs the core package *and* the optional audio extras,
then opens the Streamlit interface in your browser. Subsequent launches reuse the cached environment so you simply double-click
and jam.

> **Need to pre-download dependencies?** Run `launcher.py --prepare-only` to bootstrap everything without starting the UI, or use
> `launcher.py --reset` to recreate the environment from scratch.

### System requirements for audio rendering
The launcher provisions every Python dependency automatically, but FluidSynth-based audio still depends on a native `fluidsynth`
executable and a General MIDI soundfont. Install those once per machine using the guidance below, then the app will pick them up
on every launch.

- **Windows** – install the prebuilt binaries from the official FluidSynth releases
  (e.g. [GitHub downloads](https://github.com/FluidSynth/fluidsynth/releases)) or via Chocolatey: `choco install fluidsynth`.
  Ensure the install folder (usually `C:\Program Files\FluidSynth\bin`) is on your `PATH`.
- **macOS** – install with Homebrew: `brew install fluidsynth`. If you use MacPorts, run `sudo port install fluidsynth` instead.
- **Debian/Ubuntu** – install from APT:

  ```bash
  sudo apt-get install fluidsynth fluid-soundfont-gm
  ```

Any General MIDI `.sf2` soundfont will work. Good starting points include the
[FluidR3 GM soundfont](https://member.keymusician.com/Member/FluidR3_GM/index.html) and
[MuseScore General](https://musescore.org/en/handbook/3/soundfonts-and-sfz-files#list). Place the `.sf2` file in the project
folder (next to `launcher.py`) or reference an absolute path by setting the `LOFI_SYMPHONY_SOUNDFONT` environment variable. If
the variable is unset, LofiSymphony automatically searches for `*.sf2` files alongside the app and uses the first match.

### Audiocraft (MusicGen) support
MusicGen generation requires `audiocraft`, `torch` and `torchaudio`. CPU inference works, though a GPU dramatically reduces render
time. The launcher installs these packages automatically. Install CUDA-enabled PyTorch if you plan to use a GPU. If the optional
packages fail to install, rerun `launcher.py --reset` after resolving the issue – the UI will gracefully fall back to MIDI-only
features.

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
- **Missing dependencies** – rerun the launcher so it can reinstall the managed virtual environment (`launcher.py --reset` performs a full rebuild).

Enjoy crafting mellow vibes with **LofiSymphony**. 🎧
