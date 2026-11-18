from __future__ import annotations

from .contracts import CapabilitySpec


class CapabilityRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Capability already registered: {spec.name}")
        if spec.handler is None:
            raise ValueError(f"Capability has no handler: {spec.name}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> CapabilitySpec:
        return self._specs[name]

    def list(self) -> list[dict]:
        return [self._specs[name].public_dict() for name in sorted(self._specs)]

    def names(self) -> set[str]:
        return set(self._specs)


registry = CapabilityRegistry()
