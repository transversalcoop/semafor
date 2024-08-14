from django.urls import reverse
from django.conf import settings
from django.templatetags.static import static

from jinja2 import Environment

from semafor.utils import dedication_intensity


def environment(**options):
    env = Environment(extensions=[], **options)
    env.globals.update(
        {
            "len": len,
            "url": reverse,
            "static": static,
            "settings": settings,
            "dedication_intensity": dedication_intensity,
        }
    )
    return env
