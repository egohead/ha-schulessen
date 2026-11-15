"""Minimaler WAMP-v2-Client (WAMP-CRA) für Essensbestellportale."""
from __future__ import annotations

import base64
import hashlib
import hmac
import itertools
import json
from datetime import datetime, timedelta

import logging

import aiohttp

from homeassistant.util import dt as dt_util


_LOGGER = logging.getLogger(__name__)


def _dumps(obj) -> str:
    # Der Router erwartet kompaktes JSON ohne Leerzeichen.
    return json.dumps(obj, separators=(",", ":"))


class WampAuthError(Exception):
    """Login fehlgeschlagen."""


class WampApiError(Exception):
    """Sonstiger Fehler."""


def _sig(password: str, extra: dict, challenge: str) -> str:
    salt = extra.get("salt")
    if salt:
        # Das Portal speichert den PBKDF2-Schlüssel und leitet ihn beim Login ein zweites Mal ab.
        password = base64.b64encode(hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(),
            int(extra.get("iterations", 1000)), int(extra.get("keylen", 32)))).decode()
        key = base64.b64encode(hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(),
            int(extra.get("iterations", 1000)), int(extra.get("keylen", 32))))
    else:
        key = password.encode()
    return base64.b64encode(hmac.new(key, challenge.encode(), hashlib.sha256).digest()).decode()


def _text(dish: dict) -> tuple[str, str]:
    secs = (dish.get("dishDescription") or {}).get("textSections") or []
    parts = [s.get("text", "") for s in secs if not s.get("superscript") and not s.get("iconDataUrl")]
    text = "".join(parts).strip(" ,") or dish.get("name", "")
    haupt = ", ".join(s.get("text", "").strip(" ,") for s in secs
                      if s.get("bold") and not s.get("superscript") and s.get("text", "").strip(" ,"))
    return " ".join(text.split()), haupt


def _allergene(dish: dict) -> str:
    a = (dish.get("dishDescription") or {}).get("allergens") or []
    return ", ".join(x.get("abbreviation", "") for x in a if x.get("abbreviation"))


class WampClient:
    def __init__(self, session: aiohttp.ClientSession, url: str, realm: str,
                 login: str, password: str) -> None:
        if not url.lower().startswith("wss://"):
            raise WampApiError("Nur wss://-Adressen sind erlaubt")
        self._s = session
        self._url = url
        self._realm = realm
        self._login = login
        self._password = password
        self._ids = itertools.count(1)

    async def _session(self):
        ws = await self._s.ws_connect(self._url, protocols=("wamp.2.json",),
                                      timeout=aiohttp.ClientWSTimeout(ws_close=10), heartbeat=30,
                                      max_msg_size=16 * 1024 * 1024)
        try:
            await ws.send_str(_dumps([1, self._realm, {
                "roles": {
                    "caller": {"features": {"call_canceling": False, "call_timeout": False, "caller_identification": True,
                                            "payload_passthru_mode": True, "progressive_call_results": True}},
                    "callee": {"features": {"caller_identification": True, "call_trustlevels": False,
                                            "pattern_based_registration": False, "shared_registration": False,
                                            "call_timeout": False, "call_canceling": False,
                                            "progressive_call_results": True, "payload_passthru_mode": True}},
                    "subscriber": {"features": {"call_timeout": False, "call_canceling": False,
                                                "progressive_call_results": False, "payload_passthru_mode": True,
                                                "subscription_revocation": True}},
                    "publisher": {"features": {"publisher_identification": True, "subscriber_blackwhite_listing": True,
                                               "publisher_exclusion": True, "payload_passthru_mode": True}}},
                "authid": self._login, "authmethods": ["wampcra"]}]))
            for _ in range(10):
                msg = await ws.receive(timeout=20)
                if msg.type != aiohttp.WSMsgType.TEXT:
                    await ws.close()
                    raise WampApiError(f"Verbindung beendet: {msg.type}")
                m = json.loads(msg.data)
                _LOGGER.debug("WAMP session <- Typ %s", m[0] if m else None)
                if m[0] == 4:
                    extra = m[2] or {}
                    await ws.send_str(_dumps([5, _sig(self._password, extra, extra.get("challenge", "")), {}]))
                elif m[0] == 2:
                    return ws
                elif m[0] == 3:
                    await ws.close()
                    raise WampAuthError(str(m[2]) if len(m) > 2 else "abgelehnt")
            await ws.close()
            raise WampApiError("Kein Sitzungsaufbau")
        except BaseException:
            if not ws.closed:
                await ws.close()
            raise

    async def _call(self, ws, proc: str, kwargs: dict | None = None):
        rid = next(self._ids)
        msg = [48, rid, {}, proc]
        if kwargs is not None:
            msg += [[], kwargs]
        await ws.send_str(_dumps(msg))
        _LOGGER.debug("WAMP -> CALL %s", proc)
        for _ in range(100):
            r = await ws.receive(timeout=30)
            if r.type != aiohttp.WSMsgType.TEXT:
                raise WampApiError(f"Verbindung beendet: {r.type}")
            m = json.loads(r.data)
            _LOGGER.debug("WAMP <- Typ %s", m[0] if m else None)
            if m[0] == 50 and m[1] == rid:
                return (m[3] if len(m) > 3 else []) or []
            if m[0] == 8 and m[2] in (rid, -1):
                raise WampApiError(f"{proc}: {m[4] if len(m) > 4 else 'Fehler'}")
        raise WampApiError(f"{proc}: keine Antwort")

    async def test(self) -> dict:
        ws = await self._session()
        try:
            c = await self._call(ws, f"{self._realm}.get.caller.client")
            return c[0] if c else {}
        finally:
            await self._close(ws)

    async def _close(self, ws):
        try:
            await ws.send_str(_dumps([6, {}, "wamp.close.normal"]))
        except Exception:  # noqa: BLE001
            pass
        await ws.close()

    async def fetch(self, wochen: int) -> dict:
        heute = dt_util.now().date()
        montag = heute - timedelta(days=heute.weekday())
        ws = await self._session()
        tage: dict = {}
        try:
            client = await self._call(ws, f"{self._realm}.get.caller.client")
            for w in range(wochen):
                mo = montag + timedelta(weeks=w)
                stamp = datetime(mo.year, mo.month, mo.day, tzinfo=dt_util.get_default_time_zone())
                res = await self._call(ws, f"{self._realm}.get.caller.food.plan",
                                       {"monday": stamp.strftime("%Y-%m-%dT00:00:00.000%z")})
                plan = res[0] if res else {}
                for fd in plan.get("foodDays") or []:
                    groups = fd.get("mealsGroups") or []
                    if not groups:
                        continue
                    d = dt_util.as_local(dt_util.parse_datetime(fd["deliveryDate"])).date()
                    menues = []
                    schluss = None
                    for g in groups:
                        bis = g.get("orderableTo") or {}
                        if bis.get("timeDistance") == 0:
                            schluss = datetime(d.year, d.month, d.day, bis.get("hour", 8), bis.get("minute", 0),
                                               tzinfo=dt_util.get_default_time_zone()).isoformat()
                        for m in g.get("meals") or []:
                            dish = m.get("dish") or {}
                            if dish.get("isVisible") is False:
                                continue
                            text, haupt = _text(dish)
                            menues.append({
                                "nr": m.get("orderNumber"),
                                "name": m.get("name", ""),
                                "kurz": haupt,
                                "text": text,
                                "kennzeichnung": _allergene(dish),
                                "preis": m.get("grossPrice"),
                                "bestellt": bool(dish.get("ordered")),
                                "bestellbar": bool(dish.get("isOrderable")),
                                "stornierbar": bool(dish.get("isCancelable")),
                                "bestellschluss": schluss,
                                "abbestellschluss": schluss,
                            })
                    gew = next((x for x in menues if x["bestellt"]), None)
                    tage[d.isoformat()] = {
                        "datum": d.isoformat(), "feiertag": False, "zustellpause": False,
                        "pause_grund": "", "bestellt": gew, "menues": menues,
                        "bestellschluss": schluss,
                    }
        finally:
            await self._close(ws)
        c0 = client[0] if client else {}
        name = ((c0.get("vCard") or {}).get("names") or [{}])[0]
        return {"tage": tage, "einrichtung": {}, "teilnehmer": f"{name.get('givenName', '')} {name.get('surname', '')}".strip()}
