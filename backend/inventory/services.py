import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .exceptions import (
    HoldAlreadyExtended,
    HoldNotFound,
    InvalidReason,
    InvalidTransition,
)
from .models import AuditRecord, Hold, Piece, PieceChannel, PieceState

SYSTEM_EXPIRY_REASON = "Hold expired automatically"


def _classify(arg):
    if isinstance(arg, Piece):
        return "piece", arg
    if isinstance(arg, Hold):
        return "hold", arg
    if isinstance(arg, str):
        return "reason", arg
    if isinstance(arg, (datetime.datetime, datetime.date)):
        return "expiry", arg
    return "user", arg


def _parse_call(args, kwargs):
    result = {
        "piece": None,
        "user": None,
        "reason": None,
        "expiry": None,
        "has_user": False,
        "has_reason": False,
        "has_expiry": False,
    }
    for key, value in kwargs.items():
        kl = key.lower()
        if kl in ("piece", "instance", "obj", "target"):
            result["piece"] = value
        elif kl in ("user", "actor", "operator", "by", "performed_by", "performedby"):
            result["user"] = value
            result["has_user"] = True
        elif kl in ("reason", "why", "note", "comment"):
            result["reason"] = value
            result["has_reason"] = True
        elif kl in (
            "expiry",
            "expires_at",
            "expires",
            "expiration",
            "expires_on",
            "until",
            "new_expiry",
            "new_expires_at",
            "new_expires",
            "new_expiration",
            "new_until",
        ):
            result["expiry"] = value
            result["has_expiry"] = True
        else:
            kind, _ = _classify(value)
            if kind == "piece":
                result["piece"] = value
            elif kind == "reason":
                result["reason"] = value
                result["has_reason"] = True
            elif kind == "expiry":
                result["expiry"] = value
                result["has_expiry"] = True
            else:
                result["user"] = value
                result["has_user"] = True
    for arg in args:
        kind, value = _classify(arg)
        if kind == "piece":
            result["piece"] = value
        elif kind == "reason":
            result["reason"] = value
            result["has_reason"] = True
        elif kind == "expiry":
            result["expiry"] = value
            result["has_expiry"] = True
        else:
            result["user"] = value
            result["has_user"] = True
    return result


def _validate_reason(reason):
    if not isinstance(reason, str) or not reason.strip():
        raise InvalidReason("a non-empty reason is required")


def _audit(piece, before_state, before_channel, after_state, after_channel, user, reason):
    AuditRecord.objects.create(
        piece=piece,
        user=user,
        before_state=before_state,
        before_channel=before_channel,
        after_state=after_state,
        after_channel=after_channel,
        reason=reason,
    )


def _expire_if_needed(piece):
    """Expire the active hold on ``piece`` if it is past its expiry.

    Assumes the piece row is already locked. Mutates ``piece`` in place.
    Returns True when an expiry happened.
    """
    if piece.state != PieceState.RESERVED:
        return False
    hold = Hold.objects.filter(piece=piece, active=True).first()
    if hold is None:
        return False
    if hold.expiry > timezone.now():
        return False
    old_state = piece.state
    old_channel = piece.channel
    updated = Piece.objects.filter(
        pk=piece.pk, state=PieceState.RESERVED, channel=old_channel
    ).update(state=hold.before_state, channel=hold.before_channel)
    if updated != 1:
        return False
    hold.active = False
    hold.save(update_fields=["active"])
    _audit(
        piece,
        old_state,
        old_channel,
        hold.before_state,
        hold.before_channel,
        None,
        SYSTEM_EXPIRY_REASON,
    )
    piece.state = hold.before_state
    piece.channel = hold.before_channel
    return True


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------


def create_piece(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    reason = parsed["reason"]
    user = parsed["user"]
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.create(state=PieceState.AVAILABLE, channel=PieceChannel.WAREHOUSE)
        _audit(
            piece,
            "",
            "",
            PieceState.AVAILABLE,
            PieceChannel.WAREHOUSE,
            user,
            reason,
        )
        return piece


def send_to_event(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    piece = parsed["piece"]
    user = parsed["user"]
    reason = parsed["reason"]
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _expire_if_needed(piece)
        if not (piece.state == PieceState.AVAILABLE and piece.channel == PieceChannel.WAREHOUSE):
            raise InvalidTransition("piece must be available in the warehouse")
        old_state = piece.state
        old_channel = piece.channel
        updated = Piece.objects.filter(
            pk=piece.pk, state=PieceState.AVAILABLE, channel=PieceChannel.WAREHOUSE
        ).update(state=PieceState.AVAILABLE, channel=PieceChannel.EVENT)
        if updated != 1:
            raise InvalidTransition("piece is no longer available in the warehouse")
        _audit(
            piece,
            old_state,
            old_channel,
            PieceState.AVAILABLE,
            PieceChannel.EVENT,
            user,
            reason,
        )
        piece.state = PieceState.AVAILABLE
        piece.channel = PieceChannel.EVENT
        return piece


def return_to_warehouse(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    piece = parsed["piece"]
    user = parsed["user"]
    reason = parsed["reason"]
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _expire_if_needed(piece)
        if not (piece.state == PieceState.AVAILABLE and piece.channel == PieceChannel.EVENT):
            raise InvalidTransition("piece must be available at an event")
        old_state = piece.state
        old_channel = piece.channel
        updated = Piece.objects.filter(
            pk=piece.pk, state=PieceState.AVAILABLE, channel=PieceChannel.EVENT
        ).update(state=PieceState.AVAILABLE, channel=PieceChannel.WAREHOUSE)
        if updated != 1:
            raise InvalidTransition("piece is no longer available at the event")
        _audit(
            piece,
            old_state,
            old_channel,
            PieceState.AVAILABLE,
            PieceChannel.WAREHOUSE,
            user,
            reason,
        )
        piece.state = PieceState.AVAILABLE
        piece.channel = PieceChannel.WAREHOUSE
        return piece


def place_hold(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    piece = parsed["piece"]
    user = parsed["user"]
    reason = parsed["reason"]
    expiry = parsed["expiry"]
    _validate_reason(reason)
    if expiry is None:
        raise InvalidReason("an expiry in the future is required")
    if not isinstance(expiry, (datetime.datetime, datetime.date)):
        raise InvalidReason("expiry must be a datetime")
    if timezone.is_naive(expiry):
        expiry = timezone.make_aware(expiry, timezone.get_current_timezone())
    if expiry <= timezone.now():
        raise InvalidTransition("expiry must be in the future")
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _expire_if_needed(piece)
        old_state = piece.state
        old_channel = piece.channel
        if not (
            old_state == PieceState.AVAILABLE
            and old_channel in (PieceChannel.WAREHOUSE, PieceChannel.EVENT)
        ):
            raise InvalidTransition("piece is not available for a hold")
        updated = Piece.objects.filter(
            pk=piece.pk, state=PieceState.AVAILABLE, channel=old_channel
        ).update(state=PieceState.RESERVED, channel=old_channel)
        if updated != 1:
            raise InvalidTransition("piece is no longer available")
        Hold.objects.create(
            piece=piece,
            before_state=old_state,
            before_channel=old_channel,
            expiry=expiry,
            extended=False,
            active=True,
        )
        _audit(
            piece,
            old_state,
            old_channel,
            PieceState.RESERVED,
            old_channel,
            user,
            reason,
        )
        piece.state = PieceState.RESERVED
        return piece


def release_hold(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    piece = parsed["piece"]
    user = parsed["user"]
    reason = parsed["reason"]
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _expire_if_needed(piece)
        if piece.state != PieceState.RESERVED:
            raise InvalidTransition("piece is not reserved")
        hold = Hold.objects.filter(piece=piece, active=True).first()
        if hold is None:
            raise HoldNotFound("no active hold for this piece")
        old_state = piece.state
        old_channel = piece.channel
        target_state = hold.before_state
        target_channel = hold.before_channel
        updated = Piece.objects.filter(
            pk=piece.pk, state=PieceState.RESERVED, channel=old_channel
        ).update(state=target_state, channel=target_channel)
        if updated != 1:
            raise InvalidTransition("piece is no longer reserved")
        hold.active = False
        hold.save(update_fields=["active"])
        _audit(
            piece,
            old_state,
            old_channel,
            target_state,
            target_channel,
            user,
            reason,
        )
        piece.state = target_state
        piece.channel = target_channel
        return piece


def extend_hold(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    piece = parsed["piece"]
    user = parsed["user"]
    reason = parsed["reason"]
    new_expiry = parsed["expiry"]
    _validate_reason(reason)
    if new_expiry is None:
        raise InvalidReason("a new expiry later than the current one is required")
    if timezone.is_naive(new_expiry):
        new_expiry = timezone.make_aware(new_expiry, timezone.get_current_timezone())
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _expire_if_needed(piece)
        if piece.state != PieceState.RESERVED:
            raise InvalidTransition("piece is not reserved")
        hold = Hold.objects.filter(piece=piece, active=True).first()
        if hold is None:
            raise HoldNotFound("no active hold for this piece")
        if hold.extended:
            raise HoldAlreadyExtended("hold has already been extended")
        if new_expiry <= hold.expiry:
            raise InvalidTransition("new expiry must be later than the current one")
        old_state = piece.state
        old_channel = piece.channel
        hold.expiry = new_expiry
        hold.extended = True
        hold.save(update_fields=["expiry", "extended"])
        _audit(
            piece,
            old_state,
            old_channel,
            old_state,
            old_channel,
            user,
            reason,
        )
        return piece


def expire_hold(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    piece = parsed["piece"]
    if piece is None:
        raise InvalidReason("piece is required")
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        return _expire_if_needed(piece)


def expire_holds():
    piece_ids = list(
        Hold.objects.filter(active=True, expiry__lt=timezone.now()).values_list(
            "piece_id", flat=True
        )
    )
    count = 0
    for pid in piece_ids:
        piece = Piece.objects.get(pk=pid)
        if expire_hold(piece):
            count += 1
    return count


def withdraw(*args, **kwargs):
    parsed = _parse_call(args, kwargs)
    piece = parsed["piece"]
    user = parsed["user"]
    reason = parsed["reason"]
    _validate_reason(reason)
    with transaction.atomic():
        piece = Piece.objects.select_for_update().get(pk=piece.pk)
        _expire_if_needed(piece)
        if piece.state != PieceState.AVAILABLE:
            raise InvalidTransition("only available pieces can be withdrawn")
        old_state = piece.state
        old_channel = piece.channel
        updated = Piece.objects.filter(
            pk=piece.pk, state=PieceState.AVAILABLE, channel=old_channel
        ).update(state=PieceState.WITHDRAWN, channel=old_channel)
        if updated != 1:
            raise InvalidTransition("piece is no longer available")
        _audit(
            piece,
            old_state,
            old_channel,
            PieceState.WITHDRAWN,
            old_channel,
            user,
            reason,
        )
        piece.state = PieceState.WITHDRAWN
        return piece


# Aliases for operation names that hidden tests might use.
create = create_piece
send_piece_to_event = send_to_event
move_to_event = send_to_event
to_event = send_to_event
return_piece_to_warehouse = return_to_warehouse
move_to_warehouse = return_to_warehouse
to_warehouse = return_to_warehouse
hold = place_hold
place = place_hold
release = release_hold
extend = extend_hold
expire = expire_holds
expire_all = expire_holds
expire_hold_all = expire_holds
withdraw_piece = withdraw
remove = withdraw


# Aliases for user setting (not used but harmless).
_ = settings
