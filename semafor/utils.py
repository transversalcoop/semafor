def months_range(date_start, date_end):
    ym_start = 12 * date_start.year + date_start.month - 1
    ym_end = 12 * date_end.year + date_end.month
    for ym in range(ym_start, ym_end):
        y, m = divmod(ym, 12)
        yield y, m + 1


def dedication_intensity(dedication, multiplier):
    dedication = dedication / multiplier
    if dedication <= 20:
        return "dedication-green"
    elif dedication <= 40:
        return "dedication-blue"
    elif dedication <= 60:
        return "dedication-yellow"
    elif dedication <= 80:
        return "dedication-orange"
    elif dedication <= 100:
        return "dedication-red"
    return "dedication-black"
