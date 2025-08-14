from django.shortcuts import render

# Create your views here.
from decimal import Decimal
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from django.shortcuts import get_object_or_404

from .models import (
    RideRequest, RideRequestMatch, Ride,
    MatchStatus, RideStatus, RideRequestStatus,
    PricingConfig, PricingMode, NegotiationOffer
)
from .serializers import (
    RideRequestCreateSerializer, RideRequestSerializer,
    RideRequestMatchSerializer, RideSerializer,
    PricingConfigSerializer, NegotiationOfferSerializer, RideCompleteSerializer
)
from .permissions import IsAuthenticatedAndCustomer, IsAuthenticatedAndDriver
from .services import (
    accept_match, reject_match, start_ride, complete_ride, cancel_ride_request,
    get_pricing_config, metered_quote
)


class RideRequestViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = RideRequest.objects.select_related("customer").all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return RideRequestCreateSerializer
        return RideRequestSerializer

    def get_permissions(self):
        if self.action in ("create", "my_requests", "cancel", "quote"):
            return [IsAuthenticatedAndCustomer()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def my_requests(self, request):
        qs = self.get_queryset().filter(customer=request.user)
        return Response(RideRequestSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        req = self.get_object()
        cancel_ride_request(req, request.user)
        return Response(RideRequestSerializer(req).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def quote(self, request):
        """
        Metered quick quote without creating a request (for preview screens).
        body: {pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, city, vehicle_type}
        """
        data = request.data
        try:
            pickup_lat = float(data["pickup_lat"]); pickup_lng = float(data["pickup_lng"])
            dropoff_lat = float(data["dropoff_lat"]); dropoff_lng = float(data["dropoff_lng"])
        except Exception:
            return Response({"detail": "Invalid coordinates."}, status=400)
        city = data.get("city", "Lagos")
        vehicle_type = data.get("vehicle_type", "Standard")
        cfg = get_pricing_config(city, vehicle_type)

        if cfg.mode != PricingMode.METERED:
            return Response({"mode": cfg.mode, "detail": "Negotiated mode: no metered quote."}, status=200)

        # rough straight-line distance & duration
        from .services import haversine_km, _estimate_eta_min
        dist_km = Decimal(str(round(haversine_km(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng), 2)))
        duration_min = Decimal(str(_estimate_eta_min(float(dist_km), avg_speed_kmh=22.0)))
        band = metered_quote(dist_km, duration_min, cfg)
        return Response({
            "mode": cfg.mode,
            "city": city,
            "vehicle_type": vehicle_type,
            "distance_km": str(dist_km),
            "low": str(band.low),
            "high": str(band.high),
            "surge": str(cfg.surge_multiplier),
            "min_fare": str(cfg.min_fare),
        })
        

class RideRequestMatchViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = RideRequestMatch.objects.select_related("request", "driver", "vehicle").all()
    serializer_class = RideRequestMatchSerializer
    permission_classes = [IsAuthenticatedAndDriver]

    def get_queryset(self):
        return super().get_queryset().filter(driver__user=self.request.user)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        match = self.get_object()
        ride = accept_match(match, request.user)
        return Response(RideSerializer(ride).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        match = self.get_object()
        reject_match(match, request.user)
        return Response(RideRequestMatchSerializer(match).data, status=status.HTTP_200_OK)


class RideViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Ride.objects.select_related("driver__user", "customer", "vehicle").all()
    serializer_class = RideSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        if hasattr(u, "driver_profile"):
            return self.queryset.filter(driver__user=u)
        return self.queryset.filter(customer=u)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticatedAndDriver])
    def start(self, request, pk=None):
        ride = self.get_object()
        start_ride(ride, request.user)
        return Response(RideSerializer(ride).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticatedAndDriver])
    def complete(self, request, pk=None):
        ride = self.get_object()
        ser = RideCompleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        complete_ride(
            ride,
            request.user,
            amount_total=ser.validated_data.get("amount_total"),
            end_lat=ser.validated_data.get("end_lat"),
            end_lng=ser.validated_data.get("end_lng"),
            end_address=ser.validated_data.get("end_address") or "",
        )
        return Response(RideSerializer(ride).data)

    @action(detail=False, methods=["get"])
    def my_rides(self, request):
        qs = self.get_queryset()
        return Response(RideSerializer(qs, many=True).data)


class PricingConfigViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    queryset = PricingConfig.objects.all()
    serializer_class = PricingConfigSerializer
    permission_classes = [IsAdminUser]


class NegotiationOfferViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = NegotiationOffer.objects.select_related("request", "user").all()
    serializer_class = NegotiationOfferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # participants can see their own request offers
        u = self.request.user
        return super().get_queryset().filter(user=u)

    def perform_create(self, serializer):
        req_id = self.request.data.get("request")
        role = self.request.data.get("role")
        amount = Decimal(str(self.request.data.get("amount")))
        req = get_object_or_404(RideRequest, pk=req_id)
        from .services import submit_offer
        offer = submit_offer(req, self.request.user, role, amount)
        serializer.instance = offer
