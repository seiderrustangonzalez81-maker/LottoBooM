from django import template
register = template.Library()

@register.filter
def format_timedelta(seconds):
    if not seconds or seconds <= 0:
        return "00:00:00"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"