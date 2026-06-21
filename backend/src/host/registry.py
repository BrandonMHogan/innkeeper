"""ModuleRegistry — Protocol type -> provider instance map (D-07).

Consumers never name the module they're calling — they ask the registry for
whoever implements a Protocol. `resolve()` is keyed by Protocol type, never
by module id/name, so a provider can be swapped later without touching any
consumer.
"""


class ModuleRegistry:
    def __init__(self) -> None:
        self._providers: dict[type, object] = {}

    def register(self, protocol_type: type, instance: object) -> None:
        if protocol_type in self._providers:
            raise RuntimeError(
                f"Provider conflict: {protocol_type} already provided by "
                f"{self._providers[protocol_type]!r}, cannot also register {instance!r}"
            )
        self._providers[protocol_type] = instance

    def resolve(self, protocol_type: type) -> object:
        try:
            return self._providers[protocol_type]
        except KeyError:
            raise RuntimeError(f"No provider registered for {protocol_type}") from None
