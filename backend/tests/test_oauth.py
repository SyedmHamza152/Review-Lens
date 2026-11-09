"""OAuth flow unit tests (token exchange mocked — no network)."""
from app.integrations import google_oauth


def test_authorization_url_structure(monkeypatch):
    monkeypatch.setattr(google_oauth.settings, "GOOGLE_CLIENT_ID", "test-id")
    monkeypatch.setattr(google_oauth.settings, "GOOGLE_CLIENT_SECRET", "test-secret")
    url, state = google_oauth.build_authorization_url()
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "access_type=offline" in url
    assert "adwords" in url.replace("%2F", "/") or "adwords" in url
    assert len(state) >= 20
    # state single-use
    assert google_oauth.consume_state(state) is True
    assert google_oauth.consume_state(state) is False


def test_state_validation_rejects_unknown():
    assert google_oauth.consume_state("not-a-real-state") is False


def test_not_configured_raises(monkeypatch):
    monkeypatch.setattr(google_oauth.settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(google_oauth.settings, "GOOGLE_CLIENT_SECRET", "")
    try:
        google_oauth.build_authorization_url()
        assert False, "should have raised"
    except google_oauth.OAuthNotConfigured:
        pass


def test_token_encryption_roundtrip():
    from app.core.security import decrypt_secret, encrypt_secret

    token = "ya29.a0AfB_test-refresh-token"
    encrypted = encrypt_secret(token)
    assert encrypted != token
    assert token not in encrypted
    assert decrypt_secret(encrypted) == token
    assert decrypt_secret("garbage") == ""
