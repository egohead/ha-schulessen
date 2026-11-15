from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.schulessen.api_rest import RestAuthError
from custom_components.schulessen.const import DOMAIN

KONTO = {"name": "Anna", "username": "4711", "password": "geheim", "mandant": "108106-gfb-leipzig",
         "url": "https://proxy.mms-rcs.de", "portal_url": "https://bestellung-gfb-catering.de",
         "dashboard": False}


async def _bis_konto(hass):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["type"] is FlowResultType.FORM and r["step_id"] == "user"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"vorlage": "gfb_leipzig"})
    assert r["step_id"] == "konto"
    return r


async def test_vorlage_und_anlage(hass):
    r = await _bis_konto(hass)
    with patch("custom_components.schulessen.config_flow._pruefen", return_value="123"), \
         patch("custom_components.schulessen.async_setup_entry", return_value=True):
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {**KONTO, "bestaetigung": True})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["title"] == "Anna"
    assert r["data"]["typ"] == "rest"
    assert r["data"]["mandant"] == "108106-gfb-leipzig"
    assert r["result"].unique_id == "123"


async def test_bestaetigung_fehlt_behaelt_eingaben(hass):
    r = await _bis_konto(hass)
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {**KONTO, "bestaetigung": False})
    assert r["type"] is FlowResultType.FORM
    assert r["errors"] == {"bestaetigung": "bestaetigung_fehlt"}
    werte = {str(k): k.description.get("suggested_value") for k in r["data_schema"].schema if k.description}
    assert werte["username"] == "4711"


async def test_unsichere_adresse(hass):
    r = await _bis_konto(hass)
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {**KONTO, "url": "http://proxy.mms-rcs.de", "bestaetigung": True})
    assert r["errors"] == {"url": "insecure_url_rest"}


async def test_falsches_passwort(hass):
    r = await _bis_konto(hass)
    with patch("custom_components.schulessen.config_flow._pruefen", side_effect=RestAuthError("nein")):
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {**KONTO, "bestaetigung": True})
    assert r["errors"] == {"base": "invalid_auth"}
