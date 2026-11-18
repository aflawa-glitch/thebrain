from app.core.contracts import CapabilitySpec
from app.core.registry import CapabilityRegistry


def test_registry_requires_handler():
    registry = CapabilityRegistry()
    try:
        registry.register(CapabilitySpec("missing", "no handler", {}, {}))
    except ValueError as exc:
        assert "no handler" in str(exc)
    else:
        raise AssertionError("registry accepted a capability without a handler")


def test_registered_capabilities_are_explicit_and_bounded():
    from app.core.orchestrator import registry
    items = {item["name"]: item for item in registry.list()}
    assert {"research", "open_url", "memory_retrieval", "language_model"} <= set(items)
    for item in items.values():
        assert "input_schema" in item and "output_schema" in item
        assert "permissions" in item and "side_effects" in item
        assert item["timeout_seconds"] > 0
        assert item["verification"]
