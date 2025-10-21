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

1. **Windows** – double-click `Start Lofi Symphony.bat` (or run it from PowerShell).
2. **macOS** – double-click `Start Lofi Symphony.command` (run `chmod +x` once if macOS marks it as downloaded from the web).
3. **Linux / power users** – run `python launcher.py` from the project folder.

The launcher creates an isolated `.lofi_venv` virtual environment, installs the entire core dependency set (no compilers or
manual steps required) and then opens the Streamlit interface in your browser. Subsequent launches reuse the cached
environment so you simply double-click and jam. Each run double-checks the essential Python packages, provisions a working
`ffmpeg` binary (via `imageio-ffmpeg` when necessary) and fetches the `en_core_web_sm` spaCy model automatically when you
enable MusicGen support, so the install won't get stuck on missing components.

> Want Audiocraft/MusicGen integration as well? Run `python launcher.py --with-musicgen` once the base environment is ready.
> Those optional packages pull in PyTorch and spaCy, so the download is larger and Windows users still need the Microsoft C++
> Build Tools before enabling the flag.

Prefer setting everything up manually? Skip ahead to [run locally from a terminal](#-run-locally-from-a-terminal) for a slim, developer-friendly workflow.

### What to expect on first launch

1. The launcher checks that a compatible Python (3.9–3.11) is available. If not, install one from [python.org](https://www.python.org/downloads/) first.
2. A `.lofi_venv` folder appears beside `launcher.py`; this is your self-contained environment.
3. Dependencies are downloaded (this can take a few minutes the first time; add `--with-musicgen` later if you want the optional Audiocraft packages).
4. Streamlit starts automatically and opens a browser tab at [http://localhost:8501](http://localhost:8501). If a tab does not open, copy the displayed URL into your browser manually.
5. Use the **Generator**, **Performance** and **Timeline** tabs to create ideas. Stop the app at any time with `Ctrl+C` in the launcher window.

On subsequent launches the launcher reuses the cached environment, so you will jump straight to step 4.

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
time. Enable these extras by running `python launcher.py --with-musicgen` after the base environment is ready. The launcher fetches
PyTorch CPU wheels from the official index and wires them into the managed virtual environment. If the optional packages fail to
install, rerun `launcher.py --with-musicgen --reset` after installing the Microsoft C++ Build Tools on Windows or the relevant
compiler toolchain on macOS/Linux – the UI will gracefully fall back to MIDI-only features until everything is available.

## 🧪 Running the app
Launch the web UI with either the console entry point installed by the package or the classic Streamlit command:

```bash
# Via the packaged console script
lofi-symphony

# or manually
streamlit run lofi_symphony/app.py
```

If you prefer working directly from the source tree, run the package as a module
so Python sets up the package context correctly:

```bash
python -m lofi_symphony

# or invoke the Streamlit script in place
python src/lofi_symphony/app.py
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

## 🧑‍💻 Run locally from a terminal
Prefer to stay in your own shell instead of the bundled launcher? Create a virtual environment, install the core requirements, then call the helper that mirrors the quick-start hardening:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# POSIX
./scripts/run_local.sh
# PowerShell
./scripts/run_local.ps1
```

No account or email is required. Telemetry is disabled via config/env.

The shell and PowerShell helpers keep the Streamlit server bound to localhost, disable telemetry, and honour the prompt safeguards defined in `.streamlit/config.toml`. Pass arguments after `--` to forward them straight to Streamlit (for example `./scripts/run_local.sh -- --server.port 8502`). If you prefer not to use the helpers, run `python -m streamlit run src/lofi_symphony/app.py` from the project root.

## 🔒 Deployment hardening checklist
- Review `.streamlit/config.toml` before hosting the app. The checked-in template hides Streamlit's email prompt and disables telemetry; adjust those values deliberately when exposing the UI beyond localhost.
- Before each release, run `pip-audit -r requirements.txt --progress-spinner off` (or integrate it into CI) to confirm the dependency set remains free of known CVEs.

## 🛠️ Development
- `src/lofi_symphony/generator.py` – MIDI creation and audio rendering utilities.
- `src/lofi_symphony/app.py` – Streamlit UI.
- `app.py` – lightweight launcher for local development.

Pull requests are welcome! Share screenshots, new progressions, or improvements to the visual design.

## ❓ Troubleshooting
- **Audio preview unavailable** – confirm `fluidsynth` and a soundfont are installed, then restart the app.
- **Missing dependencies** – rerun the launcher so it can reinstall the managed virtual environment (`launcher.py --reset` performs a full rebuild).
- **MusicGen extras fail to install** – verify the Microsoft C++ Build Tools (Windows) or your platform's compiler toolchain are installed, then rerun `launcher.py --with-musicgen --reset`. Without those tools, stick with the default MIDI workflow – it ships fully packaged and won't prompt for compilers.
- **`pip install python` errors** – grab Python directly from [python.org](https://www.python.org/downloads/) or the Microsoft Store instead of installing a `python` package via pip; the launcher will use whichever interpreter you run it with.

Enjoy crafting mellow vibes with **LofiSymphony**. 🎧
