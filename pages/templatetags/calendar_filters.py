from django import template

register = template.Library()


@register.filter
def dict_lookup(dictionary, key):
    """Allow dictionary access in templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
