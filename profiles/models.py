from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import PermissionsMixin, AbstractBaseUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator


GENDER = (("MALE", "Male"), ("FEMALE", "Female"))


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, username, phone_number, email, password, **extra_fields):
        if not username:
            raise ValueError("The given username must be set")
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(
            username=username,
            phone_number=phone_number,
            email=email,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, phone_number, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, phone_number, email, password, **extra_fields)

    def create_superuser(self, username, phone_number, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(username, phone_number, email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    username = models.CharField(_("username"), max_length=150, unique=True)
    email = models.EmailField(_("email address"), unique=True)
    phone_number = models.CharField(_("phone number"), max_length=20)
    first_name = models.CharField(_("first name"), max_length=30)
    last_name = models.CharField(_("last name"), max_length=30)
    gender = models.CharField(_("gender"), choices=GENDER, max_length=6)
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)

    profile_picture = models.ImageField(
        _("profile picture"),
        default="default_image.png",
        upload_to="profile_pictures/",
        blank=True
    )

    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    is_staff = models.BooleanField(_("staff status"), default=False)
    is_active = models.BooleanField(_("active"), default=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["first_name", "last_name", "phone_number", "email"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        indexes = [
            models.Index(fields=["username"]),
            models.Index(fields=["email"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self):
        return self.username

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk:
            prev = self.__class__.objects.filter(pk=self.pk).first()
            if prev and not self.profile_picture:
                self.profile_picture = prev.profile_picture or "default_image.png"
        else:
            if not self.profile_picture:
                self.profile_picture = "default_image.png"
        super().save(*args, **kwargs)


class Driver(models.Model):
    user = models.OneToOneField("profiles.CustomUser", on_delete=models.CASCADE, related_name="driver_profile")
    vehicle = models.ForeignKey("vehicle.Vehicle", on_delete=models.SET_NULL, blank=True, null=True, related_name="drivers")

    # live location for matching
    current_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    current_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )

    is_available = models.BooleanField(default=True, db_index=True)
    total_rides = models.PositiveIntegerField(default=0)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        indexes = [models.Index(fields=["is_available"])]

    def __str__(self):
        return f"Driver {self.user.username}"


class Customer(models.Model):
    user = models.OneToOneField("profiles.CustomUser", on_delete=models.CASCADE, related_name="customer_profile")
    favourite_locations = models.ManyToManyField("location.Location", blank=True, related_name="favourited_by")
    home_location = models.ForeignKey("location.Location", on_delete=models.SET_NULL, blank=True, null=True, related_name="home_customers")
    work_location = models.ForeignKey("location.Location", on_delete=models.SET_NULL, blank=True, null=True, related_name="work_customers")

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"

    def __str__(self):
        return f"Customer {self.user.username}"
