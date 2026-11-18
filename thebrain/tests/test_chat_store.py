from app.core.chat_store import create_conversation, save_message, get_history

def test_create_and_save_message(isolated_database):
    cid = create_conversation(None, "Test chat")
    save_message(cid, "user", "Halo")
    save_message(cid, "assistant", "Hai")
    history = get_history(cid)
    assert len(history) == 2
    assert history[0]["content"] == "Halo"
    assert history[1]["role"] == "assistant"
