from django import forms
from django.contrib.auth import authenticate
from profiles.models import CustomUser, Customer, Driver

ROLE_CHOICES = (("CUSTOMER", "Customer"), ("DRIVER", "Driver"))

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"class":"form-control", "placeholder":"Username or email"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class":"form-control", "placeholder":"Password"}))

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class":"form-control"}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs={"class":"form-select"}))

    class Meta:
        model = CustomUser
        fields = ("username", "email", "phone_number", "first_name", "last_name", "gender", "date_of_birth")

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("password")
        user.set_password(pw)
        if commit:
            user.save()
            role = self.cleaned_data.get("role")
            if role == "CUSTOMER":
                Customer.objects.get_or_create(user=user)
            else:
                # Create Driver profile (vehicle can be added later from admin)
                Driver.objects.get_or_create(user=user)
        return user

class RideRequestForm(forms.Form):
    pickup_address = forms.CharField(max_length=256, widget=forms.TextInput(attrs={"class":"form-control", "placeholder":"Pickup address"}))
    dropoff_address = forms.CharField(max_length=256, widget=forms.TextInput(attrs={"class":"form-control", "placeholder":"Dropoff address"}))
    pickup_lat = forms.FloatField(widget=forms.HiddenInput())
    pickup_lng = forms.FloatField(widget=forms.HiddenInput())
    dropoff_lat = forms.FloatField(widget=forms.HiddenInput())
    dropoff_lng = forms.FloatField(widget=forms.HiddenInput())
    payment_method = forms.ChoiceField(choices=[("CASH","Cash"),("INAPP","In-App")], widget=forms.Select(attrs={"class":"form-select"}))
    city = forms.CharField(max_length=64, initial="Lagos", widget=forms.HiddenInput())
    vehicle_type = forms.CharField(max_length=64, initial="Standard", widget=forms.HiddenInput())
