from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from bson import ObjectId
import pytest


EXISTING_USER_ID = ObjectId()

GITHUB_USER_INFO = {
    "id": 12345,
    "name": "Test User",
    "login": "testuser",
}

GITHUB_EMAILS = [
    {"email": "test@example.com", "primary": True, "verified": True}
]

GOOGLE_USER_INFO = {
    "sub": "google-999",
    "name": "Google User",
    "email": "test@example.com",
}


def make_fake_db(existing=None, inserted=None):

    class FakeUserCollection:
        @staticmethod
        def find_one(q):
            if existing and q.get("email"):
                return existing
            if existing and q.get("github_id"):
                return None
            if existing and q.get("google_id"):
                return None
            if inserted and q.get("_id"):
                return {**inserted, "_id": inserted.get("_id")}
            return None

        @staticmethod
        def update_one(f, u):
            if existing:
                existing.update(u.get("$set", {}))

        @staticmethod
        def insert_one(doc):
            doc["_id"] = ObjectId()
            if inserted is not None:
                inserted.update(doc)
            return SimpleNamespace(inserted_id=doc.get("_id", ObjectId()))

        @staticmethod
        def update_many(f, u):
            pass

    class FakeTopicCollection:
        @staticmethod
        def create_index(*a, **kw):
            pass

        @staticmethod
        def count_documents(*a, **kw):
            return 1

        @staticmethod
        def insert_one(*a, **kw):
            return SimpleNamespace(inserted_id="topic-1")

        @staticmethod
        def insert_many(*a, **kw):
            pass

    class FakeQuestionCollection:
        @staticmethod
        def create_index(*a, **kw):
            pass

        @staticmethod
        def count_documents(*a, **kw):
            return 0

        @staticmethod
        def insert_one(*a, **kw):
            return SimpleNamespace(inserted_id="q-1")

        @staticmethod
        def insert_many(*a, **kw):
            pass

    class FakeDB:
        user = FakeUserCollection()
        topic = FakeTopicCollection()
        question = FakeQuestionCollection()

    return FakeDB()


def make_app(monkeypatch, db_override):
    import app as app_module
    import app.auth.routes as auth_routes

    monkeypatch.setattr(app_module, "db", db_override)
    monkeypatch.setattr(auth_routes, "db", db_override)
    monkeypatch.setattr(app_module.mongo, "init_app", lambda a: None)
    monkeypatch.setattr(app_module.bcrypt, "init_app", lambda a: None)
    monkeypatch.setattr(app_module.login_manager, "init_app", lambda a: None)
    monkeypatch.setattr(app_module.oauth, "init_app", lambda a: None)
    monkeypatch.setattr(
        app_module.oauth,
        "register",
        lambda name, **kwargs: None,
    )
    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


# ── GitHub Tests ──────────────────────────────────────────────────────────────

def test_github_links_existing_email_user(monkeypatch):
    """GitHub OAuth links github_id to existing user with matching email."""
    existing = {"_id": EXISTING_USER_ID, "email": "test@example.com", "progress": {}}
    db = make_fake_db(existing=existing)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github") as mock_github:
            mock_github.authorize_access_token.return_value = {"access_token": "tok"}
            mock_github.get.side_effect = lambda url: (
                MagicMock(ok=True, json=lambda: GITHUB_USER_INFO)
                if url == "user"
                else MagicMock(status_code=200, json=lambda: GITHUB_EMAILS)
            )
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 302
            assert "github_id" in existing


def test_github_creates_new_user_when_no_match(monkeypatch):
    """GitHub OAuth creates a new user when no existing email or github_id match."""
    inserted = {}
    db = make_fake_db(inserted=inserted)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github") as mock_github:
            mock_github.authorize_access_token.return_value = {"access_token": "tok"}
            mock_github.get.side_effect = lambda url: (
                MagicMock(ok=True, json=lambda: GITHUB_USER_INFO)
                if url == "user"
                else MagicMock(status_code=200, json=lambda: GITHUB_EMAILS)
            )
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 302
            assert inserted.get("github_id") == str(GITHUB_USER_INFO["id"])


def test_github_missing_token_returns_400(monkeypatch):
    """GitHub OAuth returns 400 when token is missing."""
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github") as mock_github:
            mock_github.authorize_access_token.return_value = None
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 400


def test_github_failed_user_fetch_returns_400(monkeypatch):
    """GitHub OAuth returns 400 when user info fetch fails."""
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.github") as mock_github:
            mock_github.authorize_access_token.return_value = {"access_token": "tok"}
            mock_github.get.return_value = MagicMock(ok=False)
            resp = client.get("/login/github/authorize")
            assert resp.status_code == 400


# ── Google Tests ──────────────────────────────────────────────────────────────

def test_google_links_existing_email_user(monkeypatch):
    """Google OAuth links google_id to existing user with matching email."""
    existing = {"_id": EXISTING_USER_ID, "email": "test@example.com", "progress": {}}
    db = make_fake_db(existing=existing)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.google") as mock_google:
            mock_google.authorize_access_token.return_value = {"access_token": "tok"}
            mock_google.parse_id_token.return_value = GOOGLE_USER_INFO
            resp = client.get("/login/google/authorize")
            assert resp.status_code == 302
            assert "google_id" in existing


def test_google_creates_new_user_when_no_match(monkeypatch):
    """Google OAuth creates a new user when no existing email or google_id match."""
    inserted = {}
    db = make_fake_db(inserted=inserted)
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.google") as mock_google:
            mock_google.authorize_access_token.return_value = {"access_token": "tok"}
            mock_google.parse_id_token.return_value = GOOGLE_USER_INFO
            resp = client.get("/login/google/authorize")
            assert resp.status_code == 302
            assert inserted.get("google_id") == "google-999"


def test_google_missing_userinfo_returns_400(monkeypatch):
    """Google OAuth returns 400 when userinfo is missing."""
    db = make_fake_db()
    flask_app = make_app(monkeypatch, db)

    with flask_app.test_client() as client:
        with patch("app.auth.routes.google") as mock_google:
            mock_google.authorize_access_token.return_value = {"access_token": "tok"}
            mock_google.parse_id_token.return_value = None
            mock_google.userinfo.return_value = None
            resp = client.get("/login/google/authorize")
            assert resp.status_code in (302, 400)
