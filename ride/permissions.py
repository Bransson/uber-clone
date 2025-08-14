from rest_framework.permissions import BasePermission

class IsAuthenticatedAndCustomer(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and hasattr(u, "customer_profile"))

class IsAuthenticatedAndDriver(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and hasattr(u, "driver_profile"))
