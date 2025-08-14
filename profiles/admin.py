from django.contrib import admin
from .models import CustomUser, Driver, Customer


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "first_name", "last_name", "phone_number", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name", "phone_number")
    list_filter = ("is_active", "is_staff", "gender")
    ordering = ("username",)
    autocomplete_fields = []  # can be left empty unless you reference others


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("user", "vehicle", "is_available", "current_lat", "current_lng")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "vehicle")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user", "favourite_locations", "home_location", "work_location")
