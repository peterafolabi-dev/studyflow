from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Look up `key` in a dict from within a template (mapping[key] isn't
    directly usable in Django template syntax)."""
    if not mapping:
        return None
    return mapping.get(key)
