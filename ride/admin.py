from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Ride, RideRequest, RideRequestMatch, PricingConfig, NegotiationOffer

@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "driver", "city", "vehicle_type", "status", "payment_method", "requested_at", "amount_total", "amount_paid", "distance_km")
    list_filter = ("status", "payment_method", "requested_at", "city", "vehicle_type")
    search_fields = ("id", "customer__email", "driver__user__email", "pickup_address", "dropoff_address")
    autocomplete_fields = ("customer", "driver", "vehicle", "rating")
    readonly_fields = ("requested_at", "started_at", "ended_at")

@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "city", "vehicle_type", "status", "requested_at", "distance_km", "estimated_amount_low", "estimated_amount_high")
    list_filter = ("status", "requested_at", "city", "vehicle_type")
    search_fields = ("id", "customer__email", "pickup_address", "dropoff_address")
    autocomplete_fields = ("customer",)
    readonly_fields = ("requested_at",)

@admin.register(RideRequestMatch)
class RideRequestMatchAdmin(admin.ModelAdmin):
    list_display = ("id", "request", "driver", "vehicle", "status", "distance_to_pickup_km", "eta_to_pickup_min", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "request__id", "driver__user__email")
    autocomplete_fields = ("request", "driver", "vehicle")
    readonly_fields = ("created_at",)

@admin.register(PricingConfig)
class PricingConfigAdmin(admin.ModelAdmin):
    list_display = ("city", "vehicle_type", "mode", "base_fare", "per_km", "per_min", "booking_fee", "min_fare", "surge_multiplier", "commission_pct", "active")
    list_filter = ("city", "vehicle_type", "mode", "active")
    search_fields = ("city", "vehicle_type")

@admin.register(NegotiationOffer)
class NegotiationOfferAdmin(admin.ModelAdmin):
    list_display = ("id", "request", "role", "user", "amount", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("user__username",)
    autocomplete_fields = ("request", "user")
