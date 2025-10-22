"""Timeline management utilities for arranging generated and recorded clips."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

import numpy as np
import pandas as pd
import pretty_midi

from .generator import INSTRUMENT_PROGRAMS


@dataclass
class TimelineEvent:
    """A single note or clip stored on the timeline."""

    start: float
    duration: float
    pitch: int
    velocity: int
    instrument: str

    def to_dict(self) -> dict[str, float | int | str]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, float | int | str]) -> "TimelineEvent":
        return cls(
            start=float(payload["start"]),
            duration=float(payload["duration"]),
            pitch=int(payload["pitch"]),
            velocity=int(payload["velocity"]),
            instrument=str(payload["instrument"]),
        )


class Timeline:
    """Mutable collection of :class:`TimelineEvent` items."""

    def __init__(self, events: Iterable[TimelineEvent] | None = None) -> None:
        self._events: List[TimelineEvent] = list(events or [])

    def __iter__(self):  # pragma: no cover - trivial
        return iter(self._events)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._events)

    @property
    def events(self) -> List[TimelineEvent]:
        return list(self._events)

    def to_dataframe(self) -> pd.DataFrame:
        data = [event.to_dict() for event in self._events]
        if not data:
            return pd.DataFrame(columns=["start", "duration", "pitch", "velocity", "instrument"])
        return pd.DataFrame(data)

    def update_from_dataframe(self, frame: pd.DataFrame) -> None:
        self._events = [TimelineEvent.from_dict(row) for row in frame.to_dict(orient="records")]

    def add_event(self, event: TimelineEvent) -> None:
        self._events.append(event)
        self._events.sort(key=lambda ev: (ev.start, ev.pitch))

    def extend(self, events: Sequence[TimelineEvent]) -> None:
        for event in events:
            self.add_event(event)

    def quantize(self, grid: float = 0.25) -> None:
        for event in self._events:
            event.start = float(np.round(event.start / grid) * grid)
            event.duration = max(grid, float(np.round(event.duration / grid) * grid))

    def to_json(self, path: Path) -> Path:
        payload = [event.to_dict() for event in self._events]
        path.write_text(json.dumps(payload, indent=2))
        return path

    @classmethod
    def from_json(cls, path: Path) -> "Timeline":
        payload = json.loads(path.read_text())
        return cls(TimelineEvent.from_dict(event) for event in payload)

    def to_pretty_midi(self, tempo: int) -> pretty_midi.PrettyMIDI:
        midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
        grouped: dict[str, pretty_midi.Instrument] = {}
        for event in self._events:
            if event.instrument == "Drums":
                program = 0
                is_drum = True
            else:
                is_drum = False
                if event.instrument in INSTRUMENT_PROGRAMS:
                    program = INSTRUMENT_PROGRAMS[event.instrument]
                else:
                    try:
                        program = pretty_midi.instrument_name_to_program(event.instrument)
                    except ValueError:
                        program = 0
            instrument = grouped.get(event.instrument)
            if instrument is None:
                instrument = pretty_midi.Instrument(program=program, is_drum=is_drum, name=event.instrument)
                grouped[event.instrument] = instrument
                midi.instruments.append(instrument)
            elif not instrument.name:
                instrument.name = event.instrument

            note = pretty_midi.Note(
                start=event.start,
                end=event.start + event.duration,
                velocity=event.velocity,
                pitch=event.pitch,
            )
            instrument.notes.append(note)
        return midi


def dataframe_for_display(timeline: Timeline) -> pd.DataFrame:
    frame = timeline.to_dataframe()
    if frame.empty:
        frame = pd.DataFrame(
            [
                {
                    "start": 0.0,
                    "duration": 1.0,
                    "pitch": 60,
                    "velocity": 80,
                    "instrument": "Piano",
                }
            ]
        )
    return frame
