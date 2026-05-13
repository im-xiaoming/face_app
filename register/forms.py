from django import forms
from users.models import UserModel
from django.core.exceptions import ValidationError


class UserForm(forms.ModelForm):
    class Meta:
        model = UserModel
        fields = ['name', 'email', 'dob']

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Nguyễn Văn A',
                'id': 'name'
            }),

            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'example@email.com',
                'id': 'email'
            }),

            'dob': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
                'id': 'dob'
            }),
        }
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email is required.")
        
        if UserModel.objects.filter(email=email).exists():
            raise ValidationError("Email is exists.")
        
        return email
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Name is required.")
        
        return name
        
    def clean_dob(self):
        dob = self.cleaned_data.get('dob')
        if not dob:
            raise ValidationError("DOB is required.")
        
        return dob