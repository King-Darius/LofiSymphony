"""Audiocraft helpers to bridge MusicGen with the LofiSymphony workflow."""

from __future__ import annotations

import functools
import importlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, TYPE_CHECKING

from .generator import generate_lofi_midi, midi_to_audio

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import torch


class AudiocraftUnavailable(RuntimeError):
    """Raised when Audiocraft cannot be imported or initialised."""


class _MusicGen(Protocol):
    def set_generation_params(
        self,
        *,
        duration: float,
        top_k: int,
        top_p: float,
        temperature: float,
        cfg_coef: float,
    ) -> None:
        ...

    def generate_audio(self, descriptions: list[str]) -> Iterable["torch.Tensor"]:  # pragma: no cover - heavy
        ...


@dataclass
class AudiocraftSettings:
    """Configuration for a MusicGen generation request."""

    model: str = "facebook/musicgen-small"
    prompt: str = "A warm lofi beat with dusty textures"
    duration: float = 12.0
    top_k: int = 250
    top_p: float = 0.0
    temperature: float = 1.0
    cfg_coef: float = 3.5


@functools.lru_cache(maxsize=1)
def _load_musicgen(model_name: str) -> _MusicGen:
    try:
        models = importlib.import_module("audiocraft.models.musicgen")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise AudiocraftUnavailable("Audiocraft is not installed. Install `audiocraft` to enable this feature.") from exc

    model = models.MusicGen.get_pretrained(model_name)
    model.set_generation_params(
        duration=12.0,
        top_k=250,
        top_p=0.0,
        temperature=1.0,
        cfg_coef=3.5,
    )
    return model


def render_musicgen(settings: AudiocraftSettings) -> Path:
    """Generate an audio preview from a textual prompt using MusicGen."""

    model = _load_musicgen(settings.model)
    model.set_generation_params(
        duration=settings.duration,
        top_k=settings.top_k,
        top_p=settings.top_p,
        temperature=settings.temperature,
        cfg_coef=settings.cfg_coef,
    )
    tensor_audio = next(iter(model.generate_audio([settings.prompt])))

    try:
        torchaudio = importlib.import_module("torchaudio")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise AudiocraftUnavailable(
            "Torchaudio is required to export MusicGen results. Install `torchaudio`."
        ) from exc

    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    out_path = Path(temp_path)
    torchaudio.save(out_path, tensor_audio.cpu(), sample_rate=model.sample_rate)
    return out_path


def generate_musicgen_backing(
    *,
    prompt: str,
    key: str,
    scale: str,
    tempo: int,
    instruments: Iterable[str],
) -> Path:
    """Produce a hybrid track that blends MIDI scaffolding with MusicGen."""

    midi_bytes = generate_lofi_midi(key=key, scale=scale, tempo=tempo, instruments=instruments)
    midi_audio = midi_to_audio(midi_bytes)
    fd, temp_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    midi_path = Path(temp_path)
    midi_audio.export(midi_path, format="wav")

    settings = AudiocraftSettings(prompt=prompt)
    musicgen_path = render_musicgen(settings)

    try:
        audiosegment = importlib.import_module("pydub").AudioSegment
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise AudiocraftUnavailable("pydub is required to fuse MusicGen and MIDI renders.") from exc

    midi_seg = audiosegment.from_wav(midi_path)
    mg_seg = audiosegment.from_wav(musicgen_path)
    blended = midi_seg.overlay(mg_seg - 6)
    output_path = Path.cwd() / "lofi_musicgen_blend.wav"
    blended.export(output_path, format="wav")

    midi_path.unlink(missing_ok=True)
    musicgen_path.unlink(missing_ok=True)
    return output_path
