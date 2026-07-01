from kb_engine.importing import mail


def test_connect_is_exposed():
    assert callable(mail.connect)  # import-only contract; no network invoked here
