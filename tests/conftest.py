from datetime import date, timedelta

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def tag(d: date, bestellt: bool, schluss: str | None = None, **extra) -> dict:
    menues = [
        {"name": "Menü 1", "kurz": "Nudeln", "text": "Nudeln mit Tomatensoße", "preis": 3.85,
         "kennzeichnung": "A", "bestellt": bestellt},
        {"name": "Menü 2", "kurz": "Reis", "text": "Gemüsereis", "preis": 3.85, "kennzeichnung": None,
         "bestellt": False},
    ]
    t = {"datum": d.isoformat(), "feiertag": False, "zustellpause": False, "pause_grund": None,
         "bestellschluss": schluss, "menues": menues, "bestellt": menues[0] if bestellt else None}
    t.update(extra)
    return t


@pytest.fixture
def speiseplan():
    """Heute bestellt, morgen offen (Schluss morgen 08:00), übermorgen bestellt."""
    from homeassistant.util import dt as dt_util

    heute = dt_util.now().date()
    tage = {}
    for i, b in enumerate([True, False, True]):
        d = heute + timedelta(days=i)
        schluss = dt_util.start_of_local_day(d).replace(hour=8).isoformat()
        tage[d.isoformat()] = tag(d, b, schluss)
    return {"tage": tage, "einrichtung": {"name": "Testschule"}}
