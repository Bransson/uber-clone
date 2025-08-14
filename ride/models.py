from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone


class PaymentMethod(models.TextChoices):
    INAPP = "INAPP", "In‑App"
    CASH = "CASH", "Cash"


class RideStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"
    ACCEPTED = "ACCEPTED", "Accepted"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED = "COMPLETED", "Completed"
    CANCELED = "CANCELED", "Canceled"


class RideRequestStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    MATCHED = "MATCHED", "Matched"
    EXPIRED = "EXPIRED", "Expired"
    CANCELED = "CANCELED", "Canceled"


class MatchStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    EXPIRED = "EXPIRED", "Expired"


# —— Pricing Configs —— #

class PricingMode(models.TextChoices):
    METERED = "METERED", "Metered (Bolt/LagRide)"
    NEGOTIATED = "NEGOTIATED", "Negotiated (inDrive)"


class PricingConfig(models.Model):
    """
    Editable from Admin: configure per-city & per-vehicle pricing and mode.
    """
    city = models.CharField(max_length=64, db_index=True)  # e.g., "Lagos", "Abuja" (free text or enum)
    vehicle_type = models.CharField(max_length=64, default="Standard")  # "Standard", "XL", "Bike", etc.
    mode = models.CharField(max_length=16, choices=PricingMode.choices, default=PricingMode.METERED)

    # Metered fields (used when mode=METERED)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("250.00"))
    per_km = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("120.00"))
    per_min = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("10.00"))
    booking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("100.00"))
    min_fare = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("600.00"))

    # Surge multiplier (1.0 = no surge)
    surge_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))

    # Platform commission percent (0-100). Applied on gross; informational for payout calc.
    commission_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("15.00"))

    active = models.BooleanField(default=True)

    class Meta:
        unique_together = [("city", "vehicle_type")]
        indexes = [
            models.Index(fields=["city"]),
            models.Index(fields=["vehicle_type"]),
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return f"{self.city} / {self.vehicle_type} [{self.mode}]"


# —— Core Ride Models —— #

class Ride(models.Model):
    driver = models.ForeignKey("profiles.Driver", on_delete=models.SET_NULL, blank=True, null=True, related_name="rides")
    vehicle = models.ForeignKey("vehicle.Vehicle", on_delete=models.SET_NULL, blank=True, null=True, related_name="rides")
    customer = models.ForeignKey("profiles.CustomUser", on_delete=models.CASCADE, related_name="rides")
    rating = models.ForeignKey("rating.Rating", on_delete=models.SET_NULL, blank=True, null=True, related_name="rides")

    pickup_address = models.CharField(max_length=256)
    dropoff_address = models.CharField(max_length=256)
    end_address = models.CharField(max_length=256, blank=True, default="")

    pickup_lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    pickup_lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    dropoff_lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    dropoff_lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    end_lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)], blank=True, null=True)
    end_lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)], blank=True, null=True)

    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    estimated_amount_low = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    estimated_amount_high = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    amount_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)

    requested_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)

    status = models.CharField(max_length=20, choices=RideStatus.choices, default=RideStatus.REQUESTED, db_index=True)

    city = models.CharField(max_length=64, default="Lagos")  # simple city tag used to select pricing config
    vehicle_type = models.CharField(max_length=64, default="Standard")

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["requested_at"]),
            models.Index(fields=["driver", "status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["vehicle_type"]),
        ]
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Ride #{self.pk} ({self.customer_id}) – {self.status}"


class RideRequest(models.Model):
    customer = models.ForeignKey("profiles.CustomUser", on_delete=models.CASCADE, related_name="ride_requests")

    pickup_address = models.CharField(max_length=256)
    dropoff_address = models.CharField(max_length=256)

    pickup_lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    pickup_lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    dropoff_lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    dropoff_lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])

    distance_km = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    estimated_amount_low = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    estimated_amount_high = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=RideRequestStatus.choices, default=RideRequestStatus.OPEN, db_index=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    # city/vehicle-type for pricing selection
    city = models.CharField(max_length=64, default="Lagos")
    vehicle_type = models.CharField(max_length=64, default="Standard")

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["requested_at"]),
            models.Index(fields=["customer", "status"]),
            models.Index(fields=["city"]),
            models.Index(fields=["vehicle_type"]),
        ]
        ordering = ["-requested_at"]

    def __str__(self):
        return f"RideRequest #{self.pk} – {self.status}"


class RideRequestMatch(models.Model):
    request = models.ForeignKey("ride.RideRequest", on_delete=models.CASCADE, related_name="matches")
    driver = models.ForeignKey("profiles.Driver", on_delete=models.CASCADE, related_name="ride_request_matches")
    vehicle = models.ForeignKey("vehicle.Vehicle", on_delete=models.SET_NULL, blank=True, null=True, related_name="ride_request_matches")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=MatchStatus.choices, default=MatchStatus.PENDING, db_index=True)
    distance_to_pickup_km = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    eta_to_pickup_min = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["request", "driver"], name="unique_request_driver")]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["created_at"])]

    def __str__(self):
        return f"Match req={self.request_id} driver={self.driver_id} ({self.status})"


# —— Negotiation (inDrive-like) —— #

class NegotiationOffer(models.Model):
    """
    Store rider/driver offers for a request (used when PricingConfig.mode=NEGOTIATED).
    """
    ROLE = (("RIDER", "Rider"), ("DRIVER", "Driver"))

    request = models.ForeignKey("ride.RideRequest", on_delete=models.CASCADE, related_name="offers")
    role = models.CharField(max_length=10, choices=ROLE)
    user = models.ForeignKey("profiles.CustomUser", on_delete=models.CASCADE, related_name="negotiation_offers")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["role"]), models.Index(fields=["created_at"])]
