"""Password-free sign-in: we email a link, and following it signs you in.

The link carries a signed token holding the email address and the account's
last-login time. Signing in updates last_login, so each link works once, and
it expires after LINK_MAX_AGE regardless.
"""
from django.contrib.auth import get_user_model
from django.core import signing

SALT = 'forum.signin'
LINK_MAX_AGE = 60 * 30  # seconds


def _user_for(email):
    return get_user_model().objects.filter(email__iexact=email).order_by('pk').first()


def _login_stamp(user):
    return user.last_login.timestamp() if user and user.last_login else None


def make_token(email, next_url=''):
    email = email.strip().lower()
    return signing.dumps(
        {'e': email, 'l': _login_stamp(_user_for(email)), 'n': next_url},
        salt=SALT, compress=True,
    )


def read_token(token):
    """(email, next_url) for a valid, unused token, else None."""
    try:
        data = signing.loads(token, salt=SALT, max_age=LINK_MAX_AGE)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    email = data.get('e', '')
    if not email or data.get('l') != _login_stamp(_user_for(email)):
        return None
    return email, data.get('n', '')


def get_or_create_user(email):
    user = _user_for(email)
    if user:
        return user
    User = get_user_model()
    username = email[:150]
    n = 1
    while User.objects.filter(username=username).exists():
        n += 1
        suffix = f'+{n}'
        username = email[:150 - len(suffix)] + suffix
    user = User(username=username, email=email)
    user.set_unusable_password()
    user.save()
    return user
