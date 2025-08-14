from django.contrib import admin
from .models import Rating

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("ride", "driver_rating", "customer_rating", "created_at")
    search_fields = ("ride__id",)
    autocomplete_fields = ("ride",)
