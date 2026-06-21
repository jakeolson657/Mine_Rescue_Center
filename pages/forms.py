from django import forms
from django.template.defaultfilters import filesizeformat


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


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """A FileField that keeps every selected file. Django's plain FileField only
    cleans the last file in a multi-select <input>; this returns the full list.
    (The pattern recommended in the Django file-uploads docs.)"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)]


class ProblemSubmissionForm(forms.Form):
    """Lets a visitor send in a competition's problems that aren't in the
    archive yet. The submission is emailed (with the files attached) to the
    team — nothing is stored on the site."""

    MAX_FILES = 15
    MAX_FILE_SIZE = 15 * 1024 * 1024        # 15 MB per file
    MAX_TOTAL_SIZE = 25 * 1024 * 1024       # 25 MB across all files

    competition_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Loveland, Colorado'}),
    )
    year = forms.IntegerField(
        required=False, min_value=1900, max_value=2100,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 2024'}),
    )
    location = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'City, State'}),
    )
    context = forms.CharField(
        max_length=5000,
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': "Which problem(s) are these? Include the discipline "
                           "(coal / nonmetal), day, and anything else that helps "
                           "us index them correctly.",
        }),
    )
    files = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            'accept': '.pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,'
                      '.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip',
        }),
    )
    name = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Your name'}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    # Honeypot: real people leave this empty; bots tend to fill every field.
    # Hidden off-screen in the template and ignored on submit when filled.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}),
    )

    def clean_context(self):
        context = self.cleaned_data['context'].strip()
        if len(context) < 3:
            raise forms.ValidationError("Please add a little more detail.")
        return context

    def clean_files(self):
        files = self.cleaned_data['files']
        if len(files) > self.MAX_FILES:
            raise forms.ValidationError(
                f"Please attach at most {self.MAX_FILES} files at a time."
            )
        total = 0
        for upload in files:
            if upload.size > self.MAX_FILE_SIZE:
                raise forms.ValidationError(
                    f"“{upload.name}” is {filesizeformat(upload.size)}; the limit "
                    f"is {filesizeformat(self.MAX_FILE_SIZE)} per file."
                )
            total += upload.size
        if total > self.MAX_TOTAL_SIZE:
            raise forms.ValidationError(
                f"Those files total {filesizeformat(total)}; the limit is "
                f"{filesizeformat(self.MAX_TOTAL_SIZE)}. For anything larger, "
                f"email the files to info@minerescuecenter.com."
            )
        return files
