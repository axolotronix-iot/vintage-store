from django.conf import settings
from django.db import models


class PieceState(models.TextChoices):
    AVAILABLE = "available", "Disponible"
    RESERVED = "reserved", "Reservada"
    SOLD = "sold", "Vendida"
    WITHDRAWN = "withdrawn", "Dada de baja"


class PieceChannel(models.TextChoices):
    WAREHOUSE = "warehouse", "Bodega"
    EVENT = "event", "Evento"
    WEBSITE = "website", "Página propia"
    GOTRENDIER = "gotrendier", "GoTrendier"


class Piece(models.Model):
    state = models.CharField(
        max_length=20,
        choices=PieceState.choices,
        default=PieceState.AVAILABLE,
    )
    channel = models.CharField(
        max_length=20,
        choices=PieceChannel.choices,
        default=PieceChannel.WAREHOUSE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Piece {self.pk} ({self.state}/{self.channel})"


class Hold(models.Model):
    piece = models.ForeignKey("Piece", on_delete=models.PROTECT, related_name="holds")
    previous_state = models.CharField(max_length=20, choices=PieceState.choices)
    previous_channel = models.CharField(max_length=20, choices=PieceChannel.choices)
    expires_at = models.DateTimeField()
    extended = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["piece"],
                condition=models.Q(active=True),
                name="inventory_hold_one_active_per_piece",
            ),
        ]

    def __str__(self):
        return f"Hold for piece {self.piece_id} (active={self.active})"


class PieceTransition(models.Model):
    piece = models.ForeignKey("Piece", on_delete=models.PROTECT, related_name="transitions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="piece_transitions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    from_state = models.CharField(max_length=20, choices=PieceState.choices, blank=True, default="")
    from_channel = models.CharField(
        max_length=20, choices=PieceChannel.choices, blank=True, default=""
    )
    to_state = models.CharField(max_length=20, choices=PieceState.choices)
    to_channel = models.CharField(max_length=20, choices=PieceChannel.choices)
    reason = models.TextField()

    def __str__(self):
        return (
            f"Transition piece {self.piece_id}: "
            f"{self.from_state}/{self.from_channel} -> "
            f"{self.to_state}/{self.to_channel}"
        )
