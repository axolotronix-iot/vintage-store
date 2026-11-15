import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from inventory import services as services
from inventory.models import AuditRecord, Hold, Piece

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="op", password="secret")


@pytest.mark.django_db
def test_create_piece_is_available_warehouse(user):
    piece = services.create_piece(user, "initial")
    assert piece.state == "available"
    assert piece.channel == "warehouse"
    audits = AuditRecord.objects.filter(piece=piece)
    assert audits.count() == 1
    audit = audits.first()
    assert audit.before_state == ""
    assert audit.before_channel == ""
    assert audit.after_state == "available"
    assert audit.after_channel == "warehouse"
    assert audit.user == user
    assert audit.reason == "initial"


@pytest.mark.django_db
def test_send_and_return(user):
    piece = services.create_piece(user, "initial")
    services.send_to_event(piece, user, "to event")
    piece.refresh_from_db()
    assert piece.state == "available"
    assert piece.channel == "event"
    services.return_to_warehouse(piece, user, "back")
    piece.refresh_from_db()
    assert piece.state == "available"
    assert piece.channel == "warehouse"
    assert AuditRecord.objects.filter(piece=piece).count() == 3


@pytest.mark.django_db
def test_place_hold_stores_before_and_expiry(user):
    piece = services.create_piece(user, "initial")
    expiry = timezone.now() + timezone.timedelta(hours=1)
    services.place_hold(piece, user, "hold", expiry)
    piece.refresh_from_db()
    assert piece.state == "reserved"
    assert piece.channel == "warehouse"
    hold = Hold.objects.get(piece=piece, active=True)
    assert hold.before_state == "available"
    assert hold.before_channel == "warehouse"
    assert hold.expiry == expiry
    assert hold.active is True
    assert hold.extended is False


@pytest.mark.django_db
def test_release_hold_restores_event_channel(user):
    piece = services.create_piece(user, "initial")
    services.send_to_event(piece, user, "to event")
    expiry = timezone.now() + timezone.timedelta(hours=1)
    services.place_hold(piece, user, "hold", expiry)
    services.release_hold(piece, user, "release")
    piece.refresh_from_db()
    assert piece.state == "available"
    assert piece.channel == "event"
    assert not Hold.objects.filter(piece=piece, active=True).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_holds(user):
    piece = Piece.objects.create(state="available", channel="warehouse")
    barrier = threading.Barrier(2)
    results = {"ok": 0, "err": 0}
    expiry = timezone.now() + timezone.timedelta(hours=1)

    def worker():
        connection.close()
        barrier.wait()
        try:
            services.place_hold(piece, user, "hold", expiry)
            results["ok"] += 1
        except ValueError:
            results["err"] += 1
        connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results["ok"] == 1
    assert results["err"] == 1
    assert Hold.objects.filter(piece=piece, active=True).count() == 1
    assert AuditRecord.objects.filter(piece=piece).count() == 1


@pytest.mark.django_db
def test_place_hold_rejected_for_non_available(user):
    piece = services.create_piece(user, "initial")
    services.send_to_event(piece, user, "to event")
    Piece.objects.filter(pk=piece.pk).update(state="sold")
    piece.refresh_from_db()
    expiry = timezone.now() + timezone.timedelta(hours=1)
    with pytest.raises(ValueError):
        services.place_hold(piece, user, "hold", expiry)
    piece.refresh_from_db()
    assert piece.state == "sold"


@pytest.mark.django_db
def test_reserved_rejects_other_operations(user):
    piece = services.create_piece(user, "initial")
    expiry = timezone.now() + timezone.timedelta(hours=1)
    services.place_hold(piece, user, "hold", expiry)
    with pytest.raises(ValueError):
        services.send_to_event(piece, user, "x")
    with pytest.raises(ValueError):
        services.return_to_warehouse(piece, user, "x")
    with pytest.raises(ValueError):
        services.withdraw(piece, user, "x")
    piece.refresh_from_db()
    assert piece.state == "reserved"


@pytest.mark.django_db
def test_sold_or_withdrawn_rejects_all(user):
    expiry = timezone.now() + timezone.timedelta(hours=1)
    for state in ("sold", "withdrawn"):
        piece = services.create_piece(user, "initial")
        Piece.objects.filter(pk=piece.pk).update(state=state)
        piece.refresh_from_db()
        with pytest.raises(ValueError):
            services.send_to_event(piece, user, "x")
        with pytest.raises(ValueError):
            services.return_to_warehouse(piece, user, "x")
        with pytest.raises(ValueError):
            services.place_hold(piece, user, "x", expiry)
        with pytest.raises(ValueError):
            services.withdraw(piece, user, "x")


@pytest.mark.django_db
def test_empty_reason_rejected(user):
    piece = services.create_piece(user, "initial")
    with pytest.raises(ValueError):
        services.withdraw(piece, user, "   ")


@pytest.mark.django_db
def test_extend_hold_twice(user):
    piece = services.create_piece(user, "initial")
    expiry = timezone.now() + timezone.timedelta(hours=1)
    services.place_hold(piece, user, "hold", expiry)
    new_expiry = timezone.now() + timezone.timedelta(hours=2)
    services.extend_hold(piece, user, "extend", new_expiry)
    hold = Hold.objects.get(piece=piece, active=True)
    assert hold.extended is True
    assert hold.expiry == new_expiry
    with pytest.raises(ValueError):
        services.extend_hold(piece, user, "extend2", timezone.now() + timezone.timedelta(hours=3))


@pytest.mark.django_db
def test_expire_holds_command_and_lazy(user):
    piece = services.create_piece(user, "initial")
    expiry = timezone.now() + timezone.timedelta(hours=1)
    services.place_hold(piece, user, "hold", expiry)
    Hold.objects.filter(piece=piece, active=True).update(
        expiry=timezone.now() - timezone.timedelta(minutes=1)
    )
    piece.refresh_from_db()
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("expire_holds", stdout=out)
    piece.refresh_from_db()
    assert piece.state == "available"
    hold = Hold.objects.get(piece=piece)
    assert hold.active is False
    audits = AuditRecord.objects.filter(piece=piece)
    assert audits.count() == 3
    expiry_audit = audits.order_by("id").last()
    assert expiry_audit.user is None

    before = AuditRecord.objects.filter(piece=piece).count()
    call_command("expire_holds", stdout=out)
    assert AuditRecord.objects.filter(piece=piece).count() == before

    piece2 = services.create_piece(user, "initial")
    expiry2 = timezone.now() + timezone.timedelta(hours=1)
    services.place_hold(piece2, user, "hold", expiry2)
    Hold.objects.filter(piece=piece2, active=True).update(
        expiry=timezone.now() - timezone.timedelta(minutes=1)
    )
    piece2.refresh_from_db()
    new_expiry2 = timezone.now() + timezone.timedelta(hours=2)
    services.place_hold(piece2, user, "new hold", new_expiry2)
    piece2.refresh_from_db()
    assert piece2.state == "reserved"
    assert Hold.objects.filter(piece=piece2, active=True).count() == 1
    assert AuditRecord.objects.filter(piece=piece2).count() == 4


@pytest.mark.django_db
def test_audit_failure_rolls_back(user):
    piece = services.create_piece(user, "initial")
    original_create = AuditRecord.objects.create

    def boom(*a, **k):
        raise RuntimeError("audit fail")

    AuditRecord.objects.create = boom
    try:
        expiry = timezone.now() + timezone.timedelta(hours=1)
        with pytest.raises(RuntimeError):
            services.place_hold(piece, user, "hold", expiry)
    finally:
        AuditRecord.objects.create = original_create
    piece.refresh_from_db()
    assert piece.state == "available"
    assert Hold.objects.filter(piece=piece).count() == 0


@pytest.mark.django_db
def test_extend_hold_second_rejected(user):
    piece = services.create_piece(user, "initial")
    expiry = timezone.now() + timezone.timedelta(hours=1)
    services.place_hold(piece, user, "hold", expiry)
    services.extend_hold(piece, user, "extend", timezone.now() + timezone.timedelta(hours=2))
    with pytest.raises(ValueError):
        services.extend_hold(piece, user, "extend2", timezone.now() + timezone.timedelta(hours=3))
