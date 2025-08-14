from django.db import models
from django.utils.translation import gettext_lazy as _

class VehicleType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    per_km_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    per_minute_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Vehicle Type"
        verbose_name_plural = "Vehicle Types"

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    driver = models.OneToOneField(
        "profiles.Driver", on_delete=models.CASCADE, related_name="vehicle_profile", null=True, blank=True
    )
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.SET_NULL, null=True, related_name="vehicles")
    license_plate = models.CharField(_("license plate"), max_length=20, unique=True)
    model = models.CharField(max_length=50)
    color = models.CharField(max_length=30)
    year = models.PositiveIntegerField()

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.model} ({self.license_plate})"
