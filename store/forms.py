from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import Order

User = get_user_model()


class SignUpForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("That username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("That email is already registered.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            candidate = User(
                username=cleaned.get("username", ""), email=cleaned.get("email", "")
            )
            try:
                validate_password(password, candidate)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class CheckoutForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField()
    mobile = forms.RegexField(
        regex=r"^(\+91[\s-]?)?[6-9]\d{9}$",
        max_length=15,
        error_messages={"invalid": "Enter a valid 10-digit Indian mobile number."},
    )
    address = forms.CharField(max_length=500, widget=forms.Textarea)
    payment_method = forms.ChoiceField(choices=Order.PaymentMethod.choices)


class QuantityForm(forms.Form):
    # 0 is allowed: setting a quantity of zero removes the item from the cart.
    quantity = forms.IntegerField(min_value=0, max_value=1000)
