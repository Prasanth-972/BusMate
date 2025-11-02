from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User
from .models import BusRoute, BusPassApplication, UserProfile, BoardingLocation
from django.core.files.images import get_image_dimensions
from django.core.exceptions import ValidationError

class UserRegistrationForm(UserCreationForm):
    photo = forms.ImageField(required=False, label='Profile Photo', 
                           help_text='Upload a square photo (max 5MB, JPG/PNG only)')
    
    USER_TYPE_CHOICES = (
        ('STUDENT', 'Student'),
        ('FACULTY', 'Faculty'),
    )
    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, label='I am a')
    DEPARTMENT_CHOICES = (
        ('Polytechnic', 'Polytechnic'),
        ('Btech cs', 'Btech cs'),
        ('Btech electrical', 'Btech electrical'),
        ('Btech mechanical', 'Btech mechanical'),
        ('BBA', 'BBA'),
        ('MBA', 'MBA'),
        ('BCA', 'BCA'),
        ('MCA', 'MCA'),
    )
    department = forms.ChoiceField(choices=DEPARTMENT_CHOICES, required=False, label='Department')
    mobile_number = forms.CharField(max_length=15, required=False, label='Mobile Number')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'mobile_number', 'password1', 'password2', 'user_type', 'department', 'photo']
        widgets = {
            'photo': forms.FileInput(attrs={'accept': 'image/*', 'capture': 'camera'})
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Save extended profile fields
            profile = UserProfile.objects.create(
                user=user,
                is_admin=False,
                user_type=self.cleaned_data.get('user_type') or 'STUDENT',
                department=self.cleaned_data.get('department') or '',
                mobile_number=self.cleaned_data.get('mobile_number') or ''
            )
            
            # Handle photo upload
            photo = self.cleaned_data.get('photo')
            if photo:
                # Validate image
                try:
                    w, h = get_image_dimensions(photo)
                    # Check file size (5MB max)
                    if photo.size > 5*1024*1024:
                        raise ValidationError("Image file too large (max 5MB)")
                    # Check file type
                    if not photo.content_type in ['image/jpeg', 'image/png']:
                        raise ValidationError("Only JPG and PNG images are allowed")
                    
                    # Save the photo
                    profile.photo = photo
                    profile.save()
                except Exception as e:
                    # If there's any error with the image, we'll just skip saving it
                    # The form will still be valid but the photo won't be saved
                    pass

        return user

class BusRouteForm(forms.ModelForm):
    boarding_locations = forms.CharField(
        required=False,
        label='Boarding Locations',
        help_text='Enter one location per line or separate with commas',
        widget=forms.Textarea(attrs={'rows': 3})
    )
    class Meta:
        model = BusRoute
        fields = ['name', 'description', 'fee', 'max_seats']

class BusPassApplicationForm(forms.ModelForm):
    # Boarding location becomes a dropdown based on the route
    boarding_location = forms.ChoiceField(choices=[], label='Boarding Location')

    def __init__(self, *args, **kwargs):
        route = kwargs.pop('route', None)
        super().__init__(*args, **kwargs)
        if route is not None:
            locs = BoardingLocation.objects.filter(route=route).order_by('position', 'name')
            choices = [(bl.name, bl.name) for bl in locs]
            # Fallback: if no locations defined, allow free text via a text input
            if choices:
                self.fields['boarding_location'].choices = choices
            else:
                # Replace with CharField if none available
                self.fields['boarding_location'] = forms.CharField(label='Boarding Location')

    class Meta:
        model = BusPassApplication
        fields = ['boarding_location']


class UserProfileEditForm(forms.ModelForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    photo = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}),
                            help_text='Upload a square photo (max 5MB, JPG/PNG only)')
    
    class Meta:
        model = UserProfile
        fields = ['email', 'first_name', 'last_name', 'mobile_number', 'department', 'preferred_boarding_location', 'photo']
    
    def __init__(self, *args, **kwargs):
        super(UserProfileEditForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
    
    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            try:
                # Check file size (5MB max)
                if photo.size > 5 * 1024 * 1024:
                    raise ValidationError("Image file too large (max 5MB)")
                # Check file type
                if not photo.content_type in ['image/jpeg', 'image/png']:
                    raise ValidationError("Only JPG and PNG images are allowed")
            except AttributeError:
                # Handle case when file is not an image
                raise ValidationError("Invalid image file")
        return photo
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        
        # Update user fields
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            profile.save()
        
        return profile