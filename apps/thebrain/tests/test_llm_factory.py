from app.core.llm_factory import for_role, clear_cache

def test_factory_returns_singleton():
    clear_cache()
    client1 = for_role("primary")
    client2 = for_role("primary")
    assert client1 is client2

def test_factory_returns_different_roles():
    clear_cache()
    client1 = for_role("primary")
    client2 = for_role("utility")
    assert client1 is not client2
