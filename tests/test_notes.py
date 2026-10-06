import os
import sys
import types
from datetime import datetime, timedelta

import mongomock
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import run

BASE_URL = "https://localhost"


def _note(note_id, user_id, title, body, tags=None, days_old=0):
    timestamp = datetime(2026, 1, 1) - timedelta(days=days_old)
    return {
        "id": note_id,
        "title": title,
        "body": body,
        "user_id": user_id,
        "user_name": "Test User",
        "tags": tags or [],
        "timestamp": timestamp,
        "date_string": timestamp.strftime("%d %b %Y"),
        "deleted": False,
    }


@pytest.fixture()
def db(monkeypatch):
    mock_db = mongomock.MongoClient()["notes_test"]
    monkeypatch.setattr(run, "mongo", types.SimpleNamespace(db=mock_db))
    run.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return mock_db


@pytest.fixture()
def client(db):
    return run.app.test_client()


@pytest.fixture()
def auth_client(client, db):
    db.users.insert_one({
        "id": "user-1",
        "title": "Mr",
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "verified": True,
        "password": run.bc.generate_password_hash("Passw0rd!").decode("utf-8"),
    })
    response = client.post(
        "/login",
        data={"email": "test@example.com", "pass": "Passw0rd!"},
        base_url=BASE_URL,
    )
    assert response.status_code == 302
    return client


def _get_notes(client, **params):
    query = [("format", "json")]
    for key, value in params.items():
        if isinstance(value, list):
            query.extend((key, item) for item in value)
        else:
            query.append((key, value))
    return client.get("/notes", query_string=query, base_url=BASE_URL)


# Tag semantics: multiple tags are intersected

def test_multiple_tags_intersect(auth_client, db):
    db.notes.insert_many([
        _note("n1", "user-1", "Both tags", "a", tags=["home", "todo"]),
        _note("n2", "user-1", "Only home", "b", tags=["home"]),
        _note("n3", "user-1", "Only todo", "c", tags=["todo"]),
        _note("n4", "user-1", "No tags", "d"),
    ])
    response = _get_notes(auth_client, tag=["home", "todo"])
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert [n["id"] for n in data["notes"]] == ["n1"]


def test_single_tag_matches_subset(auth_client, db):
    db.notes.insert_many([
        _note("n1", "user-1", "Both tags", "a", tags=["home", "todo"]),
        _note("n2", "user-1", "Only home", "b", tags=["home"]),
        _note("n3", "user-1", "Only todo", "c", tags=["todo"]),
    ])
    data = _get_notes(auth_client, tag="home").get_json()
    assert data["total"] == 2
    assert {n["id"] for n in data["notes"]} == {"n1", "n2"}


# Keyword search: escaped regex, metacharacters are literal

def test_keyword_metacharacters_are_escaped(auth_client, db):
    db.notes.insert_many([
        _note("n1", "user-1", "C++ tips", "templates"),
        _note("n2", "user-1", "Cxx tips", "unrelated"),
        _note("n3", "user-1", "Plain", "nothing here"),
    ])
    data = _get_notes(auth_client, q="C++").get_json()
    assert data["total"] == 1
    assert [n["id"] for n in data["notes"]] == ["n1"]
    # An unbalanced parenthesis would crash a raw regex; escaped it is literal
    response = _get_notes(auth_client, q="tips (")
    assert response.status_code == 200
    assert response.get_json()["total"] == 0


def test_keyword_matches_title_and_body_case_insensitive(auth_client, db):
    db.notes.insert_many([
        _note("n1", "user-1", "Shopping LIST", "x"),
        _note("n2", "user-1", "Errands", "buy from the list"),
        _note("n3", "user-1", "Work", "roadmap"),
    ])
    data = _get_notes(auth_client, q="list").get_json()
    assert data["total"] == 2
    assert {n["id"] for n in data["notes"]} == {"n1", "n2"}


# Pagination: filter first, clamp out-of-range values

def test_total_reflects_filtered_count_before_pagination(auth_client, db):
    notes = [_note("bulk-%02d" % i, "user-1", "bulk note %d" % i, "x", days_old=i)
             for i in range(7)]
    notes += [_note("other-%d" % i, "user-1", "other %d" % i, "x") for i in range(5)]
    db.notes.insert_many(notes)
    data = _get_notes(auth_client, q="bulk", per_page=3, page=1).get_json()
    assert data["total"] == 7
    assert data["pages"] == 3
    assert len(data["notes"]) == 3
    page3 = _get_notes(auth_client, q="bulk", per_page=3, page=3).get_json()
    assert len(page3["notes"]) == 1
    assert page3["total"] == 7


def test_out_of_range_page_is_clamped(auth_client, db):
    db.notes.insert_many([
        _note("n%02d" % i, "user-1", "note %d" % i, "x", days_old=i)
        for i in range(25)
    ])
    high = _get_notes(auth_client, per_page=10, page=99).get_json()
    assert high["page"] == 3
    assert high["pages"] == 3
    assert len(high["notes"]) == 5
    low = _get_notes(auth_client, per_page=10, page=0).get_json()
    assert low["page"] == 1
    assert len(low["notes"]) == 10
    negative = _get_notes(auth_client, per_page=10, page=-5).get_json()
    assert negative["page"] == 1


def test_invalid_per_page_is_clamped(auth_client, db):
    db.notes.insert_many([
        _note("n%02d" % i, "user-1", "note %d" % i, "x", days_old=i)
        for i in range(60)
    ])
    # Numeric but out of range: clamped into the legal interval
    for raw in ("0", "-3"):
        data = _get_notes(auth_client, per_page=raw).get_json()
        assert data["per_page"] == 1
    # Not a number at all: fall back to the default
    for raw in ("abc", ""):
        data = _get_notes(auth_client, per_page=raw).get_json()
        assert data["per_page"] == run.NOTES_PER_PAGE_DEFAULT
    too_big = _get_notes(auth_client, per_page=1000).get_json()
    assert too_big["per_page"] == run.NOTES_PER_PAGE_MAX
    assert len(too_big["notes"]) == run.NOTES_PER_PAGE_MAX


# Access control

def test_unauthenticated_gets_401_json(client):
    response = _get_notes(client)
    assert response.status_code == 401
    assert response.is_json
    assert "error" in response.get_json()


def test_unauthenticated_page_request_gets_401(client):
    response = client.get("/notes", base_url=BASE_URL)
    assert response.status_code == 401


def test_only_own_notes_are_returned(auth_client, db):
    db.notes.insert_many([
        _note("mine", "user-1", "My note", "x", tags=["home"]),
        _note("theirs", "user-2", "Their note", "x", tags=["home"]),
    ])
    data = _get_notes(auth_client, tag="home").get_json()
    assert data["total"] == 1
    assert [n["id"] for n in data["notes"]] == ["mine"]
