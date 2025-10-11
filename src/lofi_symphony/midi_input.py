"""Realtime MIDI input capture utilities."""

from __future__ import annotations

import importlib
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional


class MidiBackendUnavailable(RuntimeError):
    """Raised when no MIDI backend can be initialised."""


def _load_mido():
    try:
        return importlib.import_module("mido")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise MidiBackendUnavailable("Install `mido` and `python-rtmidi` to enable MIDI input.") from exc


@dataclass(slots=True)
class MidiMessage:
    note: int
    velocity: int
    timestamp: float


class MidiInputManager:
    """Manage MIDI input ports and streaming."""

    def __init__(self) -> None:
        self._mido = _load_mido()
        self._listener: Optional[threading.Thread] = None
        self._queue: "queue.Queue[MidiMessage]" = queue.Queue()
        self._stop_event = threading.Event()
        self._port: Optional[object] = None

    def list_input_ports(self) -> Iterable[str]:
        return self._mido.get_input_names()

    def start_listening(self, port_name: str) -> None:
        if self._listener and self._listener.is_alive():  # pragma: no cover - guard
            self.stop_listening()

        self._stop_event.clear()
        self._port = self._mido.open_input(port_name)

        def _poll() -> None:
            assert self._port is not None
            while not self._stop_event.is_set():
                for message in self._port.iter_pending():
                    if message.type in {"note_on", "note_off"}:
                        velocity = message.velocity if message.type == "note_on" else 0
                        midi_message = MidiMessage(note=message.note, velocity=velocity, timestamp=time.time())
                        self._queue.put(midi_message)
                time.sleep(0.01)

        self._listener = threading.Thread(target=_poll, daemon=True)
        self._listener.start()

    def stop_listening(self) -> None:
        if self._listener and self._listener.is_alive():
            self._stop_event.set()
            self._listener.join(timeout=2)
        if self._port is not None:
            self._port.close()
        self._listener = None
        self._port = None

    def drain(self, callback: Callable[[MidiMessage], None]) -> None:
        while not self._queue.empty():
            callback(self._queue.get())

    def __del__(self):  # pragma: no cover - cleanup
        self.stop_listening()
