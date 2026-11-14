from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model. Intentionally adds no fields."""

    pass
