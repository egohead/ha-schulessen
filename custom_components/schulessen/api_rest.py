"""Minimaler REST-Client für Essensbestellportale mit Mandanten-Login."""
from __future__ import annotations

import re
from datetime import date

import aiohttp


class RestAuthError(Exception):
    """Login fehlgeschlagen."""


class RestApiError(Exception):
    """Sonstiger API-Fehler."""


def clean_text(raw: str) -> tuple[str, str]:
    """Menütext säubern, Kennzeichnungen (K, Ia, ...) getrennt zurückgeben."""
    t = raw or ""
    t = re.sub(r"\[/?b\]", "", t)
    t = t.replace("[br]", " ").replace('"', "")
    t = re.sub(r"\s+", " ", t).strip()
    kenn = ""
    m = re.search(r"\(([A-Z][^()]*)\)\s*$", t)
    if m and re.fullmatch(r"[A-Za-z0-9IVX.,\s]+", m.group(1)):
        kenn = m.group(1).strip()
        t = t[: m.start()].strip()
    t = re.sub(r"\s+,", ",", t).strip(" ,")
    return t, kenn


class RestClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, mandant: str,
                 login: str, password: str) -> None:
        if not url.lower().startswith("https://"):
            raise RestApiError("Nur https://-Adressen sind erlaubt")
        self._s = session
        self._url = url.rstrip("/")
        self._mandant = mandant
        self._login = login
        self._password = password
        self.token: str | None = None
        self.kunde: dict = {}

    async def _post(self, path: str, body: dict) -> dict:
        async with self._s.post(self._url + path, json=body,
                                timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status in (401, 403):
                raise RestAuthError(f"HTTP {r.status}")
            if r.status >= 400:
                raise RestApiError(f"HTTP {r.status}")
            data = await r.json(content_type=None)
        if not isinstance(data, dict) or "content" not in data:
            raise RestApiError("Unerwartete Antwort")
        if data.get("token"):
            self.token = data["token"]
        return data

    async def login(self) -> dict:
        try:
            data = await self._post("/login", {
                "command": "kunde/LoginAPI_1_5_1", "client": "web",
                "parameter": {"mandantId": self._mandant, "login": self._login,
                              "passwd": self._password, "lang": "de"}})
        except RestApiError as err:
            raise RestAuthError(str(err)) from err
        c = data.get("content")
        if not isinstance(c, dict) or not c.get("bestellerId") or not self.token:
            raise RestAuthError("Login abgelehnt")
        self.kunde = c
        return c

    async def ensure_session(self) -> None:
        if self.token:
            try:
                data = await self._post("/relogin", {
                    "token": self.token, "client": "web",
                    "parameter": {"mandantId": self._mandant}})
                c = data.get("content")
                if isinstance(c, dict) and c.get("bestellerId"):
                    self.kunde = c
                    return
            except (RestAuthError, RestApiError, aiohttp.ClientError):
                pass
        await self.login()

    async def _call(self, command: str, von: date, bis: date) -> dict:
        data = await self._post("/call", {
            "command": command, "client": "web",
            "parameter": {"mandantId": self._mandant,
                          "bestellerId[0]": self.kunde["bestellerId"],
                          "von": von.isoformat(), "bis": bis.isoformat()},
            "token": self.token})
        c = data.get("content")
        if not isinstance(c, dict):
            raise RestApiError(f"{command}: unerwartete Antwort")
        return c

    async def fetch(self, von: date, bis: date) -> dict:
        await self.ensure_session()
        plan = await self._call("speiseplan/kundeAPI_1_5", von, bis)
        best = await self._call("bestellungen/getAPI_1_5", von, bis)
        texte = plan.get("menuetexte") or {}
        tage_plan = {}
        for k in (plan.get("kunden") or {}).values():
            tage_plan.update(k.get("speisePlanTage") or {})
        tage_best = {}
        for k in (best.get("kunden") or {}).values():
            tage_best.update(k.get("tage") or {})
        pausen = self.kunde.get("zustellPausen") or []
        tage = {}
        for datum, tag in sorted(tage_plan.items()):
            pause = next((p for p in pausen
                          if p.get("von", "") <= datum <= p.get("bis", "")), None)
            bm = (tage_best.get(datum) or {}).get("bestellMenues") or {}
            menues = []
            for nr, m in sorted((tag.get("tagesMenues") or {}).items(),
                                key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0):
                tx = texte.get(m.get("menueTextId"), {})
                text, kenn = clean_text(tx.get("menueText", ""))
                b = bm.get(str(nr)) or {}
                menge = b.get("mengeNeu", b.get("mengeAlt", 0)) or 0
                menues.append({
                    "nr": int(nr) if str(nr).isdigit() else nr,
                    "name": m.get("bezeichnung") or tx.get("bezeichnung", ""),
                    "kurz": m.get("kurzBez", ""),
                    "text": text,
                    "kennzeichnung": kenn,
                    "preis": (m.get("preis") or {}).get("betrag"),
                    "bestellt": menge > 0,
                    "bestellschluss": m.get("bestellschluss"),
                    "abbestellschluss": m.get("abbestellschluss"),
                })
            gew = next((x for x in menues if x["bestellt"]), None)
            tage[datum] = {
                "datum": datum,
                "feiertag": bool(tag.get("feiertag")),
                "zustellpause": bool(tag.get("zustellPause")) or pause is not None,
                "pause_grund": (pause or {}).get("info") or (pause or {}).get("grund", ""),
                "bestellt": gew,
                "menues": menues,
                "bestellschluss": menues[0]["bestellschluss"] if menues else None,
            }
        return {
            "tage": tage,
            "einrichtung": self.kunde.get("einrichtung") or {},
            "teilnehmer": (self.kunde.get("essensteilnehmer") or {}).get("vorname", ""),
        }
