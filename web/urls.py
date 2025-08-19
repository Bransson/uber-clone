from django.urls import path
from . import views


urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_view, name="register"),

    # customer
    path("customer/dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("customer/request/", views.request_ride, name="request_ride"),
    path("customer/ride-status/<int:pk>/", views.ride_status, name="ride_status"),
    path("customer/poll/<int:request_id>/", views.poll_request_status, name="poll_request_status"),

    # driver
    path("driver/dashboard/", views.driver_dashboard, name="driver_dashboard"),
    path("driver/ride/<int:ride_id>/", views.driver_ride_detail, name="driver_ride_detail"),
    path("driver/match/<int:match_id>/accept/", views.accept_match_view, name="accept_match"),
    path("driver/match/<int:match_id>/reject/", views.reject_match_view, name="reject_match"),
]
