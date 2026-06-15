from django import forms


class FeedbackForm(forms.Form):
    """Short feedback form. The visitor only has to write a message; name and
    email are optional so we can follow up if they want a reply."""

    name = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Your name'}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    message = forms.CharField(
        max_length=5000,
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': "What's working, what could work better, and what "
                           "you'd like to see added…",
        }),
    )
    # Honeypot: real people leave this empty; bots tend to fill every field.
    # Hidden off-screen in the template and ignored on submit when filled.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}),
    )

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if len(message) < 3:
            raise forms.ValidationError("Please add a little more detail.")
        return message
