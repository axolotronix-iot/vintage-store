import pytest
from django.db import connection


def test_home_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Vintage" in response.content


def test_admin_login_page_renders(client):
    response = client.get("/admin/login/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_database_works():
    with connection.cursor() as cursor:
        cursor.execute("select 1")
        assert cursor.fetchone() == (1,)
