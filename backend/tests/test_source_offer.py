from fastapi.testclient import TestClient

from app.main import SOURCE_REPO_URL, app

client = TestClient(app)


def test_source_offer_redirects_to_public_repo():
    response = client.get("/source", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == SOURCE_REPO_URL


def test_api_source_offer_redirects_to_public_repo():
    response = client.get("/api/source", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == SOURCE_REPO_URL
