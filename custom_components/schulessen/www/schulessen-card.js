/* Schulessen-Karte für Home Assistant (wird von den Schulessen-Integrationen mitgeliefert). */
(() => {
  const TAG = "schulessen-card";
  if (customElements.get(TAG)) return;

  const WT = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
  const WT_LANG = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];
  const MON = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."];

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
    return `${WT[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`;
  };
  const langDatum = (iso) => {
    const d = parseDay(iso);
    return `${WT_LANG[d.getDay()]}, ${d.getDate()}. ${MON[d.getMonth()]}`;
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
    return Number.isFinite(n) ? n.toLocaleString("de-DE", { style: "currency", currency: "EUR" }) : esc(p);
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
    if (ms <= 0) return "abgelaufen";
    const min = Math.round(ms / 60000);
    if (min < 60) return `noch ${min} Min.`;
    const h = Math.floor(min / 60);
    if (h < 48) return `noch ${h} Std.`;
    return `noch ${Math.floor(h / 24)} Tage`;
  };
  const zeitText = (ziel) =>
    `${WT[ziel.getDay()]} ${ziel.getDate()}.${ziel.getMonth() + 1}., ${String(ziel.getHours()).padStart(2, "0")}:${String(
      ziel.getMinutes()
    ).padStart(2, "0")} Uhr`;

  const art = (tag) => {
    if (!tag) return "leer";
    if (tag.feiertag) return "frei";
    if (tag.pause) return "pause";
    if (!tag.menues || !tag.menues.length) return "leer";
    if (tag.menues.some((m) => m.bestellt)) return "ok";
    return "offen";
  };
  const STATUS = {
    ok: ["Bestellt", "mdi:check-circle"],
    offen: ["Nicht bestellt", "mdi:alert-circle"],
    pause: ["Abbestellt", "mdi:minus-circle"],
    frei: ["Feiertag", "mdi:party-popper"],
    leer: ["Kein Speiseplan", "mdi:calendar-blank"],
  };

  class SchulessenCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._woche = 0;
      this._auswahl = null;
      this._sig = "";
    }

    static getStubConfig(hass) {
      const e = Object.keys(hass.states).find((k) => hass.states[k].attributes.schulessen_karte);
      return { entity: e || "", variante: "voll" };
    }

    setConfig(config) {
      if (!config.entity) throw new Error("Bitte die Stand-Entität der Schulessen-Integration angeben (entity).");
      this._config = { variante: "voll", ...config };
      this._sig = "";
      if (this._hass) this._render();
    }

    set hass(hass) {
      this._hass = hass;
      const st = hass.states[this._config?.entity];
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
      const st = this._hass.states[this._config.entity];
      return (st && st.attributes.tage) || [];
    }

    _aktualisieren() {
      this._hass.callService("homeassistant", "update_entity", { entity_id: this._config.entity });
      const b = this.shadowRoot.querySelector(".refresh");
      if (b) {
        b.classList.add("dreht");
        setTimeout(() => b.classList.remove("dreht"), 1200);
      }
    }

    _render() {
      if (!this._hass || !this._config) return;
      const st = this._hass.states[this._config.entity];
      if (!st) {
        this.shadowRoot.innerHTML = `<ha-card><div class="leerhinweis">Entität ${esc(this._config.entity)} nicht gefunden.</div></ha-card>`;
        return;
      }
      const a = st.attributes;
      const tage = this._tage();
      const heute = isoDay(new Date());
      const tagHeute = tage.find((t) => t.datum === heute);
      const jetzt = new Date();
      const nachAusgabe = jetzt.getHours() >= 14;
      let hero = tagHeute && art(tagHeute) !== "leer" && art(tagHeute) !== "frei" && !nachAusgabe ? tagHeute : null;
      let heroLabel = "Heute";
      if (!hero) {
        hero = tage.find((t) => t.datum > heute && art(t) !== "leer" && art(t) !== "frei") || null;
        const morgen = new Date();
        morgen.setDate(morgen.getDate() + 1);
        heroLabel = hero && hero.datum === isoDay(morgen) ? "Morgen" : "Nächster Schultag";
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
              <div class="kicker">Schulessen</div>
              <div class="name">${esc(titel)}</div>
              ${a.einrichtung ? `<div class="einrichtung">${esc(a.einrichtung)}</div>` : ""}
            </div>
            <div class="aktionen">
              <span class="pille ${live ? "live" : "cache"}" title="${stand ? "Stand " + stand.toLocaleString("de-DE") : ""}">
                <span class="punkt"></span>${live ? "Aktuell" : "Zwischenspeicher"}${
        stand ? ` · ${String(stand.getHours()).padStart(2, "0")}:${String(stand.getMinutes()).padStart(2, "0")}` : ""
      }
              </span>
              <button class="refresh" title="Jetzt aktualisieren" aria-label="Aktualisieren"><ha-icon icon="mdi:refresh"></ha-icon></button>
            </div>
          </header>
          ${this._heroHtml(hero, heroLabel)}
          ${this._offenHtml(offen, a.portal, kompakt)}
          ${kompakt ? "" : this._wocheHtml(tage, heute)}
          ${kompakt ? "" : this._detailHtml(tage)}
          ${!kompakt && a.portal ? `<footer><a class="link" href="${esc(a.portal)}" target="_blank" rel="noopener"><ha-icon icon="mdi:open-in-new"></ha-icon>Bestellportal öffnen</a></footer>` : ""}
        </ha-card>`;

      this.shadowRoot.querySelector(".refresh")?.addEventListener("click", () => this._aktualisieren());
      this.shadowRoot.querySelectorAll("[data-woche]").forEach((b) =>
        b.addEventListener("click", () => {
          this._woche = Math.max(0, Math.min(3, this._woche + Number(b.dataset.woche)));
          this._auswahl = null;
          this._render();
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
        return `<section class="hero leer"><div class="label">Demnächst</div><div class="gericht">Kein Speiseplan verfügbar</div></section>`;
      }
      const k = art(tag);
      const [stText, stIcon] = STATUS[k];
      const b = (tag.menues || []).find((m) => m.bestellt);
      const schluss = parseZeit(tag.bestellschluss);
      let gericht, text, chips = "", rechts = "";
      if (k === "ok") {
        gericht = esc(b.kurz || b.name);
        text = b.kurz && b.text ? esc(b.text) : b.text && b.text !== b.name ? esc(b.text) : "";
        chips = [`<span class="chip linie">${esc(b.name)}</span>`]
          .concat(b.kennzeichnung ? [`<span class="chip" title="Kennzeichnung">${esc(b.kennzeichnung)}</span>`] : [])
          .join("");
        rechts = b.preis !== null && b.preis !== undefined ? `<div class="preis">${preis(b.preis)}</div>` : "";
      } else if (k === "pause") {
        gericht = "Abbestellt";
        text = tag.pause_grund ? esc(tag.pause_grund) : "Für diesen Tag ist keine Versorgung vorgesehen.";
      } else {
        gericht = "Noch nichts bestellt";
        text = `${(tag.menues || []).length} Angebote zur Auswahl`;
      }
      return `
        <section class="hero ${k}">
          <div class="label">${label} <span class="datum">· ${langDatum(tag.datum)}</span></div>
          <div class="zeile">
            <div class="haupt">
              <div class="gericht">${gericht}</div>
              ${text ? `<div class="beschreibung">${text}</div>` : ""}
              ${chips ? `<div class="chips">${chips}</div>` : ""}
            </div>
            ${rechts}
          </div>
          <div class="fuss">
            <span class="status ${k}"><ha-icon icon="${stIcon}"></ha-icon>${stText}</span>
            ${schluss && k === "offen" ? `<span class="frist"><ha-icon icon="mdi:timer-sand"></ha-icon>Bestellschluss ${zeitText(schluss)} · ${restZeit(schluss)}</span>` : ""}
          </div>
        </section>`;
    }

    _offenHtml(offen, portal, kompakt) {
      if (!offen.length) {
        const sp = this._spanne === 1 ? "Morgen ist" : this._spanne ? `In den nächsten ${this._spanne} Tagen ist` : "Alle kommenden Schultage sind";
        return kompakt ? "" : `<div class="hinweis gut"><ha-icon icon="mdi:check-decagram"></ha-icon>${this._spanne ? sp + " alles bestellt." : sp + " versorgt."}</div>`;
      }
      const liste = offen.slice(0, kompakt ? 3 : 8).map((t) => kurzDatum(t.datum)).join(", ");
      const mehr = offen.length > (kompakt ? 3 : 8) ? ` und ${offen.length - (kompakt ? 3 : 8)} weitere` : "";
      return `
        <div class="hinweis warn">
          <ha-icon icon="mdi:bell-ring-outline"></ha-icon>
          <div class="hinweistext"><strong>${offen.length} ${offen.length === 1 ? "Schultag" : "Schultage"} ohne Bestellung${this._spanne ? (this._spanne === 1 ? " (morgen)" : ` (nächste ${this._spanne} Tage)`) : ""}</strong><span>${liste}${mehr}</span></div>
          ${portal ? `<a class="knopf" href="${esc(portal)}" target="_blank" rel="noopener">Bestellen</a>` : ""}
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
          k === "ok" ? esc(b.kurz || b.name) : k === "pause" ? "Abbestellt" : k === "frei" ? "Feiertag" : k === "offen" ? "Nicht bestellt" : k === "vorbei" ? "–" : "Kein Plan";
        zellen.push(`
          <button class="tag ${k} ${iso === heute ? "heute" : ""} ${this._auswahl === iso ? "aktiv" : ""}" data-tag="${iso}" ${t ? "" : "disabled"}>
            <span class="wt">${WT[d.getDay()]}</span>
            <span class="dt">${d.getDate()}.${d.getMonth() + 1}.</span>
            <span class="was">${inhalt}</span>
            ${b && b.name && (b.kurz || "") !== b.name ? `<span class="linie">${esc(b.name)}</span>` : ""}
          </button>`);
      }
      return `
        <section class="woche">
          <div class="wochenkopf">
            <button class="nav" data-woche="-1" ${this._woche === 0 ? "disabled" : ""} aria-label="Vorherige Woche"><ha-icon icon="mdi:chevron-left"></ha-icon></button>
            <div class="kw">KW ${kw(start)}<span>${this._woche === 0 ? (wochenende ? "Kommende Woche" : "Diese Woche") : this._woche === 1 && !wochenende ? "Nächste Woche" : `in ${this._woche + (wochenende ? 1 : 0)} Wochen`}</span></div>
            <button class="nav" data-woche="1" ${this._woche >= (wochenende ? 2 : 3) ? "disabled" : ""} aria-label="Nächste Woche"><ha-icon icon="mdi:chevron-right"></ha-icon></button>
          </div>
          <div class="tage">${zellen.join("")}</div>
        </section>`;
    }

    _detailHtml(tage) {
      if (!this._auswahl) return `<div class="tipp">Tag antippen für alle Angebote</div>`;
      const t = tage.find((x) => x.datum === this._auswahl);
      if (!t) return "";
      const k = art(t);
      if (k === "pause" || k === "frei") {
        return `<section class="detail"><div class="detailkopf">${langDatum(t.datum)}</div><div class="leise">${
          k === "frei" ? "Feiertag" : esc(t.pause_grund || "Abbestellt")
        }</div></section>`;
      }
      const schluss = parseZeit(t.bestellschluss);
      const menues = (t.menues || [])
        .map(
          (m) => `
          <div class="menue ${m.bestellt ? "gewaehlt" : ""}">
            <div class="mkopf">
              <span class="mname">${esc(m.name)}</span>
              ${m.bestellt ? `<span class="haken"><ha-icon icon="mdi:check"></ha-icon>bestellt</span>` : ""}
              <span class="mpreis">${preis(m.preis)}</span>
            </div>
            <div class="mtext">${esc(m.kurz && m.text ? m.text : m.text || m.kurz || "")}</div>
            ${m.kennzeichnung ? `<div class="mkenn">Kennzeichnung: ${esc(m.kennzeichnung)}</div>` : ""}
          </div>`
        )
        .join("");
      return `
        <section class="detail">
          <div class="detailkopf">${langDatum(t.datum)}${
        schluss ? `<span class="leise">Bestellschluss ${zeitText(schluss)}${schluss > new Date() ? " · " + restZeit(schluss) : ""}</span>` : ""
      }</div>
          ${menues || `<div class="leise">Keine Angebote</div>`}
        </section>`;
    }
  }

  const CSS = `
    :host { --se-akzent: var(--primary-color); --se-ok: var(--success-color, #2e7d32); --se-warn: var(--warning-color, #c77c02);
            --se-leise: var(--secondary-text-color); --se-linie: var(--divider-color, rgba(127,127,127,.18));
            --se-serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif; }
    ha-card { overflow: hidden; padding: 0;
              background-image: radial-gradient(130% 90% at 0% 0%, color-mix(in srgb, var(--se-akzent) 13%, transparent), transparent 55%); }
    header { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding:20px 22px 16px; }
    .kicker { font-size:11px; letter-spacing:.18em; text-transform:uppercase; color:var(--se-leise); font-weight:600; }
    .name { font-family:var(--se-serif); font-size:26px; line-height:1.15; margin-top:4px; color:var(--primary-text-color); }
    .einrichtung { font-size:13px; color:var(--se-leise); margin-top:3px; }
    .aktionen { display:flex; align-items:center; gap:6px; flex-shrink:0; }
    .pille { display:inline-flex; align-items:center; gap:6px; font-size:12px; padding:5px 10px; border-radius:999px;
             background: color-mix(in srgb, var(--primary-text-color) 6%, transparent); color:var(--se-leise); white-space:nowrap; }
    .punkt { width:7px; height:7px; border-radius:50%; background:var(--se-ok); box-shadow:0 0 0 3px color-mix(in srgb, var(--se-ok) 20%, transparent); }
    .pille.cache .punkt { background:var(--se-warn); box-shadow:0 0 0 3px color-mix(in srgb, var(--se-warn) 20%, transparent); }
    button { font:inherit; color:inherit; background:none; border:0; cursor:pointer; }
    .refresh { width:34px; height:34px; border-radius:50%; display:grid; place-items:center; color:var(--se-leise); transition:background .2s; }
    .refresh:hover { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); }
    .refresh ha-icon { --mdc-icon-size:20px; transition: transform 1.2s ease; }
    .refresh.dreht ha-icon { transform: rotate(360deg); }

    .hero { margin:0 16px; padding:18px 20px; border-radius:18px; border:1px solid var(--se-linie);
            background: var(--card-background-color, #fff); position:relative; box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 8px 24px -12px rgba(0,0,0,.12); }
    .hero.ok { border-color: color-mix(in srgb, var(--se-ok) 35%, var(--se-linie)); }
    .hero.offen { border-color: color-mix(in srgb, var(--se-warn) 45%, var(--se-linie)); }
    .label { font-size:12px; letter-spacing:.12em; text-transform:uppercase; font-weight:600; color:var(--se-akzent); }
    .label .datum { color:var(--se-leise); letter-spacing:.04em; text-transform:none; font-weight:500; }
    .zeile { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-top:8px; }
    .gericht { font-family:var(--se-serif); font-size:24px; line-height:1.25; color:var(--primary-text-color); }
    .beschreibung { margin-top:6px; font-size:14px; line-height:1.5; color:var(--se-leise); }
    .preis { font-family:var(--se-serif); font-size:20px; white-space:nowrap; color:var(--primary-text-color); }
    .chips { display:flex; flex-wrap:wrap; gap:6px; margin-top:10px; }
    .chip { font-size:11.5px; padding:3px 9px; border-radius:999px; border:1px solid var(--se-linie); color:var(--se-leise); }
    .chip.linie { color:var(--se-akzent); border-color: color-mix(in srgb, var(--se-akzent) 40%, transparent); }
    .fuss { display:flex; flex-wrap:wrap; gap:8px 16px; margin-top:14px; align-items:center; }
    .status, .frist { display:inline-flex; align-items:center; gap:6px; font-size:13px; font-weight:600; }
    .status ha-icon, .frist ha-icon { --mdc-icon-size:18px; }
    .status.ok { color:var(--se-ok); } .status.offen { color:var(--se-warn); } .status.pause, .status.leer, .status.frei { color:var(--se-leise); }
    .frist { color:var(--se-leise); font-weight:500; }

    .hinweis { display:flex; align-items:center; gap:12px; margin:12px 16px 0; padding:12px 14px; border-radius:14px; font-size:13.5px; }
    .hinweis ha-icon { --mdc-icon-size:22px; flex-shrink:0; }
    .hinweis.warn { background: color-mix(in srgb, var(--se-warn) 12%, transparent); color: var(--primary-text-color); }
    .hinweis.warn ha-icon { color: var(--se-warn); }
    .hinweis.gut { color: var(--se-leise); background: color-mix(in srgb, var(--se-ok) 7%, transparent); }
    .hinweis.gut ha-icon { color: var(--se-ok); }
    .hinweistext { display:flex; flex-direction:column; gap:2px; flex:1; min-width:0; }
    .hinweistext span { color:var(--se-leise); }
    .knopf { text-decoration:none; font-weight:600; font-size:13px; padding:8px 14px; border-radius:999px; white-space:nowrap;
             background: var(--se-warn); color: #fff; }

    .woche { margin:18px 16px 0; }
    .wochenkopf { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
    .kw { font-family:var(--se-serif); font-size:18px; display:flex; flex-direction:column; align-items:center; line-height:1.2; }
    .kw span { font-family: inherit; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--se-leise); font-family: var(--paper-font-body1_-_font-family, sans-serif); }
    .nav { width:34px; height:34px; border-radius:50%; display:grid; place-items:center; color:var(--se-leise); }
    .nav:hover:not([disabled]) { background: color-mix(in srgb, var(--primary-text-color) 8%, transparent); }
    .nav[disabled] { opacity:.3; cursor:default; }
    .tage { display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:8px; }
    .tag { text-align:left; padding:10px 10px 12px; border-radius:14px; border:1px solid var(--se-linie); min-height:96px;
           display:flex; flex-direction:column; gap:2px; transition: transform .15s, border-color .15s, background .15s; }
    .tag:hover:not([disabled]) { transform: translateY(-1px); border-color: color-mix(in srgb, var(--se-akzent) 45%, var(--se-linie)); }
    .tag[disabled] { cursor:default; opacity:.55; }
    .tag .wt { font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--se-leise); font-weight:600; }
    .tag .dt { font-family:var(--se-serif); font-size:17px; }
    .tag .was { font-size:12.5px; line-height:1.35; margin-top:4px; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
    .tag .linie { font-size:11px; color:var(--se-akzent); margin-top:auto; padding-top:4px; }
    .tag.ok { background: color-mix(in srgb, var(--se-ok) 6%, transparent); }
    .tag.ok .was { color: var(--primary-text-color); }
    .tag.offen { border-color: color-mix(in srgb, var(--se-warn) 50%, var(--se-linie)); background: color-mix(in srgb, var(--se-warn) 8%, transparent); }
    .tag.offen .was { color: var(--se-warn); font-weight:600; }
    .tag.pause .was, .tag.frei .was, .tag.leer .was, .tag.vorbei .was { color: var(--se-leise); }
    .tag.vorbei { opacity:.5; }
    .tag.heute { box-shadow: inset 0 0 0 1.5px var(--se-akzent); }
    .tag.aktiv { border-color: var(--se-akzent); background: color-mix(in srgb, var(--se-akzent) 10%, transparent); }

    .tipp { text-align:center; font-size:12px; color:var(--se-leise); margin:12px 16px 4px; }
    .detail { margin:14px 16px 0; padding:16px 18px; border-radius:16px; border:1px solid var(--se-linie); }
    .detailkopf { font-family:var(--se-serif); font-size:18px; display:flex; flex-wrap:wrap; gap:4px 12px; align-items:baseline; margin-bottom:6px; }
    .leise { font-size:12.5px; color:var(--se-leise); font-family: var(--paper-font-body1_-_font-family, sans-serif); }
    .menue { padding:12px 0; border-top:1px solid var(--se-linie); }
    .menue:first-of-type { border-top:0; }
    .mkopf { display:flex; align-items:center; gap:10px; }
    .mname { font-size:12px; letter-spacing:.1em; text-transform:uppercase; font-weight:700; color:var(--se-leise); }
    .menue.gewaehlt .mname { color: var(--se-ok); }
    .haken { display:inline-flex; align-items:center; gap:3px; font-size:11.5px; font-weight:600; color:var(--se-ok);
             padding:2px 8px; border-radius:999px; background: color-mix(in srgb, var(--se-ok) 12%, transparent); }
    .haken ha-icon { --mdc-icon-size:14px; }
    .mpreis { margin-left:auto; font-family:var(--se-serif); font-size:15px; }
    .mtext { font-size:14px; line-height:1.5; margin-top:4px; }
    .mkenn { font-size:12px; color:var(--se-leise); margin-top:4px; }

    footer { padding:14px 22px 18px; display:flex; justify-content:flex-end; }
    .link { display:inline-flex; align-items:center; gap:6px; font-size:13px; font-weight:600; text-decoration:none; color:var(--se-akzent); }
    .link ha-icon { --mdc-icon-size:16px; }
    ha-card > :last-child:not(footer) { margin-bottom:18px; }
    ha-card.kompakt .hero { margin-bottom:0; }
    ha-card.kompakt .gericht { font-size:21px; }
    .leerhinweis { padding:20px; color:var(--se-leise); }

    @media (max-width: 560px) {
      .tage { grid-template-columns: 1fr; }
      .tag { min-height:0; flex-direction:row; flex-wrap:wrap; align-items:baseline; gap:4px 10px; }
      .tag .was { flex-basis:100%; -webkit-line-clamp:2; margin-top:0; }
      .tag .linie { margin-top:0; padding-top:0; }
      .gericht { font-size:21px; }
      header { padding:18px 18px 14px; }
    }
  `;

  customElements.define(TAG, SchulessenCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === TAG)) {
    window.customCards.push({
      type: TAG,
      name: "Schulessen",
      description: "Speiseplan, Bestellstatus und Wochenübersicht der Schulessen-Integrationen",
      preview: false,
    });
  }
})();
