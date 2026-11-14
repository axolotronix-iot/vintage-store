# Spec 0001: accounts app with a custom user

Decision record: `docs/adr/0001-domain-code-layout.md`. Rules: AGENTS.md, section 3 ("Backend layout rules") and section 7.

## Goal

The project uses its own user model before any domain migration exists, because changing the user model later is very expensive in Django.

## Preconditions (done by the architect, not by the agent)

- The work happens on the branch the architect created for this attempt.
- The development database is recreated empty before the attempt. It currently has `admin` and `auth` migrations applied with the default user; Django rejects that history once `admin` depends on `accounts.0001_initial` (`InconsistentMigrationHistory`), and `make check` would fail.

## Scope

- Create the Django app `accounts` in `backend/accounts/`.
- `accounts.User` subclasses `django.contrib.auth.models.AbstractUser` and adds no fields, methods or manager.
- In `backend/config/settings.py`: add `accounts` to `INSTALLED_APPS` and set `AUTH_USER_MODEL = "accounts.User"`.
- Register `accounts.User` in Django admin with Django's own `UserAdmin`.
- Generate `backend/accounts/migrations/0001_initial.py` with `python manage.py makemigrations`. Do not write it by hand.
- Tests go in `backend/tests/accounts/`.

Importing `AbstractUser` and `UserAdmin` from Django is allowed. Importing `django.contrib.auth.models.User` is not.

## Acceptance criteria

Each criterion maps to one test in `backend/tests/accounts/`, except AC5 and AC6.

| # | Given | When | Then | Test |
|---|---|---|---|---|
| AC1 | The project settings | `get_user_model()` is called | It returns `accounts.User`, and `settings.AUTH_USER_MODEL` is `"accounts.User"` | `test_user_model_is_accounts_user` |
| AC2 | No users exist | `create_user` is called with a username and a password | The user is stored, the stored password is not the plain text, and `check_password` accepts the password | `test_create_user_hashes_password` |
| AC3 | A logged-in superuser | They request `/admin/accounts/user/` | The response status is 200 | `test_superuser_can_open_user_admin` |
| AC4 | A logged-in user who is not staff | They request `/admin/accounts/user/` | The response is a redirect to the admin login, not 200 | `test_non_staff_user_cannot_open_user_admin` |
| AC5 | The finished work | `make check` runs | It passes, including "no missing migrations" | command output in the final report |
| AC6 | The finished work | `rg -n "auth\.models import .*\bUser\b" backend` runs | It prints no matches | command output in the final report |

The existing tests in `backend/tests/test_smoke.py` keep passing without changes.

## Out of scope

- Extra user fields, email as login, profile models, a custom manager.
- Login or logout pages, templates, URLs.
- Groups, roles or permission definitions.
- The `inventory` app or any other app.
- Running `migrate` or changing the development database in any way.
- Editing `AGENTS.md`, `opencode.jsonc`, dependencies or lockfiles.
- Commits, unless the architect asks.

## Final report

As AGENTS.md section 7 requires: what changed, which commands ran with their results, and what was not verified.
