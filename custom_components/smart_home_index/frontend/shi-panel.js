// Smart Home Index sidebar panel. Plain web component, no build step.
const THUMB = (id) =>
  `https://smarthomeindex.com/api/fetchThumbnail?deviceId=${id}&w=96`;
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c],
  );
const stars = (n) =>
  `<span class="stars" title="SHI rating ${n}/5">${"★".repeat(n || 0)}<span class="off">${"★".repeat(5 - (n || 0))}</span></span>`;

const suggestUrl = (u, typed) =>
  `https://smarthomeindex.com/?suggest=${encodeURIComponent(typed || [u.manufacturer, u.model_id || u.model].filter(Boolean).join(" "))}&utm_source=home-assistant&utm_medium=integration&utm_campaign=suggest`;

class ShiPanel extends HTMLElement {
  set hass(h) {
    const first = !this._hass;
    this._hass = h;
    if (this._menu) this._menu.hass = h;
    if (first) this._load();
  }
  set narrow(n) {
    this._narrow = n;
    if (this._menu) this._menu.narrow = n;
  }

  async _load() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    try {
      this._r = await this._hass.callWS({ type: "smart_home_index/report" });
    } catch (e) {
      this.shadowRoot.innerHTML = `<p style="padding:24px">Smart Home Index is not loaded: ${esc(e.message)}</p>`;
      return;
    }
    this._render();
  }

  async _act(type, payload) {
    this._r = await this._hass.callWS({
      type: `smart_home_index/${type}`,
      ...payload,
    });
    this._pick = null;
    this._render();
  }

  _openPicker(deviceId) {
    const u = this._r.unmatched.find((x) => x.device_id === deviceId);
    this._pick = { u, query: "", results: [] };
    this._render();
    this._search("");
  }

  async _search(query) {
    const u = this._pick.u;
    const results = await this._hass.callWS({
      type: "smart_home_index/search",
      query,
      manufacturer: u.manufacturer,
      categories: u.categories,
      hints: u.hints,
    });
    if (!this._pick || this._pick.query !== query) return;
    this._pick.results = results;
    this._renderResults();
  }

  _renderResults() {
    const box = this.shadowRoot.getElementById("results");
    if (!box) return;
    const p = this._pick;
    box.innerHTML = p.results.length
      ? p.results
          .map(
            (
              d,
            ) => `<div class="row"><img class="t" referrerpolicy="no-referrer" src="${THUMB(d.id)}">
          <div class="grow"><div class="name">${esc(d.name)} ${stars(d.rating)}</div>
          <div class="meta">${esc(d.manufacturer)}${d.end_of_life ? ' · <span class="chip bad">End of life</span>' : ""}${!p.query && d.same_manufacturer ? " · same manufacturer" : ""}${!p.query && d.same_category ? " · same kind of device" : ""}</div></div>
          <button class="btn" data-link="${d.id}">This one</button></div>`,
          )
          .join("")
      : `<p class="sub" style="padding:12px 0">${p.query ? "Nothing in SHI matches that." : `SHI doesn't list anything from ${esc(p.u.manufacturer)} that looks like this. Search by product name, or suggest it.`}</p>`;
    box.querySelectorAll("[data-link]").forEach((b) =>
      b.addEventListener("click", () =>
        this._act("link", {
          device_id: p.u.device_id,
          shi_id: b.dataset.link,
        }),
      ),
    );
  }

  _picker() {
    const u = this._pick.u;
    return `<div class="scrim" id="scrim"><div class="dlg">
      <h2>Which SHI device is this?</h2>
      <p class="sub"><b>${esc(u.name)}</b> reports <b>${esc(u.manufacturer)} ${esc(u.model_id || u.model)}</b>. Pick the matching SHI record and every device reporting that model will link to it. The link is saved on this Home Assistant only.</p>
      <input id="q" type="search" placeholder="Search SHI, e.g. thermo-hygrometer" autocomplete="off">
      <div id="results"></div>
      <div class="dlgfoot"><span>Can't find it? <a class="lnk" id="suggest" target="_blank" href="${suggestUrl(u, "")}">Suggest it on Smart Home Index ↗</a></span><button class="btn quiet" id="cancel">Cancel</button></div></div></div>`;
  }

  _render() {
    const r = this._r;
    const eolCount = r.end_of_life.reduce((a, g) => a + g.count, 0);
    const tab = this._tab || "overview";
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; background: var(--primary-background-color); min-height:100vh; color: var(--primary-text-color); font-family: var(--ha-font-family-body, Roboto, sans-serif); }
        .toolbar { display:flex; align-items:center; height:56px; padding:0 12px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, white); font-size:20px; gap:8px; }
        .toolbar .title { flex:1; }
        .toolbar .src { font-size:12px; opacity:.8; }
        .tabs { display:flex; gap:4px; padding:0 16px; background: var(--app-header-background-color, var(--primary-color)); }
        .tabs button { background:none; border:none; color: var(--app-header-text-color, white); opacity:.7; padding:12px 16px; font-size:14px; cursor:pointer; border-bottom:2px solid transparent; font-family:inherit; }
        .tabs button.on { opacity:1; border-bottom-color: var(--app-header-text-color, white); }
        main { max-width:1100px; margin:0 auto; padding:16px; display:grid; gap:16px; }
        .tiles { display:grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap:16px; }
        .card { background: var(--card-background-color, white); border-radius: var(--ha-card-border-radius, 12px); border: 1px solid var(--divider-color, #e0e0e0); padding:16px; }
        .tile .n { font-size:36px; font-weight:500; }
        .tile .l { color: var(--secondary-text-color); font-size:14px; }
        .tile.warn .n { color: var(--warning-color, #ff9800); }
        h2 { font-size:18px; font-weight:500; margin:0 0 4px; }
        .sub { color: var(--secondary-text-color); font-size:14px; margin:0 0 12px; }
        .row { display:flex; align-items:center; gap:12px; padding:10px 0; border-top:1px solid var(--divider-color, #eee); }
        .row:first-of-type { border-top:none; }
        img.t { width:48px; height:48px; object-fit:contain; border-radius:8px; background: #fff; flex:none; }
        .grow { flex:1; min-width:0; }
        .name { font-weight:500; }
        .meta { color: var(--secondary-text-color); font-size:13px; }
        .arrow { color: var(--secondary-text-color); font-size:20px; }
        a.btn { color: var(--primary-color); text-decoration:none; font-weight:500; font-size:14px; white-space:nowrap; padding:6px 10px; border-radius:6px; border:1px solid var(--primary-color); }
        a.btn:hover { background: rgba(3,169,244,.08); }
        a.lnk { color: var(--primary-color); text-decoration:none; font-size:13px; }
        .chip { display:inline-block; font-size:12px; padding:2px 8px; border-radius:10px; background: var(--secondary-background-color, #eee); margin:2px 4px 2px 0; }
        .chip.bad { background: rgba(255,152,0,.18); color: var(--warning-color, #e65100); }
        .stars { color:#f5a623; letter-spacing:1px; } .stars .off { color: var(--disabled-text-color, #ccc); }
        .gap h3 { font-size:15px; margin:12px 0 4px; font-weight:500; }
        .why { margin-top:2px; }
        table { width:100%; border-collapse:collapse; font-size:14px; }
        td, th { text-align:left; padding:8px 6px; border-top:1px solid var(--divider-color, #eee); }
        th { color: var(--secondary-text-color); font-weight:500; border-top:none; }
        .foot { color: var(--secondary-text-color); font-size:12px; text-align:center; padding:8px 0 24px; }
        .bar { height:8px; border-radius:4px; background: var(--secondary-background-color, #eee); overflow:hidden; margin-top:8px; }
        .bar > div { height:100%; background: var(--primary-color); }
        .scroll { overflow-x:auto; }
        button.btn { font-family:inherit; color: var(--primary-color); background:none; font-weight:500; font-size:14px; white-space:nowrap; padding:6px 10px; border-radius:6px; border:1px solid var(--primary-color); cursor:pointer; }
        button.btn:hover { background: rgba(3,169,244,.08); }
        button.btn.quiet { color: var(--secondary-text-color); border-color: var(--divider-color, #ccc); }
        .acts { display:flex; gap:6px; align-items:center; justify-content:flex-end; flex-wrap:wrap; }
        .dlgfoot { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-top:12px; padding-top:12px; border-top:1px solid var(--divider-color, #eee); font-size:14px; flex-wrap:wrap; }
        .scrim { position:fixed; inset:0; background: rgba(0,0,0,.5); display:flex; align-items:flex-start; justify-content:center; padding-top:8vh; z-index:10; }
        .dlg { background: var(--card-background-color, white); border-radius: var(--ha-card-border-radius, 12px); padding:20px; width:min(560px, 92vw); max-height:80vh; overflow:auto; box-shadow: 0 8px 32px rgba(0,0,0,.4); }
        input[type=search] { width:100%; box-sizing:border-box; padding:10px 12px; font-size:16px; border-radius:8px; border:1px solid var(--divider-color, #ccc); background: var(--secondary-background-color, #f5f5f5); color: var(--primary-text-color); font-family:inherit; margin-bottom:8px; }
        @media (max-width: 600px) {
          main { padding:8px; gap:8px; }
          .toolbar .src { display:none; }
          .tabs { overflow-x:auto; padding:0 4px; } .tabs button { padding:12px 10px; white-space:nowrap; }
          .tile .n { font-size:28px; }
          .row { flex-wrap:wrap; }
          .row .grow { flex:1 1 calc(100% - 64px); }
          .row .arrow { display:none; }
          .row a.btn { margin-left:60px; }
          .meta { word-break:break-word; }
        }
      </style>
      <div class="toolbar"><span id="menu"></span><span class="title">Smart Home Index</span><span class="src">Catalog of ${r.catalog_size} devices${r.catalog.fetched_at ? ", updated " + esc(r.catalog.fetched_at.slice(0, 10)) : ""}</span></div>
      <div class="tabs">${["overview", "devices", "ideas", "unmatched"].map((t) => `<button data-tab="${t}" class="${t === tab ? "on" : ""}">${{ overview: "Overview", devices: "Your devices", ideas: "Ideas", unmatched: `Not in SHI yet (${r.unmatched.length})` }[t]}</button>`).join("")}</div>
      <main>${this[`_${tab}`](r, eolCount)}</main>
      ${this._pick ? this._picker() : ""}
      <div class="foot">Matching ran on this Home Assistant. Your device list was not sent anywhere. Links open smarthomeindex.com.</div>`;
    const slot = this.shadowRoot.getElementById("menu");
    const menu = document.createElement("ha-menu-button");
    menu.hass = this._hass;
    menu.narrow = this._narrow;
    this._menu = menu;
    slot.appendChild(menu);
    this.shadowRoot
      .querySelectorAll("[data-pick]")
      .forEach((b) =>
        b.addEventListener("click", () => this._openPicker(b.dataset.pick)),
      );
    this.shadowRoot
      .querySelectorAll("[data-ignore]")
      .forEach((b) =>
        b.addEventListener("click", () =>
          this._act("ignore", { device_id: b.dataset.ignore }),
        ),
      );
    this.shadowRoot
      .querySelectorAll("[data-unignore]")
      .forEach((b) =>
        b.addEventListener("click", () =>
          this._act("unignore", { device_id: b.dataset.unignore }),
        ),
      );
    this.shadowRoot
      .querySelectorAll("[data-unlink]")
      .forEach((b) =>
        b.addEventListener("click", () =>
          this._act("unlink", { link_key: b.dataset.unlink }),
        ),
      );
    if (this._pick) {
      const q = this.shadowRoot.getElementById("q");
      q.focus();
      let t;
      q.addEventListener("input", () => {
        this.shadowRoot.getElementById("suggest").href = suggestUrl(
          this._pick.u,
          q.value.trim(),
        );
        clearTimeout(t);
        t = setTimeout(() => {
          this._pick.query = q.value.trim();
          this._search(this._pick.query);
        }, 200);
      });
      this.shadowRoot.getElementById("cancel").addEventListener("click", () => {
        this._pick = null;
        this._render();
      });
      this.shadowRoot.getElementById("scrim").addEventListener("click", (e) => {
        if (e.target.id === "scrim") {
          this._pick = null;
          this._render();
        }
      });
      this._renderResults();
    }
    this.shadowRoot.querySelectorAll(".tabs button").forEach((b) =>
      b.addEventListener("click", () => {
        this._tab = b.dataset.tab;
        this._render();
      }),
    );
  }

  _overview(r, eolCount) {
    const pct = Math.round(
      (100 * r.matched.length) / Math.max(r.considered, 1),
    );
    return `
      <div class="tiles">
        <div class="card tile"><div class="n">${r.matched.length}<span style="font-size:18px;color:var(--secondary-text-color)"> / ${r.considered}</span></div><div class="l">devices matched to SHI</div><div class="bar"><div style="width:${pct}%"></div></div></div>
        <div class="card tile warn"><div class="n">${eolCount}</div><div class="l">end of life, across ${r.end_of_life.length} models</div></div>
        <div class="card tile"><div class="n">${r.gaps.length}</div><div class="l">categories you could add</div></div>
        <div class="card tile"><div class="n" style="font-size:20px;padding:10px 0">${r.protocols
          .slice(0, 3)
          .map((p) => `<span class="chip">${esc(p)}</span>`)
          .join("")}</div><div class="l">protocols your home speaks</div></div>
      </div>
      ${this._eol(r)}`;
  }

  _eol(r) {
    if (!r.end_of_life.length)
      return `<div class="card"><h2>End of life</h2><p class="sub">Nothing you own is discontinued.</p></div>`;
    return `<div class="card"><h2>End of life</h2><p class="sub">Discontinued models in your home and what replaced them. They still work; they just won't get new firmware.</p>
      ${r.end_of_life
        .map((g) => {
          const rep = g.replacements[0];
          return `<div class="row">
          <img class="t" referrerpolicy="no-referrer" src="${THUMB(g.shi_id)}">
          <div class="grow"><div class="name">${esc(g.shi_name)} ${stars(g.rating)}</div><div class="meta">${g.count} in use: ${esc(g.devices.join(", "))}</div></div>
          ${
            rep
              ? `<span class="arrow">→</span><img class="t" referrerpolicy="no-referrer" src="${THUMB(rep.id)}">
          <div class="grow"><div class="name">${esc(rep.name)} ${stars(rep.rating)}</div><div class="meta">Successor</div></div>
          <a class="btn" target="_blank" href="${g.compare_url}">Compare on SHI</a>`
              : `<a class="btn" target="_blank" href="${g.url}">View on SHI</a>`
          }
        </div>`;
        })
        .join("")}</div>`;
  }

  _devices(r) {
    const rows = [...r.matched].sort(
      (a, b) =>
        b.end_of_life - a.end_of_life || a.shi_name.localeCompare(b.shi_name),
    );
    return `<div class="card"><h2>Your devices on Smart Home Index</h2><p class="sub">Each matched device, its SHI rating for local control, and where to read more.</p>
      <div class="scroll"><table><tr><th></th><th>Your name</th><th>SHI device</th><th>Rating</th><th>Status</th><th></th></tr>
      ${rows
        .map(
          (
            m,
          ) => `<tr><td><img class="t" style="width:36px;height:36px" referrerpolicy="no-referrer" src="${THUMB(m.shi_id)}"></td>
        <td>${esc(m.name)}<div class="meta">${esc(m.integration)}${m.sw_version ? " · fw " + esc(m.sw_version) : ""}</div></td>
        <td>${esc(m.shi_name)}<div class="meta">matched by ${esc(m.matched_by)}</div></td><td>${stars(m.rating)}</td>
        <td>${m.end_of_life ? `<span class="chip bad">End of life</span>` : `<span class="chip">Current</span>`}</td>
        <td><a class="lnk" target="_blank" href="${m.url}">SHI ↗</a>${m.notes_url ? `<br><a class="lnk" target="_blank" href="${m.notes_url}">Notes ↗</a>` : ""}${m.matched_by === "your link" ? `<br><a class="lnk" href="#" data-unlink="${esc(m.link_key)}" onclick="return false">Unlink</a>` : ""}</td></tr>`,
        )
        .join("")}</table></div></div>`;
  }

  _ideas(r) {
    return `<div class="card gap"><h2>Ideas for your home</h2><p class="sub">Categories with nothing in your home yet, filled with the highest-rated devices that speak ${esc(r.protocols.slice(0, 2).join(" or "))} and need no extra hub.</p>
      ${r.gaps
        .map(
          (g) =>
            `<h3>${esc(g.category)}</h3>${g.suggestions
              .map(
                (s) => `<div class="row">
        <img class="t" referrerpolicy="no-referrer" src="${THUMB(s.id)}">
        <div class="grow"><div class="name">${esc(s.name)} ${stars(s.rating)}</div><div class="why">${s.why.map((w) => `<span class="chip">${esc(w)}</span>`).join("")}</div></div>
        <a class="btn" target="_blank" href="${s.url}">View on SHI</a></div>`,
              )
              .join("")}`,
        )
        .join("")}</div>`;
  }

  _unmatched(r) {
    return `<div class="card"><h2>Not in Smart Home Index yet</h2><p class="sub">SHI could not match these. Link a device to its SHI record if you know which one it is, or ignore it if SHI will never list it. Links and ignores are saved on this Home Assistant only. Diagnostics on the integration page lists the links, so you can send them to SHI.</p>
      <div class="scroll"><table><tr><th>Your name</th><th>Manufacturer</th><th>Model reported</th><th>Integration</th><th></th></tr>
      ${r.unmatched
        .map(
          (
            u,
          ) => `<tr><td>${esc(u.name)}</td><td>${esc(u.manufacturer)}</td><td>${esc(u.model_id || u.model)}</td><td>${esc(u.integration)}</td>
        <td><div class="acts"><button class="btn" data-pick="${u.device_id}">Link…</button><button class="btn quiet" data-ignore="${u.device_id}">Ignore</button></div></td></tr>`,
        )
        .join("")}</table></div></div>
      ${
        r.ignored.length
          ? `<div class="card"><h2>Ignored (${r.ignored.length})</h2><p class="sub">Not counted anywhere. Restore one to match it again.</p>
      <div class="scroll"><table><tr><th>Your name</th><th>Manufacturer</th><th>Model reported</th><th>Integration</th><th></th></tr>
      ${r.ignored
        .map(
          (
            u,
          ) => `<tr><td>${esc(u.name)}</td><td>${esc(u.manufacturer)}</td><td>${esc(u.model_id || u.model)}</td><td>${esc(u.integration)}</td>
        <td><div class="acts"><button class="btn quiet" data-unignore="${u.device_id}">Restore</button></div></td></tr>`,
        )
        .join("")}</table></div></div>`
          : ""
      }`;
  }
}
if (!customElements.get("shi-panel"))
  customElements.define("shi-panel", ShiPanel);
