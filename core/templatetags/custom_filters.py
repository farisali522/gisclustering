from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Getting value from dictionary by key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def append(value, arg):
    """Concatenating strings."""
    return f"{value}{arg}"

@register.filter
def replace(value, arg):
    """Replacing text. arg format: 'target:replacement'"""
    if ':' not in arg:
        return value
    target, replacement = arg.split(':')
    return value.replace(target, replacement)
