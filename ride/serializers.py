from decimal import Decimal
from rest_framework import serializers
from .models import (
    RideRequest, RideRequestMatch, Ride,
    RideRequestStatus, MatchStatus, RideStatus, PaymentMethod,
    PricingConfig, PricingMode, NegotiationOffer
)

class RideRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = [
            "pickup_address", "dropoff_address",
            "pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng",
            "payment_method", "city", "vehicle_type",
        ]

    def validate_payment_method(self, v):
        if v not in dict(PaymentMethod.choices):
            raise serializers.ValidationError("Invalid payment method.")
        return v

    def create(self, validated_data):
        user = self.context["request"].user
        return RideRequest.objects.create(customer=user, **validated_data)


class RideRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = "__all__"
        read_only_fields = ("customer", "requested_at", "status", "distance_km", "estimated_amount_low", "estimated_amount_high")


class RideRequestMatchSerializer(serializers.ModelSerializer):
    driver_username = serializers.SerializerMethodField()

    class Meta:
        model = RideRequestMatch
        fields = ["id", "request", "driver", "driver_username", "vehicle", "status", "distance_to_pickup_km", "eta_to_pickup_min", "created_at"]
        read_only_fields = ["status", "created_at", "distance_to_pickup_km", "eta_to_pickup_min"]

    def get_driver_username(self, obj):
        return getattr(obj.driver.user, "username", None)


class RideSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ride
        fields = "__all__"
        read_only_fields = (
            "customer", "driver", "vehicle", "requested_at", "started_at", "ended_at",
            "status", "estimated_amount_low", "estimated_amount_high"
        )


class PricingConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingConfig
        fields = "__all__"


class NegotiationOfferSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    class Meta:
        model = NegotiationOffer
        fields = ["id", "request", "role", "user", "username", "amount", "created_at"]
        read_only_fields = ["user", "created_at"]

    def get_username(self, obj):
        return obj.user.username


class RideCompleteSerializer(serializers.Serializer):
    amount_total = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    end_lat = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    end_lng = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    end_address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
