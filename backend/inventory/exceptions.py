class InventoryError(Exception):
    """Base class for all inventory domain rejections."""


class InvalidUser(InventoryError):
    pass


class InvalidReason(InventoryError):
    pass


class InvalidExpiry(InventoryError):
    pass


class InvalidTransition(InventoryError):
    pass
