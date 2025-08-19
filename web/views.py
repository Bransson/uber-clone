from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest

from .forms import LoginForm, RegisterForm, RideRequestForm
from ride.models import RideRequest, RideRequestMatch, Ride, RideRequestStatus, MatchStatus
from profiles.models import Customer, Driver
from ride import services as ride_services
from django.utils import timezone

def index(request):
    if request.user.is_authenticated:
        # route to driver or customer dashboard
        if hasattr(request.user, "driver_profile"):
            return redirect("driver_dashboard")
        return redirect("customer_dashboard")
    return redirect("login")

def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            # allow login via username or email
            user = authenticate(request, username=username, password=password)
            if user is None:
                # try authenticate by email
                from profiles.models import CustomUser
                try:
                    u = CustomUser.objects.get(email__iexact=username)
                    user = authenticate(request, username=u.username, password=password)
                except CustomUser.DoesNotExist:
                    user = None
            if user:
                login(request, user)
                print(request.user)
                return redirect(index)
            form.add_error(None, "Invalid credentials")
    else:
        form = LoginForm()
    
    return render(request, "auth/login.html", {"form": form})

def logout_view(request):
    logout(request)
    return redirect("login")

def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(index)
    else:
        form = RegisterForm()
    return render(request, "auth/register.html", {"form": form})

@login_required
def customer_dashboard(request):
    # Show customer's ride requests and active rides
    try:
        cust = request.user.customer_profile
    except Customer.DoesNotExist:
        return HttpResponseForbidden("Not a customer account.")
    requests = RideRequest.objects.filter(customer=request.user).order_by("-requested_at")[:10]
    active_rides = Ride.objects.filter(customer=request.user).exclude(status__in=[RideRequestStatus.CANCELED, "COMPLETED"]).order_by("-requested_at")
    return render(request, "customer/dashboard.html", {"requests": requests, "active_rides": active_rides})

@login_required
def request_ride(request):
    try:
        cust = request.user.customer_profile
    except Customer.DoesNotExist:
        return HttpResponseForbidden("Not a customer account.")
    if request.method == "POST":
        form = RideRequestForm(request.POST)
        if form.is_valid():
            rr = RideRequest.objects.create(
                customer=request.user,
                pickup_address=form.cleaned_data["pickup_address"],
                dropoff_address=form.cleaned_data["dropoff_address"],
                pickup_lat=form.cleaned_data["pickup_lat"],
                pickup_lng=form.cleaned_data["pickup_lng"],
                dropoff_lat=form.cleaned_data["dropoff_lat"],
                dropoff_lng=form.cleaned_data["dropoff_lng"],
                payment_method=form.cleaned_data["payment_method"],
                city=form.cleaned_data.get("city", "Lagos"),
                vehicle_type=form.cleaned_data.get("vehicle_type", "Standard"),
            )
            # compute estimates + matches (signals already run on save; but just in case)
            ride_services.compute_request_estimates(rr)
            from django.apps import apps
            DriverModel = apps.get_model("profiles", "Driver")
            driver_qs = DriverModel.objects.all().only("id", "is_available", "current_lat", "current_lng", "vehicle_id")
            ride_services.build_matches_for_request(rr, driver_qs=driver_qs, limit=5)
            return redirect("ride_status", rr.pk)
    else:
        form = RideRequestForm()
    return render(request, "customer/request_ride.html", {"form": form})

@login_required
def ride_status(request, pk):
    # shows status and polls matches
    req = get_object_or_404(RideRequest, pk=pk, customer=request.user)
    return render(request, "customer/ride_status.html", {"request_obj": req})

@login_required
def driver_dashboard(request):
    try:
        drv = request.user.driver_profile
    except Driver.DoesNotExist:
        return HttpResponseForbidden("Not a driver account.")
    # show pending matches
    matches = RideRequestMatch.objects.filter(driver=drv).order_by("created_at")
    active_rides = Ride.objects.filter(driver=drv).exclude(status__in=["COMPLETED", "CANCELED"]).order_by("-requested_at")
    return render(request, "driver/dashboard.html", {"matches": matches, "active_rides": active_rides})

@login_required
def driver_ride_detail(request, ride_id):
    try:
        drv = request.user.driver_profile
    except Driver.DoesNotExist:
        return HttpResponseForbidden("Not a driver account.")
    ride = get_object_or_404(Ride, pk=ride_id, driver=drv)
    return render(request, "driver/ride_detail.html", {"ride": ride})

# AJAX endpoints for driver accept / reject and customer poll
@login_required
@require_POST
def accept_match_view(request, match_id):
    try:
        drv = request.user.driver_profile
    except Driver.DoesNotExist:
        return HttpResponseForbidden()
    match = get_object_or_404(RideRequestMatch, pk=match_id, driver=drv)
    try:
        ride = ride_services.accept_match(match, request.user)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True, "ride_id": ride.id})

@login_required
@require_POST
def reject_match_view(request, match_id):
    try:
        drv = request.user.driver_profile
    except Driver.DoesNotExist:
        return HttpResponseForbidden()
    match = get_object_or_404(RideRequestMatch, pk=match_id, driver=drv)
    try:
        ride_services.reject_match(match, request.user)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)
    return JsonResponse({"ok": True})

@login_required
def poll_request_status(request, request_id):
    rr = get_object_or_404(RideRequest, pk=request_id, customer=request.user)
    matches = list(rr.matches.order_by("created_at").values("id", "driver__user__username", "status", "distance_to_pickup_km", "eta_to_pickup_min"))
    # check if matched -> find ride
    ride = Ride.objects.filter(customer=request.user, pickup_lat=rr.pickup_lat, pickup_lng=rr.pickup_lng, requested_at=rr.requested_at).first()
    ride_info = None
    if ride:
        ride_info = {"id": ride.id, "status": ride.status, "driver": getattr(ride.driver.user, "username", None)}
    return JsonResponse({"status": rr.status, "matches": matches, "ride": ride_info})
