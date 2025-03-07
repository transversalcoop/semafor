from django.urls import reverse
from django.conf import settings
from django.templatetags.static import static
from django.utils.translation import gettext, ngettext
from django.templatetags.l10n import localize

from jinja2 import Environment

from semafor.utils import (
    link_active,
    dedication_intensity,
    yes_no,
    format_duration,
    format_currency,
    format_month,
)


def environment(**options):
    env = Environment(extensions=["jinja2.ext.i18n"], **options)
    env.install_gettext_callables(gettext=gettext, ngettext=ngettext, newstyle=True)
    env.globals.update(
        {
            "len": len,
            "dir": dir,
            "str": str,
            "url": reverse,
            "static": static,
            "yes_no": yes_no,
            "localize": localize,
            "settings": settings,
            "link_active": link_active,
            "format_duration": format_duration,
            "format_currency": format_currency,
            "format_month": format_month,
            "dedication_intensity": dedication_intensity,
        }
    )
    return env
