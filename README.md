# LofiSymphony

LofiSymphony is a polished Streamlit experience for generating instant LoFi inspiration. Dial in your key, mood and groove, then export playable MIDI or WAV stems in seconds.

## ✨ Highlights
- Sleek, neon-inspired Streamlit UI with responsive layout.
- Real-time performance desk featuring an on-screen keyboard, USB MIDI capture and take recorder.
- Arrange sections in a tactile timeline editor, quantise grooves and export stems instantly.
- Import MIDI or previously exported JSON timelines directly into the arranger.
- Built-in Audiocraft MusicGen integration for text-to-music ideas and MIDI/MusicGen hybrid renders.
- Genre-aware chord palettes, melodies and bass lines powered by `pretty_midi` and `music21`.
- Humanised rhythms, drum grooves and a sidebar toggle for the vinyl texture overlay.
- One-click MIDI export plus FluidSynth-powered audio rendering (when available).
- Packaged for simple installation -- ship it as a tool or embed in your workflow.

## UI parity roadmap
- [x] Mirror the reference styling across Generator, Performance and Timeline.
- [x] Surface an Arranger preview tab with static mixer cards and section summaries.
- [x] Enable interactive track mute/solo, pan and per-section automation tied to playback.
- [x] Implement drag-and-drop clip lanes with coloured sections and section-aware timing.
- [x] Embed effects rack controls and export presets matching the mockups.


## 🚀 Quick start (no terminal required)
The project ships with ready-to-run helpers so non-technical musicians can get creating without touching a terminal.

1. **Download the app** – grab the latest release zip (or clone this repository) and extract it somewhere easy to find, such as your Desktop.
2. **Open the project folder** – inside you will see platform-specific launchers alongside `launcher.py`.
3. **Double-click the helper for your system:**
   - **Windows** – open `Start Lofi Symphony.bat`. If Windows SmartScreen appears, click **More info** → **Run anyway**. The script automatically tries the `py` launcher and falls back to `python`, then tells you exactly where to download Python 3.9+ if it is missing.
   - **macOS** – Control-click `Start Lofi Symphony.command`, choose **Open**, then confirm. macOS may ask the first time because the file was downloaded from the internet. The helper now checks your Python version and guides you back to [python.org](https://www.python.org/downloads/) if an upgrade is required.
   - **Linux** – double-click the `.command` script if your file manager supports it, or right-click → **Run**. You can also open a terminal in the folder and run `python launcher.py` manually.

The launcher creates an isolated `.lofi_venv` virtual environment, installs the entire dependency set (no compilers or manual steps required) and then opens the Streamlit interface in your default browser. Subsequent launches reuse the cached environment so you simply double-click and jam. Each run double-checks the essential Python packages, provisions a working `ffmpeg` binary (via `imageio-ffmpeg` when possible) and fetches the `en_core_web_sm` spaCy model required by the bundled MusicGen support so the install won't get stuck on missing components. If a download temporarily fails the helper retries automatically, and if it still can't provision extras such as `ffmpeg` it simply skips them and continues to launch the UI with a friendly reminder in the console.

> MusicGen support ships enabled by default. The first launch downloads PyTorch, torchaudio and Audiocraft, so expect a larger initial setup. If the install fails, rerun `python launcher.py --upgrade` (add `--reset` to recreate the environment) after installing the Microsoft C++ Build Tools on Windows or the equivalent compiler toolchain on macOS/Linux.

Prefer setting everything up manually? Skip ahead to [run locally from a terminal](#-run-locally-from-a-terminal) for a slim, developer-friendly workflow.

### Step-by-step walkthrough (first launch)

1. When the helper opens, leave the window visible. It checks that Python 3.9–3.12 is installed and tells you what to download if it is not.
2. A `.lofi_venv` folder appears beside `launcher.py`; this is your self-contained environment.
3. The launcher downloads dependencies. This can take several minutes the first time because PyTorch, torchaudio and Audiocraft are part of the default bundle—keep the window open until the prompts stop.
4. Streamlit starts automatically and opens a browser tab at [http://localhost:8501](http://localhost:8501). If a tab does not appear, copy the displayed URL into your browser manually.
5. Make music! Explore the **Generator**, **Performance** and **Timeline** tabs. Close the browser tab and press `Ctrl+C` (or `⌘`+`.` on macOS) in the launcher window when you are done.

On subsequent launches the helper reuses the cached environment, so you will jump straight to step 4.

> **Need to pre-download dependencies?** Run `launcher.py --prepare-only` to bootstrap everything without starting the UI, or use `launcher.py --reset` to recreate the environment from scratch.

### System requirements for audio rendering
The launcher provisions every Python dependency automatically, but FluidSynth-based audio still depends on a native `fluidsynth`
executable and a General MIDI soundfont. Official builds now fetch a pre-vetted FluidSynth runtime **and** the
TimGM6mb General MIDI soundfont (GPL-2) during packaging so the app is ready to render audio immediately. Set
`LOFI_SYMPHONY_SKIP_SOUNDFONT=1` before building if your redistribution policy cannot accept GPL assets, and use
`LOFI_SYMPHONY_FLUIDSYNTH` / `LOFI_SYMPHONY_SOUNDFONT` at runtime to override the bundled binary or `.sf2` with a custom path.
Other platforms can install the executable manually using the guidance below—once present, the app will pick everything up on
each launch.

- **Windows** – install the prebuilt binaries from the official FluidSynth releases
  (e.g. [GitHub downloads](https://github.com/FluidSynth/fluidsynth/releases)) or via Chocolatey: `choco install fluidsynth`.
  Ensure the install folder (usually `C:\Program Files\FluidSynth\bin`) is on your `PATH`.
- **macOS** – install with Homebrew: `brew install fluidsynth`. If you use MacPorts, run `sudo port install fluidsynth` instead.
- **Debian/Ubuntu** – install from APT:

  ```bash
  sudo apt-get install fluidsynth fluid-soundfont-gm
  ```

Any General MIDI `.sf2` or `.sf3` soundfont will work. Good starting points include
[FluidR3Mono GM (SF3)](https://github.com/musescore/MuseScore/blob/master/share/sound/FluidR3Mono_GM.sf3) and the
bundled [TimGM6mb](https://member.keymusician.com/Member/FluidR3_GM/index.html#TimGM6mb). Place the file in the project
folder (next to `launcher.py`) or reference an absolute path by setting the `LOFI_SYMPHONY_SOUNDFONT` environment variable.
If the variable is unset, LofiSymphony first checks the bundled TimGM6mb copy, then `~/.lofi_symphony/soundfonts`
(where in-app downloads are stored), followed by any `*.sf2`/`*.sf3` files alongside the app before falling back to
system-wide installs. The **Soundfont library** sidebar expander downloads checksum-verified fonts into that folder and
lets you skip automatic activation if you prefer to manage overrides manually.

### Audiocraft (MusicGen) support
MusicGen generation requires `audiocraft`, `torch` and `torchaudio`. CPU inference works, though a GPU dramatically reduces render
time. The launcher and published wheels install these packages automatically and pin to the vetted PyTorch CPU wheels. On first
launch the app now preloads the `facebook/musicgen-small` checkpoint so prompt-based rendering is ready immediately, and the
**MusicGen setup** sidebar expander surfaces status messages, a model picker (small/medium/large) and a one-click verifier if you
ever need to re-download a checkpoint. The launcher retries these downloads on every run; if pip still cannot compile them (common
on fresh Python 3.12 builds until wheels arrive), the UI shows a friendly reminder while MIDI-first features continue working. Rerun
`launcher.py --upgrade` (add `--reset` to recreate the environment) after installing the Microsoft C++ Build Tools on Windows or the relevant
compiler toolchain on macOS/Linux to retry immediately.

## 🧪 Running the app
Launch the web UI with either the console entry point installed by the package
or by invoking the module directly:

```bash
# Via the packaged console script (forward Streamlit flags after `--`)
lofi-symphony -- --server.headless true

# Equivalent module invocation
python -m lofi_symphony
```

If you prefer working directly from the source tree, you can start Streamlit in
place without installing the wheel:

```bash
# Classic Streamlit invocation from the repository root
streamlit run src/lofi_symphony/app.py

# Or ask Python to proxy to Streamlit automatically
python src/lofi_symphony/app.py -- --server.port 8502
```

The interface opens in your browser. Use the **Generator** tab for structured MIDI ideas, **Performance** for live capture, and **Timeline** to polish or export the arrangement. Hit **Generate progression** to seed the session, improvise with the keyboard or a USB MIDI controller, then audition and download the resulting stems.
> Running on Python 3.12? The launcher still attempts to download torch,
> torchaudio, audiocraft and spaCy for you. If wheels are not yet published, the
> installer logs the failure and the UI explains that MusicGen features are in a
> reduced mode until you retry.

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
- **Audio preview unavailable or only vinyl noise** – confirm `fluidsynth` and a soundfont are installed, then restart the app. Toggle off "Add vinyl texture to preview audio" in the sidebar when you want a clean render.
- **Missing dependencies** – rerun the launcher so it can reinstall the managed virtual environment (`launcher.py --reset` performs a full rebuild).
- **MusicGen dependencies fail to install** – verify the Microsoft C++ Build Tools (Windows) or your platform's compiler toolchain are installed, then rerun `launcher.py --reset` (or `--upgrade`) to retry the install. Without those tools, stick with the default MIDI workflow – it ships fully packaged and won't prompt for compilers.
- **`pip install python` errors** – grab Python directly from [python.org](https://www.python.org/downloads/) or the Microsoft Store instead of installing a `python` package via pip; the launcher will use whichever interpreter you run it with.

Enjoy crafting mellow vibes with **LofiSymphony**. 🎧
