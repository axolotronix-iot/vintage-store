import datetime
import threading

import pytest
from django.utils import timezone

from accounts.models import User
from inventory import services
from inventory.exceptions import InventoryError
from inventory.models import Hold, Piece, PieceChannel, PieceState, PieceTransition


def make_user(username="alice"):
    return User.objects.create_user(username=username, password="secret123")


@pytest.mark.django_db
def test_create_piece():
    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    assert piece.state == PieceState.AVAILABLE
    assert piece.channel == PieceChannel.WAREHOUSE
    tr = PieceTransition.objects.get(piece=piece)
    assert tr.from_state == ""
    assert tr.from_channel == ""
    assert tr.to_state == PieceState.AVAILABLE
    assert tr.to_channel == PieceChannel.WAREHOUSE
    assert tr.user == user
    assert tr.reason == "created"


@pytest.mark.django_db
def test_send_to_event_and_return():
    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    p1 = services.send_to_event(piece, user=user, reason="to event")
    assert p1.state == PieceState.AVAILABLE
    assert p1.channel == PieceChannel.EVENT
    tr1 = PieceTransition.objects.filter(piece=piece).order_by("pk").last()
    assert tr1.from_state == PieceState.AVAILABLE
    assert tr1.from_channel == PieceChannel.WAREHOUSE
    assert tr1.to_state == PieceState.AVAILABLE
    assert tr1.to_channel == PieceChannel.EVENT
    assert tr1.user == user
    assert tr1.reason == "to event"

    p2 = services.return_to_warehouse(p1, user=user, reason="back")
    assert p2.state == PieceState.AVAILABLE
    assert p2.channel == PieceChannel.WAREHOUSE
    tr2 = PieceTransition.objects.filter(piece=piece).order_by("pk").last()
    assert tr2.from_state == PieceState.AVAILABLE
    assert tr2.from_channel == PieceChannel.EVENT
    assert tr2.to_state == PieceState.AVAILABLE
    assert tr2.to_channel == PieceChannel.WAREHOUSE


@pytest.mark.django_db
def test_place_hold_keeps_channel():
    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    services.send_to_event(piece, user=user, reason="to event")
    piece.refresh_from_db()
    expires = timezone.now() + datetime.timedelta(hours=1)
    hold = services.place_hold(piece, user=user, reason="hold", expires_at=expires)
    piece.refresh_from_db()
    assert piece.state == PieceState.RESERVED
    assert piece.channel == PieceChannel.EVENT
    assert hold.previous_state == PieceState.AVAILABLE
    assert hold.previous_channel == PieceChannel.EVENT
    assert hold.expires_at == expires
    assert hold.active is True
    assert hold.extended is False


@pytest.mark.django_db
def test_release_hold_restores_previous():
    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    services.send_to_event(piece, user=user, reason="to event")
    piece.refresh_from_db()
    expires = timezone.now() + datetime.timedelta(hours=1)
    services.place_hold(piece, user=user, reason="hold", expires_at=expires)
    piece.refresh_from_db()
    services.release_hold(piece, user=user, reason="release")
    piece.refresh_from_db()
    hold = Hold.objects.get(piece=piece)
    assert piece.state == PieceState.AVAILABLE
    assert piece.channel == PieceChannel.EVENT
    assert hold.active is False


@pytest.mark.django_db(transaction=True)
def test_concurrent_holds_single_winner():
    from django.db import connections

    for _ in range(50):
        user = make_user(username=f"conc{_}a")
        piece = services.create_piece(user=user, reason="created")

        results = {"ok": 0, "err": 0}
        barrier = threading.Barrier(2)

        def worker(u, piece=piece, results=results, barrier=barrier):
            try:
                barrier.wait()
                services.place_hold(
                    piece,
                    user=u,
                    reason="hold",
                    expires_at=timezone.now() + datetime.timedelta(hours=1),
                )
                results["ok"] += 1
            except InventoryError:
                results["err"] += 1
            finally:
                connections.close_all()

        user2 = make_user(username=f"conc{_}b")
        t1 = threading.Thread(target=worker, args=(user,))
        t2 = threading.Thread(target=worker, args=(user2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["ok"] == 1
        assert results["err"] == 1
        assert Hold.objects.filter(piece=piece, active=True).count() == 1
        assert (
            PieceTransition.objects.filter(piece=piece, to_state=PieceState.RESERVED).count() == 1
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "state,channel",
    [
        (PieceState.RESERVED, PieceChannel.WAREHOUSE),
        (PieceState.SOLD, PieceChannel.WAREHOUSE),
        (PieceState.WITHDRAWN, PieceChannel.WAREHOUSE),
    ],
)
def test_place_hold_rejected(state, channel):
    user = make_user()
    # arrange piece directly
    piece = Piece.objects.create(state=state, channel=channel)
    if state == PieceState.RESERVED:
        Hold.objects.create(
            piece=piece,
            previous_state=PieceState.AVAILABLE,
            previous_channel=channel,
            expires_at=timezone.now() + datetime.timedelta(hours=1),
            active=True,
        )
    transitions_before = PieceTransition.objects.count()
    holds_before = Hold.objects.count()
    state_before = piece.state
    channel_before = piece.channel
    with pytest.raises(InventoryError):
        services.place_hold(
            piece,
            user=user,
            reason="hold",
            expires_at=timezone.now() + datetime.timedelta(hours=1),
        )
    piece.refresh_from_db()
    assert piece.state == state_before
    assert piece.channel == channel_before
    assert PieceTransition.objects.count() == transitions_before
    assert Hold.objects.count() == holds_before


@pytest.mark.django_db
def test_reserved_rejects_moves_and_withdraw():
    user = make_user()
    piece = Piece.objects.create(state=PieceState.RESERVED, channel=PieceChannel.EVENT)
    Hold.objects.create(
        piece=piece,
        previous_state=PieceState.AVAILABLE,
        previous_channel=PieceChannel.EVENT,
        expires_at=timezone.now() + datetime.timedelta(hours=1),
        active=True,
    )
    for fn in (services.send_to_event, services.return_to_warehouse, services.withdraw):
        transitions_before = PieceTransition.objects.count()
        holds_before = Hold.objects.count()
        with pytest.raises(InventoryError):
            fn(piece, user=user, reason="x")
        piece.refresh_from_db()
        assert piece.state == PieceState.RESERVED
        assert piece.channel == PieceChannel.EVENT
        assert PieceTransition.objects.count() == transitions_before
        assert Hold.objects.count() == holds_before


@pytest.mark.django_db
def test_sold_or_withdrawn_rejects_everything():
    user = make_user()
    for state in (PieceState.SOLD, PieceState.WITHDRAWN):
        piece = Piece.objects.create(state=state, channel=PieceChannel.WAREHOUSE)
        funcs = [
            (services.send_to_event, {}),
            (services.return_to_warehouse, {}),
            (services.place_hold, {"expires_at": timezone.now() + datetime.timedelta(hours=1)}),
            (services.release_hold, {}),
            (services.extend_hold, {"expires_at": timezone.now() + datetime.timedelta(hours=2)}),
            (services.withdraw, {}),
        ]
        for fn, kwargs in funcs:
            transitions_before = PieceTransition.objects.count()
            holds_before = Hold.objects.count()
            with pytest.raises(InventoryError):
                fn(piece, user=user, reason="x", **kwargs)
            piece.refresh_from_db()
            assert piece.state == state
            assert PieceTransition.objects.count() == transitions_before
            assert Hold.objects.count() == holds_before


def _prepare_piece(fn):
    if fn is services.create_piece:
        return None
    if fn is services.send_to_event:
        return Piece.objects.create(state=PieceState.AVAILABLE, channel=PieceChannel.WAREHOUSE)
    if fn is services.return_to_warehouse:
        return Piece.objects.create(state=PieceState.AVAILABLE, channel=PieceChannel.EVENT)
    if fn is services.place_hold:
        return Piece.objects.create(state=PieceState.AVAILABLE, channel=PieceChannel.WAREHOUSE)
    if fn is services.release_hold:
        piece = Piece.objects.create(state=PieceState.RESERVED, channel=PieceChannel.EVENT)
        Hold.objects.create(
            piece=piece,
            previous_state=PieceState.AVAILABLE,
            previous_channel=PieceChannel.EVENT,
            expires_at=timezone.now() + datetime.timedelta(hours=1),
            active=True,
        )
        return piece
    if fn is services.extend_hold:
        piece = Piece.objects.create(state=PieceState.RESERVED, channel=PieceChannel.EVENT)
        Hold.objects.create(
            piece=piece,
            previous_state=PieceState.AVAILABLE,
            previous_channel=PieceChannel.EVENT,
            expires_at=timezone.now() + datetime.timedelta(hours=1),
            active=True,
            extended=False,
        )
        return piece
    if fn is services.withdraw:
        return Piece.objects.create(state=PieceState.AVAILABLE, channel=PieceChannel.WAREHOUSE)
    return None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fn,kwargs",
    [
        (services.create_piece, {}),
        (services.send_to_event, {}),
        (services.return_to_warehouse, {}),
        (services.place_hold, {"expires_at": timezone.now() + datetime.timedelta(hours=1)}),
        (services.release_hold, {}),
        (services.extend_hold, {"expires_at": timezone.now() + datetime.timedelta(hours=2)}),
        (services.withdraw, {}),
    ],
)
def test_reason_is_required(fn, kwargs):
    user = make_user()
    piece = _prepare_piece(fn)
    for bad in ("", "   ", None):
        transitions_before = PieceTransition.objects.count()
        holds_before = Hold.objects.count()
        with pytest.raises(InventoryError):
            if fn is services.create_piece:
                fn(user=user, reason=bad)
            else:
                fn(piece, user=user, reason=bad, **kwargs)
        assert PieceTransition.objects.count() == transitions_before
        assert Hold.objects.count() == holds_before


@pytest.mark.django_db
@pytest.mark.parametrize(
    "fn,kwargs",
    [
        (services.create_piece, {}),
        (services.send_to_event, {}),
        (services.return_to_warehouse, {}),
        (services.place_hold, {"expires_at": timezone.now() + datetime.timedelta(hours=1)}),
        (services.release_hold, {}),
        (services.extend_hold, {"expires_at": timezone.now() + datetime.timedelta(hours=2)}),
        (services.withdraw, {}),
    ],
)
def test_user_is_required(fn, kwargs):
    piece = _prepare_piece(fn)
    transitions_before = PieceTransition.objects.count()
    holds_before = Hold.objects.count()
    with pytest.raises(InventoryError):
        if fn is services.create_piece:
            fn(user=None, reason="x")
        else:
            fn(piece, user=None, reason="x", **kwargs)
    assert PieceTransition.objects.count() == transitions_before
    assert Hold.objects.count() == holds_before


@pytest.mark.django_db
def test_extend_hold_only_once():
    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    expires = timezone.now() + datetime.timedelta(hours=1)
    services.place_hold(piece, user=user, reason="hold", expires_at=expires)
    piece.refresh_from_db()
    new_expires = expires + datetime.timedelta(hours=1)
    hold = services.extend_hold(piece, user=user, reason="extend", expires_at=new_expires)
    assert hold.extended is True
    assert hold.expires_at == new_expires
    tr = PieceTransition.objects.filter(piece=piece).order_by("pk").last()
    assert tr.from_state == tr.to_state == PieceState.RESERVED
    assert tr.from_channel == tr.to_channel == piece.channel

    # second extension rejected
    transitions_before = PieceTransition.objects.count()
    holds_before = Hold.objects.count()
    with pytest.raises(InventoryError):
        services.extend_hold(
            piece,
            user=user,
            reason="extend2",
            expires_at=new_expires + datetime.timedelta(hours=1),
        )
    assert PieceTransition.objects.count() == transitions_before
    assert Hold.objects.count() == holds_before


@pytest.mark.django_db
def test_expire_holds_command(capsys):
    from django.core.management import call_command

    piece = Piece.objects.create(state=PieceState.RESERVED, channel=PieceChannel.EVENT)
    Hold.objects.create(
        piece=piece,
        previous_state=PieceState.AVAILABLE,
        previous_channel=PieceChannel.EVENT,
        expires_at=timezone.now() - datetime.timedelta(hours=1),
        active=True,
    )
    call_command("expire_holds")
    out = capsys.readouterr().out
    assert "Apartados expirados: 1" in out
    piece.refresh_from_db()
    hold = Hold.objects.get(piece=piece)
    assert piece.state == PieceState.AVAILABLE
    assert piece.channel == PieceChannel.EVENT
    assert hold.active is False
    tr = PieceTransition.objects.get(piece=piece)
    assert tr.user is None
    assert tr.reason == "Hold expired"

    call_command("expire_holds")
    out2 = capsys.readouterr().out
    assert "Apartados expirados: 0" in out2


@pytest.mark.django_db
def test_expire_holds_ignores_live_holds(capsys):
    from django.core.management import call_command

    piece = Piece.objects.create(state=PieceState.RESERVED, channel=PieceChannel.EVENT)
    Hold.objects.create(
        piece=piece,
        previous_state=PieceState.AVAILABLE,
        previous_channel=PieceChannel.EVENT,
        expires_at=timezone.now() + datetime.timedelta(hours=1),
        active=True,
    )
    transitions_before = PieceTransition.objects.count()
    call_command("expire_holds")
    out = capsys.readouterr().out
    assert "Apartados expirados: 0" in out
    piece.refresh_from_db()
    assert piece.state == PieceState.RESERVED
    assert PieceTransition.objects.count() == transitions_before


@pytest.mark.django_db
def test_lazy_expiry_on_place_hold():
    user = make_user()
    piece = Piece.objects.create(state=PieceState.RESERVED, channel=PieceChannel.EVENT)
    old_hold = Hold.objects.create(
        piece=piece,
        previous_state=PieceState.AVAILABLE,
        previous_channel=PieceChannel.EVENT,
        expires_at=timezone.now() - datetime.timedelta(hours=1),
        active=True,
    )
    transitions_before = PieceTransition.objects.count()
    expires = timezone.now() + datetime.timedelta(hours=1)
    new_hold = services.place_hold(piece, user=user, reason="new hold", expires_at=expires)
    piece.refresh_from_db()
    old_hold.refresh_from_db()
    assert piece.state == PieceState.RESERVED
    assert piece.channel == PieceChannel.EVENT
    assert old_hold.active is False
    assert new_hold.active is True
    assert PieceTransition.objects.count() == transitions_before + 2


@pytest.mark.django_db
def test_expired_hold_cannot_be_released_or_extended():
    user = make_user()
    piece = Piece.objects.create(state=PieceState.RESERVED, channel=PieceChannel.EVENT)
    Hold.objects.create(
        piece=piece,
        previous_state=PieceState.AVAILABLE,
        previous_channel=PieceChannel.EVENT,
        expires_at=timezone.now() - datetime.timedelta(hours=1),
        active=True,
    )
    transitions_before = PieceTransition.objects.count()
    holds_before = Hold.objects.count()
    with pytest.raises(InventoryError):
        services.release_hold(piece, user=user, reason="release")
    with pytest.raises(InventoryError):
        services.extend_hold(
            piece,
            user=user,
            reason="extend",
            expires_at=timezone.now() + datetime.timedelta(hours=1),
        )
    piece.refresh_from_db()
    assert piece.state == PieceState.RESERVED
    assert PieceTransition.objects.count() == transitions_before
    assert Hold.objects.count() == holds_before


@pytest.mark.django_db
def test_audit_failure_rolls_back(monkeypatch):
    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    # make piece available
    assert piece.state == PieceState.AVAILABLE

    def boom(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("inventory.services.PieceTransition.objects.create", boom)

    transitions_before = PieceTransition.objects.count()
    holds_before = Hold.objects.count()
    with pytest.raises(RuntimeError):
        services.place_hold(
            piece,
            user=user,
            reason="hold",
            expires_at=timezone.now() + datetime.timedelta(hours=1),
        )
    piece.refresh_from_db()
    assert piece.state == PieceState.AVAILABLE
    assert Hold.objects.count() == holds_before
    assert PieceTransition.objects.count() == transitions_before


@pytest.mark.django_db
def test_audit_blocks_deletion():
    from django.db.models import ProtectedError

    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    # piece has audit record; user has audit record
    with pytest.raises(ProtectedError):
        piece.delete()
    with pytest.raises(ProtectedError):
        user.delete()
    assert PieceTransition.objects.count() == 1


@pytest.mark.django_db
def test_expires_at_validation():
    user = make_user()
    piece = services.create_piece(user=user, reason="created")
    # naive datetime rejected
    naive = datetime.datetime.now()
    with pytest.raises(InventoryError):
        services.place_hold(piece, user=user, reason="h", expires_at=naive)
    # past rejected
    with pytest.raises(InventoryError):
        services.place_hold(
            piece, user=user, reason="h", expires_at=timezone.now() - datetime.timedelta(hours=1)
        )
    # extend must be later
    expires = timezone.now() + datetime.timedelta(hours=1)
    services.place_hold(piece, user=user, reason="h", expires_at=expires)
    piece.refresh_from_db()
    with pytest.raises(InventoryError):
        services.extend_hold(piece, user=user, reason="e", expires_at=expires)
    # not timezone-aware for extend
    with pytest.raises(InventoryError):
        services.extend_hold(piece, user=user, reason="e", expires_at=datetime.datetime.now())
