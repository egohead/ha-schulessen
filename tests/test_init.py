from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.schulessen.const import DOMAIN
from custom_components.schulessen.diagnostics import async_get_config_entry_diagnostics

DATEN = {"typ": "rest", "name": "Anna", "username": "4711", "password": "geheim",
         "mandant": "108106-gfb-leipzig", "url": "https://proxy.mms-rcs.de", "dashboard": False}


async def _einrichten(hass, speiseplan, options=None):
    entry = MockConfigEntry(domain=DOMAIN, title="Anna", unique_id="123", data=DATEN, options=options or {})
    entry.add_to_hass(hass)
    with patch("custom_components.schulessen.api_rest.RestClient.fetch", return_value=speiseplan):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_entitaeten(hass, speiseplan):
    await _einrichten(hass, speiseplan)
    assert hass.states.get("sensor.anna_essen_heute").state == "Menü 1"
    assert hass.states.get("sensor.anna_essen_morgen").state == "nicht bestellt"
    assert hass.states.get("binary_sensor.anna_essen_offen").state == "on"
    schluss = hass.states.get("sensor.anna_nachster_bestellschluss")
    assert schluss is not None and schluss.state not in ("unknown", "unavailable")
    stand = hass.states.get("sensor.anna_essen_stand")
    assert stand.attributes["schulessen_karte"] is True
    assert len(stand.attributes["tage"]) == 3
    ids = {e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), next(iter(
        hass.config_entries.async_entries(DOMAIN))).entry_id)}
    assert "calendar.anna_speiseplan" in ids


async def test_diagnose_ohne_zugangsdaten(hass, speiseplan):
    entry = await _einrichten(hass, speiseplan)
    diag = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diag)
    assert "geheim" not in text and "4711" not in text
    assert diag["abruf"]["live"] is True
    assert len(diag["tage"]) == 3


async def test_entladen(hass, speiseplan):
    entry = await _einrichten(hass, speiseplan)
    assert await hass.config_entries.async_unload(entry.entry_id)
