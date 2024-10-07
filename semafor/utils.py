from django.utils.translation import gettext_lazy as _


def months_range(date_start, date_end):
    ym_start = 12 * date_start.year + date_start.month - 1
    ym_end = 12 * date_end.year + date_end.month
    for ym in range(ym_start, ym_end):
        y, m = divmod(ym, 12)
        yield y, m + 1


def dedication_intensity(dedication, total_dedication):
    if not dedication:
        return ""
    if not total_dedication:
        return "dedication-error"

    intensity = dedication / total_dedication
    if intensity <= 0.20:
        return "dedication-green"
    elif intensity <= 0.40:
        return "dedication-blue"
    elif intensity <= 0.60:
        return "dedication-yellow"
    elif intensity <= 0.80:
        return "dedication-orange"
    elif intensity <= 1:
        return "dedication-red"
    return "dedication-black"


def link_active(request, urlpath, exact=False):
    if exact:
        return request.path == urlpath
    return str(request.path).startswith(urlpath)


def yes_no(b):
    if b:
        return _("Sí")
    return _("No")
