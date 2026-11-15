DOMAIN = "schulessen"

CONF_TYP = "typ"
TYP_WAMP = "wamp"
TYP_REST = "rest"
CONF_REALM = "realm"
CONF_MANDANT = "mandant"
CONF_NAME = "name"
CONF_PORTAL = "portal_url"
CONF_DASHBOARD = "dashboard"
DASHBOARD_ANGELEGT = "dashboard_angelegt"
CONF_BESTAETIGUNG = "bestaetigung"
CONF_VORLAGE = "vorlage"

WOCHEN = 3          # WAMP: Wochen im Voraus
TAGE_VORAUS = 21    # REST: Tage im Voraus

CONF_ERINNERUNG = "erinnerung"
CONF_ERINNERUNG_ZEIT = "erinnerung_zeit"
CONF_ERINNERUNG_TAGE = "erinnerung_tage"
CONF_ERINNERUNG_ZIELE = "erinnerung_ziele"
CONF_FERIENKALENDER = "ferienkalender"
CONF_APP_LINK = "app_link"  # z. B. shortcuts://run-shortcut?name=…, für Benachrichtigungen
CONF_VORLAUF = "erinnerung_vorlauf"  # Stunden vor Bestellschluss, 0 = aus
STANDARD_ZEIT = "17:00:00"
STANDARD_TAGE = 3

# Vorlagen für die Einrichtung
VORLAGEN = {
    "dls_seb_leipzig": {
        "titel": "DLS „Guten APPetit!“ (SEB Schulessen Leipzig)",
        CONF_TYP: TYP_WAMP,
        CONF_REALM: "biz.dls",
        "url": "wss://connectanum.dls-gmbh.biz/wamp",
        CONF_PORTAL: "https://seb.dls-gmbh.biz/mein-essen",
    },
    "gfb_leipzig": {
        "titel": "GFB Catering Leipzig",
        CONF_TYP: TYP_REST,
        CONF_MANDANT: "108106-gfb-leipzig",
        "url": "https://proxy.mms-rcs.de",
        CONF_PORTAL: "https://bestellung-gfb-catering.de",
    },
    "manuell_wamp": {"titel": "Anderes Portal mit WAMP-Schnittstelle (wss://…, Realm)", CONF_TYP: TYP_WAMP},
    "manuell_rest": {"titel": "Anderes Portal mit REST-Schnittstelle (https://…, Mandant)", CONF_TYP: TYP_REST},
}
