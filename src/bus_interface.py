"""Bus abstraction for the HIL test runner (Exercise 9a).

The HIL runner only ever talks to :class:`BusInterface`, so the test
sequences are backend-agnostic. In CI we use the in-memory
:class:`StubBus`; for real hardware you would provide a python-can backed
implementation of the same interface and the identical test sequences run
unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BusInterface(ABC):
    """Abstraction over the signal transport.

    A ``StubBus`` for unit tests; a CAN-backed bus wrapping python-can for
    real HIL. The HIL runner only ever talks to this interface, so tests are
    backend-agnostic.
    """

    @abstractmethod
    def send_signals(self, signals: dict[str, float]) -> None:
        """Inject (write) stimulus signals into the DUT."""
        ...

    @abstractmethod
    def read_signals(self, names: list[str]) -> dict[str, float]:
        """Read back the named response signals from the DUT."""
        ...


class StubBus(BusInterface):
    """In-memory stub standing in for the ECU + CAN transport.

    Models a trivial 'ECU': it echoes a ``BrakeCmd`` derived from injected
    ``EgoSpeed``/``TargetDistance`` so the runner has something real to
    assert on. Replace with a real CAN-backed implementation for hardware
    runs.
    """

    def __init__(self) -> None:
        self._state: dict[str, float] = {}

    def send_signals(self, signals: dict[str, float]) -> None:
        self._state.update(signals)
        self._recompute_outputs()

    def read_signals(self, names: list[str]) -> dict[str, float]:
        # Missing signals default to 0.0 so readback never raises.
        return {n: self._state.get(n, 0.0) for n in names}

    def _recompute_outputs(self) -> None:
        # Toy 'ECU logic' so the harness has a deterministic DUT to test.
        speed = self._state.get("EgoSpeed", 0.0)
        dist = self._state.get("TargetDistance", 999.0)
        if speed > 0 and dist < 10:
            self._state["BrakeCmd"] = 1.0
        elif speed > 0 and dist < 30:
            self._state["BrakeCmd"] = 0.5
        else:
            self._state["BrakeCmd"] = 0.0
