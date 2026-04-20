def test_kb_is_loaded_at_import():
    from capacity_chatbot.knowledge import KB
    assert isinstance(KB, list)
    assert len(KB) > 0
    assert all("id" in e for e in KB)
