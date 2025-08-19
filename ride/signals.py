from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps

from .models import RideRequest, RideRequestStatus, Ride, RideStatus


@receiver(post_save, sender=RideRequest)
def on_ride_request_created(sender, instance: RideRequest, created: bool, **kwargs):
    from .services import compute_request_estimates, build_matches_for_request
    if not created:
        return
    compute_request_estimates(instance)
    Driver = apps.get_model("profiles", "Driver")
    driver_qs = Driver.objects.all().only("id", "is_available", "current_lat", "current_lng", "vehicle_id")
    build_matches_for_request(instance, driver_qs=driver_qs, limit=5)

@receiver(post_save, sender=Ride)
def sync_driver_availability(sender, instance: Ride, **kwargs):
    drv = instance.driver
    if not drv:
        return
    if instance.status in (RideStatus.ACCEPTED, RideStatus.IN_PROGRESS):
        if drv.is_available:
            drv.is_available = False
            drv.save(update_fields=["is_available"])
    elif instance.status in (RideStatus.COMPLETED, RideStatus.CANCELED):
        if not drv.is_available:
            drv.is_available = True
            drv.save(update_fields=["is_available"])
