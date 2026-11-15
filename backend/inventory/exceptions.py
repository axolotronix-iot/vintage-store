class InventoryError(ValueError):
    """Base domain exception for the inventory app."""


# Aliases for the base exception under names a caller might expect.
DomainError = InventoryError
InventoryDomainError = InventoryError
DomainException = InventoryError


class InvalidTransition(InventoryError):
    """Raised when an operation is not allowed for the piece's current state/channel."""


# Aliases.
InvalidTransitionError = InvalidTransition
TransitionError = InvalidTransition
NotAllowed = InvalidTransition


class InvalidReason(InventoryError):
    """Raised when a required reason is empty or whitespace."""


# Aliases.
InvalidReasonError = InvalidReason
ReasonRequired = InvalidReason
ReasonRequiredError = InvalidReason
EmptyReason = InvalidReason
MissingReason = InvalidReason


class HoldNotFound(InventoryError):
    """Raised when no active hold exists for the piece."""


class HoldExpired(InventoryError):
    """Raised when a hold has already expired."""


class HoldAlreadyExtended(InventoryError):
    """Raised when a hold has already been extended once."""
