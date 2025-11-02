import os
from django.db import models
from django.contrib.auth.models import User

def user_profile_photo_path(instance, filename):    
    # File will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'user_{0}/profile_photos/{1}'.format(instance.user.id, filename)

# Extends the User model to store college-specific info
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_admin = models.BooleanField(default=False)
    USER_TYPE_CHOICES = (
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty'),
    )
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='STUDENT')
    department = models.CharField(max_length=100, blank=True)
    mobile_number = models.CharField(max_length=15, blank=True)
    preferred_boarding_location = models.CharField(max_length=200, blank=True)
    photo = models.ImageField(upload_to=user_profile_photo_path, null=True, blank=True, verbose_name='Profile Photo')
    # Add other fields like 'college_id', 'contact_number' if needed
    
    def __str__(self):
        return self.user.username + (" (Admin)" if self.is_admin else "")

class BusRoute(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    fee = models.DecimalField(max_digits=8, decimal_places=2)
    max_seats = models.IntegerField(default=50) # Maximum capacity
    
    def __str__(self):
        return f"{self.name} (Fee: ₹{self.fee})"

class BoardingLocation(models.Model):
    route = models.ForeignKey(BusRoute, on_delete=models.CASCADE, related_name='boarding_locations')
    name = models.CharField(max_length=200)
    position = models.PositiveIntegerField(default=1)  # 1-based order along the route

    class Meta:
        unique_together = ('route', 'name')

    def __str__(self):
        return f"{self.name} ({self.route.name})"

class BusPassApplication(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('PAID', 'Fee Paid'),
        ('ALLOCATED', 'Seat Allocated'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled by User'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    route = models.ForeignKey(BusRoute, on_delete=models.PROTECT) # Prevents route deletion if passes exist
    boarding_location = models.CharField(max_length=200)
    application_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    seat_number = models.CharField(max_length=10, blank=True, null=True) # Allocated seat
    paid_fee = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    
    def __str__(self):
        return f"Pass for {self.user.username} on Route {self.route.name}"

class SupportMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SupportMessage({self.user.username}, {self.created_at:%Y-%m-%d %H:%M})"