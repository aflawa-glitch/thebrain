from app.core.settings_service import get_all_settings, update_settings, save_glossary, list_glossary, delete_glossary
from app.core.memory import add_memory, retrieve_memories


def test_settings_patch_preserves_invariants():
    original = get_all_settings()
    updated = update_settings({"global": {"persona_name": "JulianTest", "multilingual_input": False}, "modules": {"learning": {"auto_apply_policy_changes": True}}})
    assert updated["global"]["persona_name"] == "JulianTest"
    assert updated["global"]["multilingual_input"] is True
    assert updated["modules"]["learning"]["auto_apply_policy_changes"] is False
    update_settings(original)


def test_glossary_upsert_and_delete():
    save_glossary("JEV_TEST", "A project verification lifecycle", "project")
    save_glossary("JEV_TEST", "Updated definition", "project")
    rows = [x for x in list_glossary() if x["term"] == "JEV_TEST"]
    assert len(rows) == 1 and rows[0]["definition"] == "Updated definition"
    assert delete_glossary("JEV_TEST")
    assert not delete_glossary("JEV_TEST")


def test_memory_retrieval_preserves_provenance():
    item = add_memory("project", "Context packing must preserve evidence provenance in Julian.", "test", {"doc": "roadmap.md"})
    matches = retrieve_memories("preserve evidence provenance", limit=5)
    assert any(row["id"] == item["id"] and row["provenance"].get("doc") == "roadmap.md" for row in matches)


def test_returned_settings_are_deep_copies_and_do_not_mutate_defaults(isolated_database):
    from app.core.settings_service import DEFAULTS, get_all_settings
    before = DEFAULTS['privacy']['save_uploaded_content']
    settings = get_all_settings()
    settings['privacy']['save_uploaded_content'] = not before
    assert DEFAULTS['privacy']['save_uploaded_content'] is before
    assert get_all_settings()['privacy']['save_uploaded_content'] is before
