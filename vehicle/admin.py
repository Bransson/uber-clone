from django.contrib import admin
from .models import VehicleType, Vehicle

@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "base_fare", "per_km_rate", "per_minute_rate")
    search_fields = ("name",)

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("license_plate", "model", "color", "year", "vehicle_type", "driver", "is_active")
    search_fields = ("license_plate", "model")
    list_filter = ("vehicle_type", "is_active")
    autocomplete_fields = ("vehicle_type", "driver")
