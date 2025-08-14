from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RideRequestViewSet, RideRequestMatchViewSet, RideViewSet,
    PricingConfigViewSet, NegotiationOfferViewSet
)

router = DefaultRouter()
router.register(r"ride-requests", RideRequestViewSet, basename="ride-request")
router.register(r"matches", RideRequestMatchViewSet, basename="ride-request-match")
router.register(r"rides", RideViewSet, basename="ride")
router.register(r"pricing-configs", PricingConfigViewSet, basename="pricing-config")
router.register(r"offers", NegotiationOfferViewSet, basename="offers")

urlpatterns = [path("", include(router.urls))]
