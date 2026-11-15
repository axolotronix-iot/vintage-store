import datetime

from django.db import transaction
from django.utils import timezone

from .exceptions import (
    InvalidExpiry,
    InvalidReason,
    InvalidTransition,
    InvalidUser,
)
from .models import Hold, Piece, PieceChannel, PieceState, PieceTransition


def _get_user_model():
    from django.contrib.auth import get_user_model

    return get_user_model()


def _validate_user(user):
    User = _get_user_model()
    if not isinstance(user, User) or getattr(user, "pk", None) is None:
        raise InvalidUser("A saved user is required.")


def _validate_reason(reason):
    if not isinstance(reason, str) or not reason.strip():
        raise InvalidReason("A non-empty reason is required.")


def _validate_expires_at(expires_at, *, future=False, later_than=None):
    if not isinstance(expires_at, datetime.datetime) or timezone.is_naive(expires_at):
        raise InvalidExpiry("expires_at must be a timezone-aware datetime.")
    if future and expires_at <= timezone.now():
        raise InvalidExpiry("expires_at must be in the future.")
    if later_than is not None and not (expires_at > later_than):
        raise InvalidExpiry("expires_at must be later than the current value.")


def _transition(piece, *, user, reason, to_state, to_channel, expected_state, expected_channel):
    updated = Piece.objects.filter(
        pk=piece.pk, state=expected_state, channel=expected_channel
    ).update(state=to_state, channel=to_channel)
    if updated != 1:
        raise InvalidTransition("The piece is not in the expected state/channel.")
    PieceTransition.objects.create(
        piece=piece,
        user=user,
        from_state=expected_state,
        from_channel=expected_channel,
        to_state=to_state,
        to_channel=to_channel,
        reason=reason,
    )


def _maybe_expire(piece):
    if piece.state != PieceState.RESERVED:
        return
    hold = Hold.objects.filter(piece=piece, active=True).first()
    if hold is None:
        return
    if hold.expires_at > timezone.now():
        return
    hold.active = False
    hold.save(update_fields=["active"])
    _transition(
        piece,
        user=None,
        reason="Hold expired",
        to_state=hold.previous_state,
        to_channel=hold.previous_channel,
        expected_state=PieceState.RESERVED,
        expected_channel=piece.channel,
    )
    piece.refresh_from_db()


def create_piece(*, user, reason):
    _validate_user(user)
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.create(state=PieceState.AVAILABLE, channel=PieceChannel.WAREHOUSE)
        PieceTransition.objects.create(
            piece=piece,
            user=user,
            from_state="",
            from_channel="",
            to_state=PieceState.AVAILABLE,
            to_channel=PieceChannel.WAREHOUSE,
            reason=reason,
        )
    return piece


def send_to_event(piece, *, user, reason):
    _validate_user(user)
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _maybe_expire(piece)
        if piece.state != PieceState.AVAILABLE or piece.channel != PieceChannel.WAREHOUSE:
            raise InvalidTransition("Piece cannot be sent to event.")
        _transition(
            piece,
            user=user,
            reason=reason,
            to_state=PieceState.AVAILABLE,
            to_channel=PieceChannel.EVENT,
            expected_state=PieceState.AVAILABLE,
            expected_channel=PieceChannel.WAREHOUSE,
        )
    piece.refresh_from_db()
    return piece


def return_to_warehouse(piece, *, user, reason):
    _validate_user(user)
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _maybe_expire(piece)
        if piece.state != PieceState.AVAILABLE or piece.channel != PieceChannel.EVENT:
            raise InvalidTransition("Piece cannot be returned to warehouse.")
        _transition(
            piece,
            user=user,
            reason=reason,
            to_state=PieceState.AVAILABLE,
            to_channel=PieceChannel.WAREHOUSE,
            expected_state=PieceState.AVAILABLE,
            expected_channel=PieceChannel.EVENT,
        )
    piece.refresh_from_db()
    return piece


def place_hold(piece, *, user, reason, expires_at):
    _validate_user(user)
    _validate_reason(reason)
    _validate_expires_at(expires_at, future=True)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _maybe_expire(piece)
        if not (
            piece.state == PieceState.AVAILABLE
            and piece.channel in (PieceChannel.WAREHOUSE, PieceChannel.EVENT)
        ):
            raise InvalidTransition("Piece cannot be held.")
        Hold.objects.create(
            piece=piece,
            previous_state=piece.state,
            previous_channel=piece.channel,
            expires_at=expires_at,
            extended=False,
            active=True,
        )
        _transition(
            piece,
            user=user,
            reason=reason,
            to_state=PieceState.RESERVED,
            to_channel=piece.channel,
            expected_state=PieceState.AVAILABLE,
            expected_channel=piece.channel,
        )
    hold = Hold.objects.get(piece=piece, active=True)
    piece.refresh_from_db()
    return hold


def release_hold(piece, *, user, reason):
    _validate_user(user)
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        if piece.state != PieceState.RESERVED:
            raise InvalidTransition("Piece is not reserved.")
        hold = Hold.objects.filter(piece=piece, active=True).first()
        if hold is None or hold.expires_at <= timezone.now():
            raise InvalidTransition("No active hold or hold expired.")
        hold.active = False
        hold.save(update_fields=["active"])
        _transition(
            piece,
            user=user,
            reason=reason,
            to_state=hold.previous_state,
            to_channel=hold.previous_channel,
            expected_state=PieceState.RESERVED,
            expected_channel=piece.channel,
        )
    piece.refresh_from_db()
    return piece


def extend_hold(piece, *, user, reason, expires_at):
    _validate_user(user)
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        if piece.state != PieceState.RESERVED:
            raise InvalidTransition("Piece is not reserved.")
        hold = Hold.objects.filter(piece=piece, active=True).first()
        if hold is None or hold.expires_at <= timezone.now():
            raise InvalidTransition("No active hold or hold expired.")
        if hold.extended:
            raise InvalidTransition("Hold already extended.")
        _validate_expires_at(expires_at, later_than=hold.expires_at)
        hold.expires_at = expires_at
        hold.extended = True
        hold.save(update_fields=["expires_at", "extended"])
        _transition(
            piece,
            user=user,
            reason=reason,
            to_state=PieceState.RESERVED,
            to_channel=piece.channel,
            expected_state=PieceState.RESERVED,
            expected_channel=piece.channel,
        )
    hold.refresh_from_db()
    return hold


def withdraw(piece, *, user, reason):
    _validate_user(user)
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _maybe_expire(piece)
        if piece.state != PieceState.AVAILABLE:
            raise InvalidTransition("Piece cannot be withdrawn.")
        _transition(
            piece,
            user=user,
            reason=reason,
            to_state=PieceState.WITHDRAWN,
            to_channel=piece.channel,
            expected_state=PieceState.AVAILABLE,
            expected_channel=piece.channel,
        )
    piece.refresh_from_db()
    return piece


def expire_holds():
    count = 0
    with transaction.atomic():
        pieces = list(Piece.objects.select_for_update().filter(state=PieceState.RESERVED))
        for piece in pieces:
            hold = Hold.objects.filter(piece=piece, active=True).first()
            if hold is None:
                continue
            if hold.expires_at > timezone.now():
                continue
            hold.active = False
            hold.save(update_fields=["active"])
            _transition(
                piece,
                user=None,
                reason="Hold expired",
                to_state=hold.previous_state,
                to_channel=hold.previous_channel,
                expected_state=PieceState.RESERVED,
                expected_channel=piece.channel,
            )
            count += 1
    return count
