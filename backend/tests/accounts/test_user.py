import pytest
from django.conf import settings
from django.contrib.auth import get_user_model


def test_user_model_is_accounts_user():
    from accounts.models import User

    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert get_user_model() is User


@pytest.mark.django_db
def test_create_user_hashes_password():
    User = get_user_model()
    user = User.objects.create_user(username="alice", password="secret123")
    assert user.pk is not None
    assert user.password != "secret123"
    assert user.check_password("secret123")


@pytest.mark.django_db
def test_superuser_can_open_user_admin(client):
    User = get_user_model()
    superuser = User.objects.create_superuser(username="admin", password="pass")
    client.force_login(superuser)
    response = client.get("/admin/accounts/user/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_non_staff_user_cannot_open_user_admin(client):
    User = get_user_model()
    user = User.objects.create_user(username="bob", password="pass")
    client.force_login(user)
    response = client.get("/admin/accounts/user/")
    assert response.status_code in (301, 302)
    assert "/admin/login/" in response["Location"]
