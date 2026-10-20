"""Pure gesture gate: one event per hold; release required before another event."""
from dataclasses import dataclass


def normalize_label(label: str) -> str:
    return label.strip().lower().replace('-', ' ').replace('_', ' ')


@dataclass
class GestureGate:
    hold_seconds: float = 1.0
    release_seconds: float = 0.6
    cooldown_seconds: float = 5.0
    candidate: str | None = None
    started: float = 0.0
    absent_since: float | None = None
    latched: bool = False
    last_fired: float = float('-inf')

    def update(self, label: str | None, now: float) -> str | None:
        label = normalize_label(label) if label else None
        if label is not None and label not in ('finger up', 'palm open'):
            self.candidate = None
            self.absent_since = None
            return None
        if label is None:
            if self.absent_since is None:
                self.absent_since = now
            if now - self.absent_since >= self.release_seconds:
                self.latched = False
            self.candidate = None
            return None
        self.absent_since = None
        if self.latched:
            return None
        if label != self.candidate:
            self.candidate, self.started = label, now
            return None
        if now - self.started >= self.hold_seconds and now - self.last_fired >= self.cooldown_seconds:
            self.latched = True
            self.last_fired = now
            return label
        return None
