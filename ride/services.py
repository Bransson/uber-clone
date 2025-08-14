from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, List

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.apps import apps

from math import radians, sin, cos, asin, sqrt

from .models import (
    RideRequest, RideRequestStatus, RideRequestMatch, MatchStatus,
    Ride, RideStatus, PaymentMethod,
    PricingConfig, PricingMode, NegotiationOffer
)

EARTH_RADIUS_KM = 6371.0

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_KM * c


# ---- Pricing (Metered) ----

@dataclass
class PriceBand:
    low: Decimal
    high: Decimal

def round_money(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def metered_quote(distance_km: Decimal, duration_min: Decimal, cfg: PricingConfig, discount: Decimal = Decimal("0.00")) -> PriceBand:
    total = cfg.base_fare + cfg.per_km * distance_km + cfg.per_min * duration_min + cfg.booking_fee
    total = total * cfg.surge_multiplier
    total = max(total, cfg.min_fare)
    total = max(total - discount, Decimal("0.00"))
    total = round_money(total)
    band = round_money(total * Decimal("0.10"))
    return PriceBand(low=max(total - band, Decimal("0.00")), high=total + band)

def get_pricing_config(city: str, vehicle_type: str) -> PricingConfig:
    cfg = PricingConfig.objects.filter(city__iexact=city, vehicle_type__iexact=vehicle_type, active=True).first()
    if not cfg:
        # fallback default
        cfg = PricingConfig.objects.create(
            city=city, vehicle_type=vehicle_type, mode=PricingMode.METERED,
            base_fare=Decimal("250.00"), per_km=Decimal("120.00"), per_min=Decimal("10.00"),
            booking_fee=Decimal("100.00"), min_fare=Decimal("600.00"),
            surge_multiplier=Decimal("1.00"), commission_pct=Decimal("15.00"), active=True
        )
    return cfg


# ---- Nearby Drivers ----

def _get_driver_location(driver) -> Optional[Tuple[float, float]]:
    lat = getattr(driver, "current_lat", None)
    lng = getattr(driver, "current_lng", None)
    if lat is None or lng is None:
        return None
    try:
        return float(lat), float(lng)
    except Exception:
        return None

def _estimate_eta_min(distance_km: float, avg_speed_kmh: float = 24.0) -> int:
    if avg_speed_kmh <= 0:
        return 0
    minutes = (distance_km / avg_speed_kmh) * 60.0
    return max(1, int(round(minutes)))

def find_nearby_drivers(driver_qs, pickup_lat: float, pickup_lng: float, radius_km: float = 8.0, limit: int = 5):
    from dataclasses import dataclass
    @dataclass
    class DriverCandidate:
        driver_id: int
        vehicle_id: Optional[int]
        distance_km: Decimal
        eta_min: int
    cands: List[DriverCandidate] = []
    for d in driver_qs:
        if not getattr(d, "is_available", False):
            continue
        loc = _get_driver_location(d)
        if not loc:
            continue
        dlat, dlng = loc
        dist = haversine_km(pickup_lat, pickup_lng, dlat, dlng)
        if dist <= radius_km:
            vehicle_id = getattr(d, "active_vehicle_id", None) or getattr(d, "vehicle_id", None) or None
            cands.append(DriverCandidate(
                driver_id=d.id,
                vehicle_id=vehicle_id,
                distance_km=Decimal(str(round(dist, 2))),
                eta_min=_estimate_eta_min(dist)
            ))
    cands.sort(key=lambda c: (c.distance_km, c.eta_min))
    return cands[:limit]

@transaction.atomic
def build_matches_for_request(req: RideRequest, driver_qs, limit: int = 5) -> int:
    cands = find_nearby_drivers(driver_qs, float(req.pickup_lat), float(req.pickup_lng), limit=limit)
    created = 0
    for c in cands:
        RideRequestMatch.objects.get_or_create(
            request=req, driver_id=c.driver_id,
            defaults={
                "vehicle_id": c.vehicle_id,
                "status": MatchStatus.PENDING,
                "distance_to_pickup_km": c.distance_km,
                "eta_to_pickup_min": c.eta_min,
            }
        )
        created += 1
    return created

def compute_request_estimates(req: RideRequest) -> None:
    # distance
    dist_km = Decimal(str(round(haversine_km(float(req.pickup_lat), float(req.pickup_lng),
                                             float(req.dropoff_lat), float(req.dropoff_lng)), 2)))
    # crude duration estimate using avg speed ~22km/h
    duration_min = Decimal(str(_estimate_eta_min(float(dist_km), avg_speed_kmh=22.0)))

    cfg = get_pricing_config(req.city, req.vehicle_type)
    if cfg.mode == PricingMode.METERED:
        band = metered_quote(dist_km, duration_min, cfg)
        req.distance_km = dist_km
        req.estimated_amount_low = band.low
        req.estimated_amount_high = band.high
        req.save(update_fields=["distance_km", "estimated_amount_low", "estimated_amount_high"])
    else:
        # Negotiated: keep band empty; front-end will drive offers
        req.distance_km = dist_km
        req.estimated_amount_low = Decimal("0.00")
        req.estimated_amount_high = Decimal("0.00")
        req.save(update_fields=["distance_km", "estimated_amount_low", "estimated_amount_high"])


# ---- State transitions ----

@transaction.atomic
def accept_match(match: RideRequestMatch, driver_user) -> Ride:
    if match.status != MatchStatus.PENDING:
        raise ValidationError("Match is not pending.")
    if match.driver.user_id != driver_user.id:
        raise PermissionDenied("You cannot accept someone else's match.")

    req = match.request
    if req.status != RideRequestStatus.OPEN:
        raise ValidationError("Ride request is not open anymore.")

    # lock other matches
    RideRequestMatch.objects.filter(request=req).exclude(pk=match.pk).update(status=MatchStatus.REJECTED)
    match.status = MatchStatus.ACCEPTED
    match.save(update_fields=["status"])

    req.status = RideRequestStatus.MATCHED
    req.save(update_fields=["status"])

    # amount_total: for NEGOTIATED, take last rider or agreed driver offer if exists; else use high estimate
    cfg = get_pricing_config(req.city, req.vehicle_type)
    amount_total = req.estimated_amount_high
    if cfg.mode == PricingMode.NEGOTIATED:
        latest_offer = NegotiationOffer.objects.filter(request=req).order_by("-created_at").first()
        if latest_offer:
            amount_total = latest_offer.amount

    ride = Ride.objects.create(
        driver=match.driver,
        vehicle=match.vehicle,
        customer=req.customer,
        pickup_address=req.pickup_address,
        dropoff_address=req.dropoff_address,
        end_address="",
        pickup_lat=req.pickup_lat,
        pickup_lng=req.pickup_lng,
        dropoff_lat=req.dropoff_lat,
        dropoff_lng=req.dropoff_lng,
        distance_km=req.distance_km,
        estimated_amount_low=req.estimated_amount_low,
        estimated_amount_high=req.estimated_amount_high,
        amount_total=amount_total,
        payment_method=req.payment_method,
        status=RideStatus.ACCEPTED,
        requested_at=req.requested_at,
        city=req.city,
        vehicle_type=req.vehicle_type,
    )

    drv = match.driver
    if drv.is_available:
        drv.is_available = False
        drv.save(update_fields=["is_available"])

    return ride

@transaction.atomic
def reject_match(match: RideRequestMatch, driver_user):
    if match.status != MatchStatus.PENDING:
        raise ValidationError("Match is not pending.")
    if match.driver.user_id != driver_user.id:
        raise PermissionDenied("You cannot reject someone else's match.")
    match.status = MatchStatus.REJECTED
    match.save(update_fields=["status"])

@transaction.atomic
def start_ride(ride: Ride, driver_user):
    if ride.status != RideStatus.ACCEPTED:
        raise ValidationError("Ride cannot be started.")
    if ride.driver is None or ride.driver.user_id != driver_user.id:
        raise PermissionDenied("You cannot start this ride.")
    ride.status = RideStatus.IN_PROGRESS
    ride.started_at = timezone.now()
    ride.save(update_fields=["status", "started_at"])

@transaction.atomic
def complete_ride(ride: Ride, driver_user, amount_total: Optional[Decimal] = None, end_lat=None, end_lng=None, end_address:str=""):
    if ride.status != RideStatus.IN_PROGRESS:
        raise ValidationError("Ride is not in progress.")
    if ride.driver is None or ride.driver.user_id != driver_user.id:
        raise PermissionDenied("You cannot complete this ride.")
    ride.status = RideStatus.COMPLETED
    ride.ended_at = timezone.now()
    if amount_total is not None:
        ride.amount_total = round_money(amount_total)
    if end_lat is not None:
        ride.end_lat = end_lat
    if end_lng is not None:
        ride.end_lng = end_lng
    if end_address:
        ride.end_address = end_address
    ride.save(update_fields=["status", "ended_at", "amount_total", "end_lat", "end_lng", "end_address"])

    if ride.driver:
        ride.driver.is_available = True
        ride.driver.total_rides = (ride.driver.total_rides or 0) + 1
        ride.driver.save(update_fields=["is_available", "total_rides"])

@transaction.atomic
def cancel_ride_request(req: RideRequest, user):
    if req.customer_id != user.id:
        raise PermissionDenied("You cannot cancel another user's request.")
    if req.status != RideRequestStatus.OPEN:
        raise ValidationError("Request cannot be canceled now.")
    req.status = RideRequestStatus.CANCELED
    req.save(update_fields=["status"])
    RideRequestMatch.objects.filter(request=req, status=MatchStatus.PENDING).update(status=MatchStatus.EXPIRED)


# ---- Negotiation helpers ----

@transaction.atomic
def submit_offer(req: RideRequest, user, role: str, amount: Decimal) -> NegotiationOffer:
    cfg = get_pricing_config(req.city, req.vehicle_type)
    if cfg.mode != PricingMode.NEGOTIATED:
        raise ValidationError("Negotiation is disabled for this request.")

    if role == "RIDER" and req.customer_id != user.id:
        raise PermissionDenied("Only the requesting rider can submit rider offers.")
    if role == "DRIVER":
        # any matched or pending driver can make an offer; simplest version:
        pass

    # Optional: enforce soft bounds based on metered baseline
    # Compute a reference metered price to bound offers (e.g., 50% .. 200%)
    dist_km = req.distance_km
    duration_min = Decimal("0")  # unknown; we can set a nominal value or compute as earlier
    ref_cfg = PricingConfig(city=req.city, vehicle_type=req.vehicle_type, mode=PricingMode.METERED,
                            base_fare=Decimal("250.00"), per_km=Decimal("120.00"), per_min=Decimal("10.00"),
                            booking_fee=Decimal("100.00"), min_fare=Decimal("600.00"), surge_multiplier=Decimal("1.00"),
                            commission_pct=Decimal("15.00"), active=True)
    ref_band = metered_quote(dist_km, Decimal("15"), ref_cfg)  # assume 15min nominal
    min_allowed = round_money(ref_band.low * Decimal("0.5"))
    max_allowed = round_money(ref_band.high * Decimal("2.0"))

    if amount < min_allowed or amount > max_allowed:
        raise ValidationError(f"Offer must be between {min_allowed} and {max_allowed} for sanity.")

    offer = NegotiationOffer.objects.create(request=req, role=role, user=user, amount=round_money(amount))
    return offer
