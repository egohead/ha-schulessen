from datetime import timedelta
from unittest.mock import patch

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed, async_mock_service

from custom_components.schulessen import erinnerung
from custom_components.schulessen.const import DOMAIN

from .conftest import tag
from .test_init import DATEN


def test_schluss_zeit_formate():
    a = erinnerung.schluss_zeit({"bestellschluss": "2026-11-15T18:00:00+0100"})
    b = erinnerung.schluss_zeit({"bestellschluss": "2026-11-15T18:00:00+01:00"})
    assert a == b and a.hour == 18 - (1 - a.utcoffset().total_seconds() / 3600)
    assert erinnerung.schluss_zeit({"bestellschluss": None}) is None


def test_offene_tage_ohne_abgelaufene():
    jetzt = dt_util.now()
    morgen = jetzt.date() + timedelta(days=1)
    tage = {
        morgen.isoformat(): tag(morgen, False, (jetzt + timedelta(hours=5)).isoformat()),
        (morgen + timedelta(days=1)).isoformat(): tag(morgen + timedelta(days=1), False,
                                                      (jetzt - timedelta(hours=1)).isoformat()),
        (morgen + timedelta(days=2)).isoformat(): tag(morgen + timedelta(days=2), True, None),
    }
    assert [d for d, _ in erinnerung.offene_tage_sync(tage)] == [morgen.isoformat()]


async def test_frist_einmal_pro_tag(hass, speiseplan):
    aufrufe = async_mock_service(hass, "notify", "handy")
    entry = MockConfigEntry(domain=DOMAIN, title="Anna", unique_id="123", data=DATEN,
                            options={"erinnerung": True, "erinnerung_vorlauf": 48,
                                     "erinnerung_ziele": ["notify.handy"]})
    entry.add_to_hass(hass)
    with patch("custom_components.schulessen.api_rest.RestClient.fetch", return_value=speiseplan):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    for _ in range(3):
        with patch("custom_components.schulessen.api_rest.RestClient.fetch", return_value=speiseplan):
            async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
            await hass.async_block_till_done()
    frist = [c for c in aufrufe if "Bestellschluss" in c.data["message"]]
    assert len(frist) == 1
    assert frist[0].data["title"] == "Zu tun: Essen bestellen – Anna"
