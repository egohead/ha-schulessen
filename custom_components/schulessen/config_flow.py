from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntryDisabler, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector, EntitySelectorConfig, NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode, TextSelector,
    TextSelectorConfig, TextSelectorType, TimeSelector,
)

from . import client_fuer
from .api_rest import RestAuthError
from .api_wamp import WampAuthError
from .const import (
    CONF_BESTAETIGUNG, CONF_DASHBOARD, CONF_ERINNERUNG, CONF_ERINNERUNG_TAGE, CONF_ERINNERUNG_ZEIT,
    CONF_ERINNERUNG_ZIELE, CONF_FERIENKALENDER, CONF_MANDANT, CONF_NAME, CONF_PORTAL, CONF_REALM,
    ALTE_DOMAINS, CONF_TYP, CONF_VORLAGE, DASHBOARD_ANGELEGT, DOMAIN, STANDARD_TAGE, STANDARD_ZEIT, TYP_REST, TYP_WAMP,
    VORLAGEN,
)

_LOGGER = logging.getLogger(__name__)
BEDINGUNGEN = "https://github.com/egohead/ha-schulessen/blob/main/NUTZUNGSBEDINGUNGEN.md"
PASSWORT = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


async def _pruefen(hass, data: dict) -> str:
    """Login testen, eindeutige Kennung zurückgeben."""
    client = client_fuer(hass, data)
    async with asyncio.timeout(45):
        if data[CONF_TYP] == TYP_REST:
            kunde = await client.login()
            return str(kunde["bestellerId"])
        await client.test()
        return f"{data[CONF_REALM]}_{data[CONF_USERNAME]}"


class SpeiseplanFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._vorlage: dict = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SpeiseplanOptionen()

    async def async_step_import(self, import_data: dict):
        """Eintrag einer früheren Einzel-Integration übernehmen."""
        await self.async_set_unique_id(import_data["unique_id"])
        self._abort_if_unique_id_configured()
        daten = {**import_data["data"], DASHBOARD_ANGELEGT: True}
        if alt_id := import_data.get("entry_id"):
            # alten Eintrag deaktivieren, damit Erinnerungen nicht doppelt kommen
            await self.hass.config_entries.async_set_disabled_by(alt_id, ConfigEntryDisabler.USER)
        return self.async_create_entry(title=import_data["titel"], data=daten,
                                       options=import_data.get("options") or {})

    def _alte_eintraege(self) -> list:
        vorhanden = {e.unique_id for e in self.hass.config_entries.async_entries(DOMAIN)}
        return [(alt, typ) for dom, typ in ALTE_DOMAINS.items()
                for alt in self.hass.config_entries.async_entries(dom) if alt.unique_id not in vorhanden]

    async def async_step_user(self, user_input=None):
        """Einstieg: frühere Einträge übernehmen oder neues Portal einrichten."""
        if self._alte_eintraege():
            return self.async_show_menu(step_id="user", menu_options=["uebernehmen", "vorlage"])
        return await self.async_step_vorlage()

    async def async_step_uebernehmen(self, user_input=None):
        """Einträge der früheren Einzel-Integrationen samt Zugangsdaten übernehmen."""
        namen = []
        for alt, typ in self._alte_eintraege():
            await self.hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT},
                data={"titel": alt.title, "unique_id": alt.unique_id, "entry_id": alt.entry_id,
                      "data": {**alt.data, CONF_TYP: typ}, "options": dict(alt.options)})
            namen.append(alt.title)
        return self.async_abort(reason="uebernommen", description_placeholders={"namen": ", ".join(namen)})

    async def async_step_vorlage(self, user_input=None):
        """Schritt 1: Bestellportal wählen."""
        if user_input is not None:
            self._vorlage = dict(VORLAGEN[user_input[CONF_VORLAGE]])
            return await self.async_step_konto()
        optionen = [SelectOptionDict(value=k, label=v["titel"]) for k, v in VORLAGEN.items()]
        schema = vol.Schema({vol.Required(CONF_VORLAGE, default=next(iter(VORLAGEN))): SelectSelector(
            SelectSelectorConfig(options=optionen, mode=SelectSelectorMode.LIST))})
        return self.async_show_form(step_id="vorlage", data_schema=schema)

    async def async_step_konto(self, user_input=None):
        """Schritt 2: Name des Kindes, Zugangsdaten, Portal-Angaben."""
        typ = self._vorlage.get(CONF_TYP, TYP_WAMP)
        schema_https = "https://" if typ == TYP_REST else "wss://"
        errors = {}
        if user_input is not None:
            daten = {**user_input, CONF_TYP: typ}
            if not daten.get(CONF_BESTAETIGUNG):
                errors[CONF_BESTAETIGUNG] = "bestaetigung_fehlt"
            elif daten.get(CONF_PORTAL) and not daten[CONF_PORTAL].lower().startswith("https://"):
                errors[CONF_PORTAL] = "portal_unsicher"
            elif not daten[CONF_URL].lower().startswith(schema_https):
                errors[CONF_URL] = "insecure_url_rest" if typ == TYP_REST else "insecure_url_wamp"
            else:
                try:
                    kennung = await _pruefen(self.hass, daten)
                except (WampAuthError, RestAuthError):
                    errors["base"] = "invalid_auth"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Login-Test fehlgeschlagen")
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(kennung)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=daten[CONF_NAME], data=daten)
        felder = {
            vol.Required(CONF_NAME, default="Kind"): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): PASSWORT,
        }
        if typ == TYP_REST:
            felder[vol.Required(CONF_MANDANT)] = str
        else:
            felder[vol.Required(CONF_REALM)] = str
        felder.update({
            vol.Required(CONF_URL): str,
            vol.Optional(CONF_PORTAL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Required(CONF_DASHBOARD, default=True): bool,
            vol.Required(CONF_BESTAETIGUNG, default=False): bool,
        })
        vorschlag = {k: v for k, v in self._vorlage.items() if k not in ("titel", CONF_TYP)}
        if user_input is not None:
            vorschlag = {k: v for k, v in user_input.items() if k != CONF_BESTAETIGUNG}
        schema = self.add_suggested_values_to_schema(vol.Schema(felder), vorschlag)
        return self.async_show_form(step_id="konto", data_schema=schema, errors=errors,
                                    description_placeholders={"portal": self._vorlage.get("titel", ""),
                                                              "bedingungen": BEDINGUNGEN})

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                kennung = await _pruefen(self.hass, data)
            except (WampAuthError, RestAuthError):
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Login-Test fehlgeschlagen")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(kennung)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(step_id="reauth_confirm",
                                    data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORT}),
                                    errors=errors)


class SpeiseplanOptionen(OptionsFlow):
    async def async_step_init(self, user_input=None):
        e = self.config_entry
        errors = {}
        if user_input is not None:
            portal = (user_input.get(CONF_PORTAL) or "").strip()
            if portal and not portal.lower().startswith("https://"):
                errors[CONF_PORTAL] = "portal_unsicher"
            elif user_input.get(CONF_ERINNERUNG) and not user_input.get(CONF_ERINNERUNG_ZIELE):
                errors[CONF_ERINNERUNG_ZIELE] = "ziele_fehlen"
            else:
                if user_input.get("dashboard_neu"):
                    self.hass.config_entries.async_update_entry(e, data={**e.data, DASHBOARD_ANGELEGT: False})
                daten = {k: v for k, v in user_input.items() if k != "dashboard_neu"}
                daten[CONF_PORTAL] = portal
                daten[CONF_ERINNERUNG_TAGE] = int(daten.get(CONF_ERINNERUNG_TAGE) or STANDARD_TAGE)
                return self.async_create_entry(data=daten)

        def akt(key, default=None):
            return e.options.get(key, e.data.get(key, default))

        dienste = sorted(k for k in self.hass.services.async_services().get("notify", {})
                         if k not in ("send_message", "persistent_notification"))
        ziel_optionen = [SelectOptionDict(value=f"notify.{d}", label=f"notify.{d}") for d in dienste]
        schema = vol.Schema({
            vol.Optional(CONF_PORTAL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Required(CONF_DASHBOARD): bool,
            vol.Required("dashboard_neu", default=False): bool,
            vol.Required(CONF_ERINNERUNG): bool,
            vol.Required(CONF_ERINNERUNG_ZEIT): TimeSelector(),
            vol.Required(CONF_ERINNERUNG_TAGE): NumberSelector(NumberSelectorConfig(
                min=1, max=21, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="Tage")),
            vol.Optional(CONF_ERINNERUNG_ZIELE): SelectSelector(SelectSelectorConfig(
                options=ziel_optionen, multiple=True, mode=SelectSelectorMode.DROPDOWN, custom_value=True)),
            vol.Optional(CONF_FERIENKALENDER): EntitySelector(EntitySelectorConfig(domain="calendar")),
        })
        werte = {
            CONF_PORTAL: akt(CONF_PORTAL) or "",
            CONF_DASHBOARD: bool(akt(CONF_DASHBOARD, False)),
            CONF_ERINNERUNG: bool(akt(CONF_ERINNERUNG, False)),
            CONF_ERINNERUNG_ZEIT: akt(CONF_ERINNERUNG_ZEIT, STANDARD_ZEIT),
            CONF_ERINNERUNG_TAGE: akt(CONF_ERINNERUNG_TAGE, STANDARD_TAGE),
            CONF_ERINNERUNG_ZIELE: akt(CONF_ERINNERUNG_ZIELE) or [],
            CONF_FERIENKALENDER: akt(CONF_FERIENKALENDER),
        }
        if user_input is not None:
            werte.update(user_input)
        schema = self.add_suggested_values_to_schema(schema, {k: v for k, v in werte.items() if v is not None})
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
