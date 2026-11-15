/* Schulessen-Karte für Home Assistant */
(() => {
  const TAG = "schulessen-card";
  if (customElements.get(TAG)) return;

  const L = {
    de: {
      wt: ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"],
      wtLang: ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"],
      mon: ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."],
      kurz: (wt, d, m) => `${wt} ${d}.${m}.`,
      lang: (wt, d, mon) => `${wt}, ${d}. ${mon}`,
      uhr: (hm) => `${hm} Uhr`,
      locale: "de-DE",
      status: { ok: "Bestellt", offen: "Nicht bestellt", pause: "Abbestellt", frei: "Feiertag", leer: "Kein Speiseplan", ohne: "Kein Essen nötig" },
      ohneText: "Für diesen Tag ist bewusst nichts bestellt.", ohneSetzen: "Kein Essen nötig", ohneAufheben: "Doch Essen bestellen",
      heute: "Heute", morgen: "Morgen", naechster: "Nächster Schultag", demnaechst: "Demnächst",
      keinPlan: "Noch kein Speiseplan", keinPlanKurz: "Kein Plan", keineVersorgung: "Für diesen Tag ist keine Versorgung vorgesehen.",
      nichtsBestellt: "Noch nichts bestellt", angebote: (n) => `${n} ${n === 1 ? "Angebot" : "Angebote"} zur Auswahl`,
      kennzeichnung: "Kennzeichnung", bestellschluss: "Bestellschluss", abgelaufen: "abgelaufen",
      nochMin: (n) => `noch ${n} Min.`, nochStd: (n) => `noch ${n} Std.`, nochTage: (n) => `noch ${n} Tage`,
      allesBestellt: (sp) => (sp === 1 ? "Morgen ist alles bestellt" : sp ? `In den nächsten ${sp} Tagen ist alles bestellt` : "Alle kommenden Schultage sind bestellt"),
      ohne: (n, sp) => `${n} ${n === 1 ? "Schultag" : "Schultage"} ohne Bestellung${sp ? (sp === 1 ? " (morgen)" : ` (nächste ${sp} Tage)`) : ""}`,
      weitere: (n) => ` und ${n} weitere`,
      bestellen: "Bestellen", portal: "Bestellportal öffnen", kw: "KW",
      dieseWoche: "Diese Woche", kommendeWoche: "Kommende Woche", naechsteWoche: "Nächste Woche", inWochen: (n) => `in ${n} Wochen`,
      tipp: "Tag antippen für alle Angebote", keineAngebote: "Keine Angebote", bestellt: "bestellt",
      stand: "Stand", cache: "Zwischenspeicher", aktualisieren: "Jetzt aktualisieren",
      vorWoche: "Vorherige Woche", nachWoche: "Nächste Woche", fehlt: (e) => `Entität ${e} nicht gefunden`,
    },
    en: {
      wt: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
      wtLang: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      mon: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
      kurz: (wt, d, m) => `${wt} ${d}/${m}`,
      lang: (wt, d, mon) => `${wt}, ${d} ${mon}`,
      uhr: (hm) => hm,
      locale: "en-GB",
      status: { ok: "Ordered", offen: "Not ordered", pause: "Cancelled", frei: "Holiday", leer: "No menu", ohne: "No meal needed" },
      ohneText: "Deliberately not ordered for this day.", ohneSetzen: "No meal needed", ohneAufheben: "Order a meal after all",
      heute: "Today", morgen: "Tomorrow", naechster: "Next school day", demnaechst: "Coming up",
      keinPlan: "No menu yet", keinPlanKurz: "No menu", keineVersorgung: "No meals are planned for this day.",
      nichtsBestellt: "Nothing ordered yet", angebote: (n) => `${n} ${n === 1 ? "option" : "options"} available`,
      kennzeichnung: "Labels", bestellschluss: "Order by", abgelaufen: "passed",
      nochMin: (n) => `${n} min left`, nochStd: (n) => `${n} h left`, nochTage: (n) => `${n} days left`,
      allesBestellt: (sp) => (sp === 1 ? "Tomorrow is ordered" : sp ? `Everything ordered for the next ${sp} days` : "All upcoming school days are ordered"),
      ohne: (n, sp) => `${n} school ${n === 1 ? "day" : "days"} without an order${sp ? (sp === 1 ? " (tomorrow)" : ` (next ${sp} days)`) : ""}`,
      weitere: (n) => ` and ${n} more`,
      bestellen: "Order", portal: "Open order portal", kw: "Week",
      dieseWoche: "This week", kommendeWoche: "Coming week", naechsteWoche: "Next week", inWochen: (n) => `in ${n} weeks`,
      tipp: "Tap a day for all options", keineAngebote: "No options", bestellt: "ordered",
      stand: "Updated", cache: "Cached", aktualisieren: "Refresh now",
      vorWoche: "Previous week", nachWoche: "Next week", fehlt: (e) => `Entity ${e} not found`,
    },
  };
  let S = L.de;
  const sprache = (hass) => {
    const l = (hass && (hass.locale?.language || hass.language)) || "de";
    S = l.toLowerCase().startsWith("de") ? L.de : L.en;
    return S;
  };

  const esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const parseDay = (iso) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  };
  const isoDay = (d) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const kurzDatum = (iso) => {
    const d = parseDay(iso);
    return S.kurz(S.wt[d.getDay()], d.getDate(), d.getMonth() + 1);
  };
  const langDatum = (iso) => {
    const d = parseDay(iso);
    return S.lang(S.wtLang[d.getDay()], d.getDate(), S.mon[d.getMonth()]);
  };
  const montag = (d) => {
    const m = new Date(d);
    m.setDate(m.getDate() - ((m.getDay() + 6) % 7));
    m.setHours(0, 0, 0, 0);
    return m;
  };
  const kw = (d) => {
    const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    const n = t.getUTCDay() || 7;
    t.setUTCDate(t.getUTCDate() + 4 - n);
    const j = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    return Math.ceil(((t - j) / 86400000 + 1) / 7);
  };
  const preis = (p) => {
    if (p === null || p === undefined || p === "") return "";
    const n = Number(p);
    return Number.isFinite(n) ? n.toLocaleString(S.locale, { style: "currency", currency: "EUR" }) : esc(p);
  };
  const parseZeit = (v) => {
    if (!v) return null;
    let t = Date.parse(v);
    if (!Number.isNaN(t)) return new Date(t);
    const m = String(v).match(/(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\D+(\d{1,2}):(\d{2}))?/);
    if (m) return new Date(+m[3], +m[2] - 1, +m[1], +(m[4] || 0), +(m[5] || 0));
    return null;
  };
  const restZeit = (ziel) => {
    const ms = ziel - new Date();
    if (ms <= 0) return S.abgelaufen;
    const min = Math.round(ms / 60000);
    if (min < 60) return S.nochMin(min);
    const h = Math.floor(min / 60);
    if (h < 48) return S.nochStd(h);
    return S.nochTage(Math.floor(h / 24));
  };
  const zeitText = (ziel) =>
    `${S.kurz(S.wt[ziel.getDay()], ziel.getDate(), ziel.getMonth() + 1)}, ${S.uhr(
      `${String(ziel.getHours()).padStart(2, "0")}:${String(ziel.getMinutes()).padStart(2, "0")}`
    )}`;

  const art = (tag) => {
    if (!tag) return "leer";
    if (tag.feiertag) return "frei";
    if (tag.pause) return "pause";
    if (!tag.menues || !tag.menues.length) return "leer";
    if (tag.menues.some((m) => m.bestellt)) return "ok";
    if (tag.ausgenommen) return "ohne";
    return "offen";
  };
  const punkt = (k) => `<i class="dot ${k}" aria-hidden="true"></i>`;

  class SchulessenCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._woche = 0;
      this._auswahl = null;
      this._sig = "";
    }

    static getConfigElement() {
      return document.createElement("schulessen-card-editor");
    }

    static getStubConfig(hass) {
      const e = Object.keys(hass.states).find((k) => hass.states[k].attributes.schulessen_karte);
      return { entity: e || "", variante: "voll" };
    }

    setConfig(config) {
      if (!config.entity) throw new Error("entity fehlt: Stand-Sensor der Schulessen-Integration angeben");
      this._config = { variante: "voll", ...config };
      this._sig = "";
      if (this._hass) {
        this._eid = this._stand(this._hass);
        this._render();
      }
    }

    _stand(hass) {
      const id = this._config?.entity;
      const st = hass.states[id];
      if (!st || st.attributes.schulessen_karte) return id;
      const dev = hass.entities?.[id]?.device_id;
      if (!dev) return id;
      return Object.keys(hass.entities).find((k) => hass.entities[k].device_id === dev && hass.states[k]?.attributes.schulessen_karte) || id;
    }

    set hass(hass) {
      this._hass = hass;
      this._eid = this._stand(hass);
      const st = hass.states[this._eid];
      const sig = st ? `${st.last_updated}|${st.state}` : "none";
      if (sig !== this._sig) {
        this._sig = sig;
        this._render();
      }
    }

    getCardSize() {
      return this._config?.variante === "kompakt" ? 4 : 10;
    }

    getGridOptions() {
      return this._config?.variante === "kompakt" ? { columns: 12, min_columns: 6 } : { columns: "full" };
    }

    _tage() {
      const st = this._hass.states[this._eid || this._config.entity];
      return (st && st.attributes.tage) || [];
    }

    _aktualisieren() {
      this._hass.callService("homeassistant", "update_entity", { entity_id: this._eid || this._config.entity });
      const b = this.shadowRoot.querySelector(".refresh");
      if (b) {
        b.classList.add("dreht");
        setTimeout(() => b.classList.remove("dreht"), 600);
      }
    }

    _render() {
      if (!this._hass || !this._config) return;
      sprache(this._hass);
      const st = this._hass.states[this._eid || this._config.entity];
      if (!st) {
        this.shadowRoot.innerHTML = `<style>${CSS}</style><ha-card><div class="leerhinweis">${S.fehlt(esc(this._config.entity))}</div></ha-card>`;
        return;
      }
      const a = st.attributes;
      const tage = this._tage();
      const heute = isoDay(new Date());
      const tagHeute = tage.find((t) => t.datum === heute);
      const jetzt = new Date();
      const nachAusgabe = jetzt.getHours() >= 14;
      let hero = tagHeute && art(tagHeute) !== "leer" && art(tagHeute) !== "frei" && !nachAusgabe ? tagHeute : null;
      let heroLabel = S.heute;
      if (!hero) {
        hero = tage.find((t) => t.datum > heute && art(t) !== "leer" && art(t) !== "frei") || null;
        const morgen = new Date();
        morgen.setDate(morgen.getDate() + 1);
        heroLabel = hero && hero.datum === isoDay(morgen) ? S.morgen : S.naechster;
      }
      const grenze = new Date();
      grenze.setDate(grenze.getDate() + (Number(a.hinweis_tage) > 0 ? Number(a.hinweis_tage) : 21));
      const bis = isoDay(grenze);
      const offen = tage.filter((t) => t.datum >= heute && t.datum <= bis && art(t) === "offen");
      this._spanne = Number(a.hinweis_tage) > 0 ? Number(a.hinweis_tage) : null;
      const kompakt = this._config.variante === "kompakt";
      const titel = this._config.titel || a.kind || "Schulessen";
      const stand = st.state && st.state !== "unknown" ? new Date(st.state) : null;
      const live = a.live !== false;

      this.shadowRoot.innerHTML = `
        <style>${CSS}</style>
        <ha-card class="${kompakt ? "kompakt" : ""}">
          <header>
            <div class="kopf">
              <div class="name">${esc(titel)}</div>
              ${a.einrichtung ? `<div class="einrichtung">${esc(a.einrichtung)}</div>` : ""}
            </div>
            <div class="aktionen">
              <span class="stand" title="${stand ? S.stand + " " + stand.toLocaleString(S.locale) : ""}">
                ${punkt(live ? "live" : "cache")}${live ? S.stand : S.cache}${
        stand ? ` ${String(stand.getHours()).padStart(2, "0")}:${String(stand.getMinutes()).padStart(2, "0")}` : ""
      }
              </span>
              <button class="refresh" title="${S.aktualisieren}" aria-label="${S.aktualisieren}"><ha-icon icon="mdi:refresh"></ha-icon></button>
            </div>
          </header>
          ${this._heroHtml(hero, heroLabel)}
          ${this._offenHtml(offen, a.portal, kompakt)}
          ${kompakt ? "" : this._wocheHtml(tage, heute)}
          ${kompakt ? "" : this._detailHtml(tage)}
          ${!kompakt && a.portal ? `<footer><a class="link" href="${esc(a.portal)}" target="_blank" rel="noopener">${S.portal}<ha-icon icon="mdi:arrow-top-right"></ha-icon></a></footer>` : ""}
        </ha-card>`;

      this.shadowRoot.querySelector(".refresh")?.addEventListener("click", () => this._aktualisieren());
      this.shadowRoot.querySelectorAll("[data-woche]").forEach((b) =>
        b.addEventListener("click", () => {
          this._woche = Math.max(0, Math.min(3, this._woche + Number(b.dataset.woche)));
          this._auswahl = null;
          this._render();
        })
      );
      this.shadowRoot.querySelectorAll("[data-ohne]").forEach((b) =>
        b.addEventListener("click", () => {
          b.disabled = true;
          this._hass.callService("schulessen", "kein_essen", {
            entity_id: this._eid || this._config.entity,
            datum: b.dataset.datum,
            aktiv: b.dataset.ohne === "1",
          });
        })
      );
      this.shadowRoot.querySelectorAll("[data-tag]").forEach((b) =>
        b.addEventListener("click", () => {
          this._auswahl = this._auswahl === b.dataset.tag ? null : b.dataset.tag;
          this._render();
        })
      );
    }

    _heroHtml(tag, label) {
      if (!tag) {
        return `<section class="hero leer"><div class="label">${S.demnaechst}</div><div class="gericht">${S.keinPlan}</div></section>`;
      }
      const k = art(tag);
      const stText = S.status[k];
      const b = (tag.menues || []).find((m) => m.bestellt);
      const schluss = parseZeit(tag.bestellschluss);
      let gericht, text, chips = "", rechts = "";
      if (k === "ok") {
        gericht = esc(b.kurz || b.name);
        text = b.kurz && b.text ? esc(b.text) : b.text && b.text !== b.name ? esc(b.text) : "";
        chips = [esc(b.name)].concat(b.kennzeichnung ? [`${S.kennzeichnung} ${esc(b.kennzeichnung)}`] : []).join(" · ");
        rechts = b.preis !== null && b.preis !== undefined ? `<div class="preis">${preis(b.preis)}</div>` : "";
      } else if (k === "ohne") {
        gericht = S.status.ohne;
        text = S.ohneText;
      } else if (k === "pause") {
        gericht = S.status.pause;
        text = tag.pause_grund ? esc(tag.pause_grund) : S.keineVersorgung;
      } else {
        gericht = S.nichtsBestellt;
        text = S.angebote((tag.menues || []).length);
      }
      return `
        <section class="hero ${k}">
          <div class="label">${label}<span class="datum"> · ${langDatum(tag.datum)}</span></div>
          <div class="zeile">
            <div class="haupt">
              <div class="gericht">${gericht}</div>
              ${text ? `<div class="beschreibung">${text}</div>` : ""}
              ${chips ? `<div class="meta">${chips}</div>` : ""}
            </div>
            ${rechts}
          </div>
          <div class="fuss">
            <span class="status ${k}">${punkt(k)}${stText}</span>
            ${schluss && k === "offen" ? `<span class="frist">${S.bestellschluss} ${zeitText(schluss)}, ${restZeit(schluss)}</span>` : ""}
          </div>
        </section>`;
    }

    _offenHtml(offen, portal, kompakt) {
      if (!offen.length) {
        return kompakt ? "" : `<div class="hinweis gut">${punkt("ok")}${S.allesBestellt(this._spanne)}</div>`;
      }
      const liste = offen.slice(0, kompakt ? 3 : 8).map((t) => kurzDatum(t.datum)).join(", ");
      const mehr = offen.length > (kompakt ? 3 : 8) ? S.weitere(offen.length - (kompakt ? 3 : 8)) : "";
      return `
        <div class="hinweis warn">
          ${punkt("offen")}
          <div class="hinweistext"><strong>${S.ohne(offen.length, this._spanne)}</strong><span>${liste}${mehr}</span></div>
          ${portal ? `<a class="knopf" href="${esc(portal)}" target="_blank" rel="noopener">${S.bestellen}</a>` : ""}
        </div>`;
    }

    _wocheHtml(tage, heute) {
      const jetzt = new Date();
      const wochenende = jetzt.getDay() === 0 || jetzt.getDay() === 6;
      const start = montag(jetzt);
      start.setDate(start.getDate() + (this._woche + (wochenende ? 1 : 0)) * 7);
      const map = Object.fromEntries(tage.map((t) => [t.datum, t]));
      const zellen = [];
      for (let i = 0; i < 5; i++) {
        const d = new Date(start);
        d.setDate(d.getDate() + i);
        const iso = isoDay(d);
        const t = map[iso];
        const k = iso < heute ? "vorbei" : art(t);
        const b = t && (t.menues || []).find((m) => m.bestellt);
        const inhalt =
          k === "ok" ? esc(b.kurz || b.name) : k === "vorbei" ? "" : k === "leer" ? S.keinPlanKurz : S.status[k];
        zellen.push(`
          <button class="tag ${k} ${iso === heute ? "heute" : ""} ${this._auswahl === iso ? "aktiv" : ""}" data-tag="${iso}" ${t ? "" : "disabled"}>
            <span class="tkopf"><span class="wt">${S.kurz(S.wt[d.getDay()], d.getDate(), d.getMonth() + 1)}</span>${k === "vorbei" ? "" : punkt(k)}</span>
            <span class="was">${inhalt}</span>
            ${b && b.name && (b.kurz || "") !== b.name ? `<span class="linie">${esc(b.name)}</span>` : ""}
          </button>`);
      }
      return `
        <section class="woche">
          <div class="wochenkopf">
            <button class="nav" data-woche="-1" ${this._woche === 0 ? "disabled" : ""} aria-label="${S.vorWoche}"><ha-icon icon="mdi:chevron-left"></ha-icon></button>
            <div class="kw">${S.kw} ${kw(start)}<span>${this._woche === 0 ? (wochenende ? S.kommendeWoche : S.dieseWoche) : this._woche === 1 && !wochenende ? S.naechsteWoche : S.inWochen(this._woche + (wochenende ? 1 : 0))}</span></div>
            <button class="nav" data-woche="1" ${this._woche >= (wochenende ? 2 : 3) ? "disabled" : ""} aria-label="${S.nachWoche}"><ha-icon icon="mdi:chevron-right"></ha-icon></button>
          </div>
          <div class="tage">${zellen.join("")}</div>
        </section>`;
    }

    _detailHtml(tage) {
      if (!this._auswahl) return `<div class="tipp">${S.tipp}</div>`;
      const t = tage.find((x) => x.datum === this._auswahl);
      if (!t) return "";
      const k = art(t);
      if (k === "pause" || k === "frei") {
        return `<section class="detail"><div class="detailkopf">${langDatum(t.datum)}</div><div class="leise">${
          k === "frei" ? S.status.frei : esc(t.pause_grund || S.status.pause)
        }</div></section>`;
      }
      const schluss = parseZeit(t.bestellschluss);
      const umschalten =
        (k === "offen" || k === "ohne") && (!schluss || schluss > new Date())
          ? `<button class="umschalten" data-ohne="${k === "offen" ? 1 : 0}" data-datum="${t.datum}">${k === "offen" ? S.ohneSetzen : S.ohneAufheben}</button>`
          : "";
      const menues = (t.menues || [])
        .map(
          (m) => `
          <div class="menue ${m.bestellt ? "gewaehlt" : ""}">
            <div class="mkopf">
              <span class="mname">${esc(m.name)}</span>
              ${m.bestellt ? `<span class="haken">${punkt("ok")}${S.bestellt}</span>` : ""}
              <span class="mpreis">${preis(m.preis)}</span>
            </div>
            <div class="mtext">${esc(m.kurz && m.text ? m.text : m.text || m.kurz || "")}</div>
            ${m.kennzeichnung ? `<div class="mkenn">${S.kennzeichnung} ${esc(m.kennzeichnung)}</div>` : ""}
          </div>`
        )
        .join("");
      return `
        <section class="detail">
          <div class="detailkopf">${langDatum(t.datum)}${
        schluss ? `<span class="leise">${S.bestellschluss} ${zeitText(schluss)}${schluss > new Date() ? ", " + restZeit(schluss) : ""}</span>` : ""
      }</div>
          ${k === "ohne" ? `<div class="leise ohnehinweis">${S.ohneText}</div>` : ""}
          ${menues || `<div class="leise">${S.keineAngebote}</div>`}
          ${umschalten ? `<div class="detailfuss">${umschalten}</div>` : ""}
        </section>`;
    }
  }

  const CSS = `
    :host { --se-akzent: var(--primary-color); --se-ok: var(--success-color, #2e7d32); --se-warn: var(--warning-color, #c77c02);
            --se-warn-text: color-mix(in srgb, var(--se-warn) 78%, var(--primary-text-color));
            --se-leise: var(--secondary-text-color); --se-linie: color-mix(in srgb, var(--primary-text-color) 9%, transparent);
            --se-flaeche: color-mix(in srgb, var(--primary-text-color) 3%, transparent);
            --se-ease: cubic-bezier(.2, 0, 0, 1);
            --se-serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif; }
    ha-card { overflow: hidden; padding: 0; }
    button { font:inherit; color:inherit; background:none; border:0; cursor:pointer; }
    button:focus-visible, a:focus-visible { outline:2px solid var(--se-akzent); outline-offset:2px; }

    .dot { display:inline-block; width:8px; height:8px; border-radius:50%; flex-shrink:0; box-sizing:border-box; }
    .dot.ok, .dot.live { background:var(--se-ok); }
    .dot.offen { border:1.5px solid var(--se-warn); }
    .dot.cache { border:1.5px solid var(--se-leise); }
    .dot.pause, .dot.frei, .dot.leer, .dot.ohne { background:color-mix(in srgb, var(--se-leise) 45%, transparent); }

    header { display:flex; justify-content:space-between; align-items:center; gap:12px; padding:16px 16px 12px 24px; }
    .name { font-family:var(--se-serif); font-size:22px; line-height:1.2; color:var(--primary-text-color); }
    .einrichtung { font-size:13px; color:var(--se-leise); margin-top:4px; }
    .aktionen { display:flex; align-items:center; gap:4px; flex-shrink:0; }
    .stand { display:inline-flex; align-items:center; gap:8px; font-size:12px; color:var(--se-leise); white-space:nowrap;
             font-variant-numeric:tabular-nums; }
    .refresh { width:36px; height:36px; border-radius:8px; display:grid; place-items:center; color:var(--se-leise);
               transition:background-color .15s var(--se-ease); }
    .refresh:hover { background:var(--se-flaeche); }
    .refresh ha-icon { --mdc-icon-size:18px; }
    .refresh.dreht ha-icon { transform:rotate(360deg); transition:transform .6s var(--se-ease); }

    .hero { margin:0 16px; padding:20px; border-radius:12px; background:var(--se-flaeche); border:1px solid var(--se-linie); }
    .label { font-size:13px; font-weight:500; color:var(--primary-text-color); }
    .label .datum { color:var(--se-leise); font-weight:400; }
    .zeile { display:flex; justify-content:space-between; gap:16px; align-items:baseline; margin-top:8px; }
    .gericht { font-family:var(--se-serif); font-size:26px; line-height:1.2; color:var(--primary-text-color); }
    .beschreibung { margin-top:8px; font-size:14px; line-height:1.5; color:var(--se-leise); }
    .preis { font-family:var(--se-serif); font-size:20px; white-space:nowrap; color:var(--primary-text-color); font-variant-numeric:tabular-nums; }
    .meta { margin-top:8px; font-size:12px; color:var(--se-leise); }
    .fuss { display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:16px; align-items:center; font-size:13px; }
    .status { display:inline-flex; align-items:center; gap:8px; font-weight:500; color:var(--primary-text-color); }
    .status.offen { color:var(--se-warn-text); }
    .status.pause, .status.leer, .status.frei, .status.ohne { color:var(--se-leise); }
    .frist { color:var(--se-leise); font-variant-numeric:tabular-nums; }

    .hinweis { display:flex; align-items:center; gap:12px; margin:12px 16px 0; padding:12px 16px; border-radius:12px; font-size:14px;
               border:1px solid var(--se-linie); }
    .hinweis.gut { color:var(--se-leise); font-size:13px; border:0; padding:4px 20px; }
    .hinweistext { display:flex; flex-direction:column; gap:4px; flex:1; min-width:0; }
    .hinweistext strong { font-weight:500; color:var(--se-warn-text); }
    .hinweistext span { color:var(--se-leise); font-size:13px; }
    .knopf { text-decoration:none; font-weight:500; font-size:13px; padding:8px 16px; border-radius:8px; white-space:nowrap;
             background:var(--primary-text-color); color:var(--card-background-color, #fff); transition:opacity .15s var(--se-ease); }
    .knopf:hover { opacity:.85; }

    .woche { margin:20px 16px 0; }
    .wochenkopf { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
    .kw { font-family:var(--se-serif); font-size:18px; display:flex; flex-direction:column; align-items:center; line-height:1.2; }
    .kw span { font-family:var(--paper-font-body1_-_font-family, sans-serif); font-size:12px; color:var(--se-leise); margin-top:2px; }
    .nav { width:36px; height:36px; border-radius:8px; display:grid; place-items:center; color:var(--se-leise);
           transition:background-color .15s var(--se-ease); }
    .nav:hover:not([disabled]) { background:var(--se-flaeche); }
    .nav[disabled] { opacity:.3; cursor:default; }
    .tage { display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:8px; }
    .tag { text-align:left; padding:12px; border-radius:10px; border:1px solid var(--se-linie); min-height:96px;
           display:flex; flex-direction:column; gap:4px; transition:background-color .15s var(--se-ease), border-color .15s var(--se-ease); }
    .tag:hover:not([disabled]) { background:var(--se-flaeche); }
    .tag[disabled] { cursor:default; }
    .tkopf { display:flex; align-items:center; justify-content:space-between; gap:8px; }
    .tag .wt { font-size:12px; color:var(--se-leise); font-variant-numeric:tabular-nums; }
    .tag .was { font-size:13px; line-height:1.4; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden;
                color:var(--primary-text-color); }
    .tag .linie { font-size:12px; color:var(--se-leise); margin-top:auto; padding-top:4px; }
    .tag.offen .was { color:var(--se-warn-text); }
    .tag.pause .was, .tag.frei .was, .tag.leer .was, .tag.ohne .was { color:var(--se-leise); }
    .tag.vorbei { opacity:.45; }
    .tag.heute { border-color:color-mix(in srgb, var(--se-akzent) 55%, transparent); }
    .tag.aktiv { background:var(--se-flaeche); border-color:var(--se-akzent); }

    .tipp { text-align:center; font-size:12px; color:var(--se-leise); margin:12px 16px 0; }
    .detail { margin:12px 16px 0; padding:16px 20px; border-radius:12px; border:1px solid var(--se-linie); }
    .detailkopf { font-family:var(--se-serif); font-size:18px; display:flex; flex-wrap:wrap; gap:4px 12px; align-items:baseline; margin-bottom:4px; }
    .leise { font-size:13px; color:var(--se-leise); font-family:var(--paper-font-body1_-_font-family, sans-serif); font-variant-numeric:tabular-nums; }
    .menue { padding:12px 0; border-top:1px solid var(--se-linie); }
    .detailkopf + .menue { border-top:0; }
    .mkopf { display:flex; align-items:center; gap:12px; }
    .mname { font-size:13px; font-weight:500; color:var(--se-leise); }
    .menue.gewaehlt .mname { color:var(--primary-text-color); }
    .haken { display:inline-flex; align-items:center; gap:8px; font-size:12px; color:var(--se-leise); }
    .mpreis { margin-left:auto; font-family:var(--se-serif); font-size:16px; font-variant-numeric:tabular-nums; }
    .mtext { font-size:14px; line-height:1.5; margin-top:4px; }
    .mkenn { font-size:12px; color:var(--se-leise); margin-top:4px; }
    .ohnehinweis { margin:4px 0 8px; }
    .detailfuss { display:flex; justify-content:flex-end; padding-top:12px; border-top:1px solid var(--se-linie); margin-top:4px; }
    .umschalten { font-size:13px; font-weight:500; padding:8px 16px; border-radius:8px; border:1px solid var(--se-linie);
                  color:var(--primary-text-color); transition:background-color .15s var(--se-ease); }
    .umschalten:hover:not([disabled]) { background:var(--se-flaeche); }
    .umschalten[disabled] { opacity:.5; cursor:default; }

    footer { padding:16px 24px 20px; display:flex; justify-content:flex-end; }
    .link { display:inline-flex; align-items:center; gap:4px; font-size:13px; font-weight:500; text-decoration:none; color:var(--se-akzent); }
    .link ha-icon { --mdc-icon-size:16px; }
    ha-card > :last-child:not(footer) { margin-bottom:16px; }
    ha-card.kompakt .gericht { font-size:22px; }
    .leerhinweis { padding:20px 24px; color:var(--se-leise); }

    @media (max-width: 560px) {
      .tage { grid-template-columns:1fr; }
      .tag { min-height:0; }
      .tag .was { -webkit-line-clamp:2; }
      .gericht { font-size:22px; }
      header { padding:12px 12px 12px 20px; }
    }
  `;

  class SchulessenCardEditor extends HTMLElement {
    setConfig(config) {
      this._config = { ...config };
      this._aufbauen();
    }

    set hass(hass) {
      this._hass = hass;
      this._aufbauen();
    }

    _aufbauen() {
      if (!this._hass || !this._config) return;
      const en = sprache(this._hass) === L.en;
      if (!this._form) {
        this._form = document.createElement("ha-form");
        this._form.computeLabel = (f) =>
          ({ entity: en ? "Child (status sensor)" : "Kind (Stand-Sensor)", variante: en ? "Layout" : "Darstellung", titel: en ? "Title (optional)" : "Titel (optional)" })[f.name];
        this._form.addEventListener("value-changed", (ev) => {
          this._config = { ...this._config, ...ev.detail.value };
          Object.keys(this._config).forEach((k) => (this._config[k] === "" || this._config[k] === undefined) && delete this._config[k]);
          this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
        });
        this.appendChild(this._form);
      }
      this._form.hass = this._hass;
      this._form.schema = [
        { name: "entity", required: true, selector: { entity: { integration: "schulessen", domain: "sensor" } } },
        { name: "variante", selector: { select: { mode: "dropdown", options: [
          { value: "voll", label: en ? "Full (with week)" : "Voll (mit Woche)" },
          { value: "kompakt", label: en ? "Compact" : "Kompakt" },
        ] } } },
        { name: "titel", selector: { text: {} } },
      ];
      this._form.data = { variante: "voll", ...this._config };
    }
  }

  customElements.define(TAG, SchulessenCard);
  if (!customElements.get("schulessen-card-editor")) customElements.define("schulessen-card-editor", SchulessenCardEditor);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === TAG)) {
    window.customCards.push({
      type: TAG,
      name: "Schulessen",
      description: "Speiseplan, Bestellstatus und Wochenübersicht",
      preview: true,
      documentationURL: "https://github.com/egohead/ha-schulessen",
    });
  }
})();
