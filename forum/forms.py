import re
from datetime import timedelta

from django import forms
from django.utils import timezone

from pages.geo import STATE_CENTERS
from pages.models import US_STATES

from .models import Category, ForumProfile, Post, Status, TeamListing, Thread, is_moderator

THREADS_PER_DAY = 5
POSTS_PER_DAY = 30
LINK_RE = re.compile(r'https?://|www\.', re.IGNORECASE)
# What each team type must name in the listing's company field.
TEAM_ORGANIZATION = {'professional': 'company', 'collegiate': 'college'}
CITY_RE = re.compile(r"^[^\W\d_][^\W\d_ .'’-]*(?:[ .'’-]+[^\W\d_]+)*\.?$")

# (name, abbreviation) for the profile form's state suggestions, A-Z.
STATE_OPTIONS = sorted((name.title(), abbr) for name, abbr in US_STATES.items())
_STATE_LOOKUP = {**US_STATES, **{abbr.lower(): abbr for abbr in US_STATES.values()}}
_ABBR_TO_NAME = {abbr: name for name, abbr in STATE_OPTIONS}
# The site's own account isn't from any one state.
STATE_OPTIONAL_EMAILS = {'info@minerescuecenter.com'}


class HoneypotMixin(forms.Form):
    # Real people leave this empty; bots tend to fill every field. Hidden
    # off-screen in the template, same as the feedback form.
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}),
    )

    @property
    def is_spam(self):
        return bool(self.cleaned_data.get('website'))


class SignInForm(HoneypotMixin):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'placeholder': 'you@example.com', 'autofocus': True}))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = ForumProfile
        fields = ['display_name', 'role', 'district', 'state', 'team', 'email_on_reply']
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'First and last name'}),
            # The template adds a suggestion list that filters as they type.
            'state': forms.TextInput(attrs={
                'placeholder': 'Start typing your state', 'autocomplete': 'off',
                'role': 'combobox', 'aria-autocomplete': 'list', 'aria-controls': 'state-suggest', 'aria-expanded': 'false',
            }),
            'team': forms.TextInput(attrs={'placeholder': 'Your mine or rescue team'}),
        }
        labels = {
            'display_name': 'Display name',
            'district': 'Coal or MNM',
            'team': 'Team or company',
            'email_on_reply': 'Email me when someone replies to a thread I follow',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['display_name'].required = True
        self.state_optional = self.instance.user.email.lower() in STATE_OPTIONAL_EMAILS
        if not self.state_optional:
            self.fields['state'].required = True
            self.fields['state'].error_messages['required'] = "Please enter your state."
        # Stored as the abbreviation; shown spelled out like the suggestions.
        if not self.is_bound and self.instance.state in _ABBR_TO_NAME:
            self.initial['state'] = _ABBR_TO_NAME[self.instance.state]

    def clean_state(self):
        typed = ' '.join(self.cleaned_data['state'].split()).lower()
        if not typed:
            return ''
        abbr = _STATE_LOOKUP.get(typed)
        if abbr is None:
            raise forms.ValidationError("Please pick your state from the list.")
        return abbr

    def clean_display_name(self):
        name = ' '.join(self.cleaned_data['display_name'].split())
        if len(name) < 2:
            raise forms.ValidationError("Please use at least 2 characters.")
        taken = ForumProfile.objects.filter(display_name__iexact=name).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("Someone already uses that name. Try adding an initial.")
        return name


class TeamListingForm(forms.ModelForm):
    state = forms.ChoiceField(choices=[('', 'Choose a state')] + [
        # Hawaii has no mine rescue teams and isn't drawn on the team map.
        (abbr, name) for name, abbr in STATE_OPTIONS if abbr in STATE_CENTERS and abbr != 'HI'
    ])
    consent = forms.BooleanField(
        label="I'm part of this team. It's okay to show these team details on the public map and share the team's contact information with signed-in members.",
        error_messages={'required': "Please confirm before adding your team to the map."},
    )

    class Meta:
        model = TeamListing
        fields = ['name', 'team_type', 'company', 'sector', 'city', 'state', 'contact_email', 'contact_phone']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Blue Team'}),
            'company': forms.TextInput(attrs={'placeholder': 'Your company or college'}),
            'city': forms.TextInput(attrs={'placeholder': 'Where your team is based'}),
            'contact_email': forms.EmailInput(attrs={'placeholder': 'team@example.com'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': '(304) 555-0100', 'inputmode': 'tel'}),
        }
        error_messages = {
            'team_type': {'required': "Please choose a team type."},
            'contact_email': {'invalid': "Please enter a valid email address."},
        }

    def _clean_text(self, field):
        value = ' '.join(self.cleaned_data[field].split())
        if LINK_RE.search(value):
            raise forms.ValidationError("Please leave out links.")
        return value

    def clean_name(self):
        name = self._clean_text('name')
        if len(name) < 2:
            raise forms.ValidationError("Please enter your team's name.")
        return name

    def clean_company(self):
        return self._clean_text('company')

    def clean_contact_phone(self):
        typed = self.cleaned_data['contact_phone'].strip()
        if not typed:
            return ''
        digits = re.sub(r'\D', '', typed)
        if len(digits) == 11 and digits[0] == '1':
            digits = digits[1:]
        if len(digits) != 10:
            raise forms.ValidationError("Please enter a 10-digit phone number.")
        return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'

    def clean_city(self):
        city = self._clean_text('city')
        if not CITY_RE.match(city):
            raise forms.ValidationError("Please enter just the town or city name.")
        return city

    def clean(self):
        cleaned = super().clean()
        team_type = cleaned.get('team_type')
        if team_type == 'volunteer':
            # The field is hidden for volunteer teams, so ignore anything left in it.
            self.errors.pop('company', None)
            cleaned['company'] = ''
        elif team_type in TEAM_ORGANIZATION and 'company' not in self.errors and len(cleaned.get('company', '')) < 2:
            self.add_error('company', f"Please enter your team's {TEAM_ORGANIZATION[team_type]}.")
        name, state = cleaned.get('name'), cleaned.get('state')
        if name and state:
            taken = TeamListing.objects.filter(
                name__iexact=name, state=state, status__in=[Status.PENDING, Status.VISIBLE],
            ).exclude(pk=self.instance.pk)
            if taken.exists():
                self.add_error('name', "That team is already listed in this state.")
        return cleaned


class _PostingLimits:
    """Shared checks on what a member may post right now."""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def check_body(self, body):
        body = body.strip()
        if len(body) < 2:
            raise forms.ValidationError("Please write a little more.")
        profile = self.user.forum_profile
        new_account = self.user.date_joined > timezone.now() - timedelta(days=1)
        if new_account and not profile.posts_freely and LINK_RE.search(body):
            raise forms.ValidationError(
                "New members can post links after their first day. Please "
                "remove the link for now, or describe where to find it."
            )
        return body

    def check_rate(self, new_thread=False):
        if is_moderator(self.user):
            return
        since = timezone.now() - timedelta(days=1)
        if new_thread and Thread.objects.filter(author=self.user, created_at__gte=since).count() >= THREADS_PER_DAY:
            raise forms.ValidationError(f"You can start up to {THREADS_PER_DAY} threads a day. Please try again tomorrow.")
        if Post.objects.filter(author=self.user, created_at__gte=since).count() >= POSTS_PER_DAY:
            raise forms.ValidationError(f"You can post up to {POSTS_PER_DAY} times a day. Please try again tomorrow.")


class ThreadForm(_PostingLimits, HoneypotMixin):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), empty_label=None)
    title = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'placeholder': 'Ask a question or name the topic'}))
    body = forms.CharField(max_length=10000, widget=forms.Textarea(attrs={'rows': 9}))

    def clean_title(self):
        title = ' '.join(self.cleaned_data['title'].split())
        if len(title) < 5:
            raise forms.ValidationError("Please use a more descriptive title.")
        return title

    def clean_body(self):
        return self.check_body(self.cleaned_data['body'])

    def clean(self):
        cleaned = super().clean()
        self.check_rate(new_thread=True)
        return cleaned


class ReplyForm(_PostingLimits, HoneypotMixin):
    body = forms.CharField(max_length=10000, widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'Write a reply…'}))

    def clean_body(self):
        return self.check_body(self.cleaned_data['body'])

    def clean(self):
        cleaned = super().clean()
        self.check_rate()
        return cleaned


class EditPostForm(_PostingLimits, forms.Form):
    body = forms.CharField(max_length=10000, widget=forms.Textarea(attrs={'rows': 9}))

    def clean_body(self):
        return self.check_body(self.cleaned_data['body'])


class ReportForm(forms.Form):
    reason = forms.CharField(max_length=300, widget=forms.TextInput(attrs={'placeholder': 'What’s wrong with this post?'}))
