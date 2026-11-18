// Move Device sidebar panel. Plain web component, no build step.
//
// 1. Pick devices (filter by area, search). 2. Pick the area they move to and
// how names change. 3. Preview: every name and entity ID can be edited or
// left alone, linked devices can be left behind, and the automations,
// scripts, scenes and helpers that use the old IDs are listed. 4. Move.
//
// Move Device never edits an automation, script, scene or helper. What uses
// an old entity ID is listed before and after the move, split into
// "Needs updating in the editor" (with a link that opens it in the Home
// Assistant editor) and "Change by hand" (helpers and YAML outside the
// editor), with the old -> new entity ID for each.

const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );

const KIND_LABEL = {
  automation: "Automation",
  script: "Script",
  scene: "Scene",
  helper: "Helper",
};

const editUrl = (ref) => {
  if (ref.kind === "helper") return `/config/integrations/integration/${ref.domain}`;
  if (ref.item_id) return `/config/${ref.kind}/edit/${ref.item_id}`;
  return null;
};

// Made in the Home Assistant editor, so the link opens it there.
const inEditor = (ref) => ref.in_editor && ref.kind !== "helper" && !!ref.item_id;

class MoveDevicePanel extends HTMLElement {
  constructor() {
    super();
    this._selected = new Set();
    this._fromArea = "";
    this._search = "";
    this._toArea = "";
    this._options = {
      include_linked: true,
      rename_devices: true,
      rename_entity_names: true,
      rename_entity_ids: true,
      find: "",
      replace: "",
    };
    this._preview = null;
    this._edits = { devices: {}, entities: {}, skip: new Set() };
    this._busy = false;
    this._error = "";
    this._result = null;
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._render();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
  }

  // ---- data -------------------------------------------------------------

  _areas() {
    return Object.values(this._hass?.areas || {}).sort((a, b) =>
      (a.name || "").localeCompare(b.name || ""),
    );
  }

  _areaName(id) {
    return id ? this._hass?.areas?.[id]?.name || id : "No area";
  }

  _deviceName(device) {
    return device.name_by_user || device.name || device.id;
  }

  _devices() {
    const search = this._search.trim().toLowerCase();
    return Object.values(this._hass?.devices || {})
      .filter((d) => d.entry_type !== "service" || this._selected.has(d.id))
      .filter((d) => !this._fromArea || (this._fromArea === "-" ? !d.area_id : d.area_id === this._fromArea))
      .filter((d) => {
        if (!search) return true;
        const text = [this._deviceName(d), d.manufacturer, d.model, this._areaName(d.area_id)]
          .join(" ")
          .toLowerCase();
        return text.includes(search);
      })
      .sort((a, b) => this._deviceName(a).localeCompare(this._deviceName(b)));
  }

  async _call(message) {
    return this._hass.connection.sendMessagePromise(message);
  }

  // ---- actions ----------------------------------------------------------

  async _runPreview() {
    if (!this._selected.size || !this._toArea) return;
    this._busy = true;
    this._error = "";
    this._result = null;
    this._render();
    try {
      this._preview = await this._call({
        type: "move_device/preview",
        device_ids: [...this._selected],
        area_id: this._toArea,
        options: this._options,
      });
      this._edits = { devices: {}, entities: {}, skip: new Set() };
    } catch (err) {
      this._error = err?.message || String(err);
      this._preview = null;
    }
    this._busy = false;
    this._render();
  }

  _deviceValue(row) {
    return this._edits.devices[row.device_id] ?? row.new_name ?? row.name;
  }

  _entityValue(row, key) {
    const edit = this._edits.entities[row.entity_id] || {};
    if (key === "id") return edit.id ?? row.new_entity_id ?? row.entity_id;
    return edit.name ?? row.new_name ?? row.name ?? "";
  }

  _renames() {
    const renames = {};
    for (const device of this._preview?.devices || []) {
      if (this._edits.skip.has(device.device_id)) continue;
      for (const entity of device.entities) {
        const id = this._entityValue(entity, "id").trim();
        if (id && id !== entity.entity_id) renames[entity.entity_id] = id;
      }
    }
    return renames;
  }

  _problems() {
    const problems = [];
    const seen = new Map();
    const known = new Set(Object.keys(this._hass?.states || {}));
    for (const device of this._preview?.devices || []) {
      if (this._edits.skip.has(device.device_id)) continue;
      for (const entity of device.entities) {
        const id = this._entityValue(entity, "id").trim();
        if (!id || id === entity.entity_id) continue;
        const domain = entity.entity_id.split(".")[0];
        if (!/^[a-z0-9_]+\.[a-z0-9_]+$/.test(id) || id.split(".")[0] !== domain || /\._|_$/.test(id)) {
          problems.push(`${id} isn't a valid ${domain} entity ID.`);
        } else if (seen.has(id) || known.has(id)) {
          problems.push(`${id} is already used.`);
        }
        seen.set(id, entity.entity_id);
      }
    }
    return problems;
  }

  async _apply() {
    const preview = this._preview;
    if (!preview || this._problems().length) return;
    const devices = [];
    const entities = [];
    for (const device of preview.devices) {
      if (this._edits.skip.has(device.device_id)) continue;
      devices.push({ device_id: device.device_id, new_name: this._deviceValue(device) });
      for (const entity of device.entities) {
        const item = { entity_id: entity.entity_id };
        const id = this._entityValue(entity, "id").trim();
        if (id !== entity.entity_id) item.new_entity_id = id;
        const name = this._entityValue(entity, "name");
        if (name !== (entity.name ?? "")) item.new_name = name;
        if (item.new_entity_id || "new_name" in item) entities.push(item);
      }
    }
    this._busy = true;
    this._error = "";
    this._render();
    try {
      this._result = await this._call({
        type: "move_device/apply",
        area_id: preview.area_id,
        devices,
        entities,
      });
      this._preview = null;
      this._selected.clear();
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._busy = false;
    this._render();
  }

  // ---- rendering --------------------------------------------------------

  _render() {
    if (!this._hass || !this.shadowRoot) return;
    const focused = this.shadowRoot.activeElement;
    const focusKey = focused?.dataset?.key;
    const caret = focused?.selectionStart;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <h1>Move Device</h1>
      </div>
      <main>
        ${this._error ? `<div class="error">${esc(this._error)}</div>` : ""}
        ${this._result ? this._renderResult() : ""}
        ${this._renderPick()}
        ${this._renderTarget()}
        ${this._preview ? this._renderPreview() : ""}
      </main>`;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
    this._bind();
    if (focusKey) {
      const el = this.shadowRoot.querySelector(`[data-key="${CSS.escape(focusKey)}"]`);
      if (el) {
        el.focus();
        if (caret != null && el.setSelectionRange) el.setSelectionRange(caret, caret);
      }
    }
  }

  _renderPick() {
    const devices = this._devices();
    const areas = this._areas();
    return `<section class="card">
      <h2>1. Devices to move</h2>
      <div class="row">
        <label>From area
          <select data-key="from">
            <option value="">Any area</option>
            <option value="-" ${this._fromArea === "-" ? "selected" : ""}>No area</option>
            ${areas.map((a) => `<option value="${esc(a.area_id)}" ${a.area_id === this._fromArea ? "selected" : ""}>${esc(a.name)}</option>`).join("")}
          </select>
        </label>
        <label class="grow">Search
          <input data-key="search" type="search" placeholder="Name, maker, model" value="${esc(this._search)}">
        </label>
      </div>
      <p class="muted">${this._selected.size} picked.
        ${devices.length ? `<button class="link" data-act="all">Pick all shown</button>` : ""}
        ${this._selected.size ? `<button class="link" data-act="none">Clear</button>` : ""}</p>
      <div class="list">
        ${devices.length
          ? devices
              .map(
                (d) => `<label class="item">
                  <input type="checkbox" data-device="${esc(d.id)}" ${this._selected.has(d.id) ? "checked" : ""}>
                  <span><strong>${esc(this._deviceName(d))}</strong>
                  <small>${esc(this._areaName(d.area_id))}${d.manufacturer || d.model ? " · " + esc([d.manufacturer, d.model].filter(Boolean).join(" ")) : ""}</small></span>
                </label>`,
              )
              .join("")
          : `<p class="muted">No devices match.</p>`}
      </div>
    </section>`;
  }

  _renderTarget() {
    const o = this._options;
    const check = (key, label, help) => `<label class="check">
        <input type="checkbox" data-opt="${key}" ${o[key] ? "checked" : ""}>
        <span>${label}${help ? `<small>${help}</small>` : ""}</span></label>`;
    return `<section class="card">
      <h2>2. Moving to</h2>
      <label>Area
        <select data-key="to">
          <option value="">Choose an area</option>
          ${this._areas().map((a) => `<option value="${esc(a.area_id)}" ${a.area_id === this._toArea ? "selected" : ""}>${esc(a.name)}</option>`).join("")}
        </select>
      </label>
      ${check("include_linked", "Move linked devices too", "Devices Home Assistant shows under Linked devices, such as the same hardware from another integration.")}
      ${check("rename_devices", "Rename devices")}
      ${check("rename_entity_names", "Rename entities", "Only entities with a name of their own; the rest show the device's name.")}
      ${check("rename_entity_ids", "Change entity IDs", "For example light.kitchen_lamp to light.office_lamp.")}
      <div class="row">
        <label class="grow">Find
          <input data-key="find" data-text="find" placeholder="The old area's name and aliases" value="${esc(o.find)}">
        </label>
        <label class="grow">Replace with
          <input data-key="replace" data-text="replace" placeholder="The new area's name" value="${esc(o.replace)}">
        </label>
      </div>
      <p class="muted">Whole words only, ignoring case. The old area's name and its aliases are always found; add other words in Find (for example a nickname). You can change every suggestion in the preview.</p>
      <button class="primary" data-act="preview" ${!this._selected.size || !this._toArea || this._busy ? "disabled" : ""}>Preview</button>
    </section>`;
  }

  _renderPreview() {
    const p = this._preview;
    const renames = this._renames();
    const problems = this._problems();
    const refs = (p.references || [])
      .map((r) => ({ ...r, uses: r.uses.filter((id) => id in renames) }))
      .filter((r) => r.uses.length);
    const moving = p.devices.filter((d) => !this._edits.skip.has(d.device_id));
    const deviceName = (id) => p.devices.find((d) => d.device_id === id)?.name || id;
    return `<section class="card">
      <h2>3. Check the changes</h2>
      <p class="muted">Moving ${moving.length} device${moving.length === 1 ? "" : "s"} to <strong>${esc(p.area_name)}</strong>. Edit any name or entity ID, or clear a box to leave it as it is.</p>
      ${p.devices
        .map((d) => {
          const skipped = this._edits.skip.has(d.device_id);
          return `<div class="device ${skipped ? "skipped" : ""}">
            <div class="device-head">
              <label class="check"><input type="checkbox" data-move="${esc(d.device_id)}" ${skipped ? "" : "checked"}>
                <span><strong>${esc(d.name)}</strong>
                <small>${esc(d.area_name || "No area")} → ${esc(p.area_name)}${d.already_there ? " (already there)" : ""}${d.linked_to ? ` · linked to ${esc(deviceName(d.linked_to))}` : ""}</small></span>
              </label>
            </div>
            ${skipped ? "" : `<label>Device name
              <input data-key="dev:${esc(d.device_id)}" data-devname="${esc(d.device_id)}" value="${esc(this._deviceValue(d))}">
              ${d.new_name ? `<small class="muted">Was ${esc(d.name)}</small>` : ""}
            </label>
            ${d.entities.length ? `<table>
              <thead><tr><th>Entity</th><th>Name</th><th>Entity ID</th></tr></thead>
              <tbody>${d.entities.map((e) => this._entityRow(e)).join("")}</tbody>
            </table>` : `<p class="muted">No entities.</p>`}`}
          </div>`;
        })
        .join("")}
    </section>
    <section class="card">
      <h2>4. What uses the old entity IDs</h2>
      ${refs.length
        ? `<p class="muted">Move Device doesn't change these. After the move, open each one and switch it to the new entity ID. They're listed again when the move is done.</p>
          ${this._renderRefs(refs, (id) => renames[id])}`
        : `<p class="muted">Nothing found using the entity IDs that change. Dashboards aren't checked: look over any cards that show these devices.</p>`}
      ${(p.area_targets || []).length
        ? `<h3>Area targets</h3><ul class="refs">${p.area_targets
            .map(
              (t) => `<li><span class="badge info">${t.leaving ? "Leaves" : "Joins"}</span>
              <strong>${esc(KIND_LABEL[t.kind] || t.kind)}: ${esc(t.name)}</strong>
              <small>targets ${esc(this._areaName(t.area_id))}, so ${t.leaving ? "it won't include the moved devices any more" : "it will include the moved devices"}</small></li>`,
            )
            .join("")}</ul>`
        : ""}
      ${problems.length ? `<div class="error">${problems.map(esc).join("<br>")}</div>` : ""}
      <button class="primary" data-act="apply" ${this._busy || problems.length || !moving.length ? "disabled" : ""}>Move ${moving.length} device${moving.length === 1 ? "" : "s"}</button>
      <button class="link" data-act="reset">Back to the suggestions</button>
    </section>`;
  }

  _entityRow(e) {
    const id = this._entityValue(e, "id");
    const name = this._entityValue(e, "name");
    const named = e.name != null || e.new_name != null;
    return `<tr class="${e.conflict && id === e.new_entity_id ? "conflict" : ""}">
      <td>${esc(e.shown_name)}${e.disabled ? ' <small class="muted">(disabled)</small>' : ""}${e.area_moves ? ' <small class="muted">(area moves too)</small>' : ""}</td>
      <td>${named
        ? `<input data-key="en:${esc(e.entity_id)}" data-entname="${esc(e.entity_id)}" value="${esc(name)}">`
        : `<small class="muted">Device's name</small>`}</td>
      <td><input data-key="ei:${esc(e.entity_id)}" data-entid="${esc(e.entity_id)}" value="${esc(id)}">
        ${id !== e.entity_id ? `<small class="muted">Was ${esc(e.entity_id)}</small>` : ""}
        ${e.conflict && id === e.new_entity_id ? `<small class="bad">Already used; change it or put back ${esc(e.entity_id)}</small>` : ""}</td>
    </tr>`;
  }

  // The automations, scripts, scenes and helpers that use an old entity ID,
  // in two groups. `newId(old)` returns the ID it is being renamed to.
  _renderRefs(refs, newId) {
    const editor = refs.filter(inEditor);
    const byHand = refs.filter((r) => !inEditor(r));
    const item = (r, badge, linkText) => {
      const url = editUrl(r);
      const label = `${esc(KIND_LABEL[r.kind] || r.kind)}: ${esc(r.name)}`;
      return `<li><strong>${label}</strong>
        <small>${r.uses.map((id) => `${esc(id)} → <code>${esc(newId(id) || id)}</code>`).join(", ")}</small>
        ${url ? `<a class="open" href="${esc(url)}" target="_blank" rel="noreferrer">${linkText}</a>` : `<span class="badge ${badge}">Not made in the editor</span>`}</li>`;
    };
    return `${editor.length
        ? `<h3><span class="badge warn">Needs updating in the editor</span> ${editor.length}</h3>
          <p class="muted">Made in the Home Assistant editor. Open each one and change the old entity ID to the new one, then save.</p>
          <ul class="refs">${editor.map((r) => item(r, "warn", "Open in the editor")).join("")}</ul>`
        : ""}
      ${byHand.length
        ? `<h3><span class="badge">Change by hand</span> ${byHand.length}</h3>
          <p class="muted">Helpers, and automations, scripts or scenes kept in your own YAML files (packages or includes). Change the entity ID where they're set up.</p>
          <ul class="refs">${byHand.map((r) => item(r, "", r.kind === "helper" ? "Open the integration" : "Open")).join("")}</ul>`
        : ""}`;
  }

  _renderResult() {
    const r = this._result;
    const refs = r.needs_updating || [];
    // old entity ID -> new one, from the entities the move renamed.
    const renamed = Object.fromEntries(r.renamed_entities.map((e) => [e.entity_id, e.new_entity_id]));
    return `<section class="card done">
      <h2>Moved ${r.moved.length} device${r.moved.length === 1 ? "" : "s"} to ${esc(this._areaName(r.area_id))}</h2>
      ${r.renamed_entities.length ? `<p>${r.renamed_entities.length} entit${r.renamed_entities.length === 1 ? "y" : "ies"} renamed.</p>` : ""}
      ${refs.length
        ? `<p><strong>Still using the old entity IDs.</strong> Move Device didn't change these; update each one to the new entity ID.</p>
          ${this._renderRefs(refs, (id) => renamed[id])}`
        : r.renamed_entities.length
          ? `<p class="muted">Nothing found that uses the old entity IDs. Dashboards aren't checked: look over any cards that show these devices.</p>`
          : ""}
      <button class="link" data-act="dismiss">Done</button>
    </section>`;
  }

  _bind() {
    const root = this.shadowRoot;
    const on = (selector, event, handler) =>
      root.querySelectorAll(selector).forEach((el) => el.addEventListener(event, handler));

    on('[data-key="from"]', "change", (ev) => {
      this._fromArea = ev.target.value;
      this._render();
    });
    on('[data-key="search"]', "input", (ev) => {
      this._search = ev.target.value;
      this._render();
    });
    on("[data-device]", "change", (ev) => {
      const id = ev.target.dataset.device;
      if (ev.target.checked) this._selected.add(id);
      else this._selected.delete(id);
      this._preview = null;
      this._render();
    });
    on('[data-key="to"]', "change", (ev) => {
      this._toArea = ev.target.value;
      this._preview = null;
      this._render();
    });
    on("[data-opt]", "change", (ev) => {
      this._options[ev.target.dataset.opt] = ev.target.checked;
      this._preview = null;
      this._render();
    });
    on("[data-text]", "change", (ev) => {
      this._options[ev.target.dataset.text] = ev.target.value;
      this._preview = null;
      this._render();
    });
    on("[data-move]", "change", (ev) => {
      const id = ev.target.dataset.move;
      if (ev.target.checked) this._edits.skip.delete(id);
      else this._edits.skip.add(id);
      this._render();
    });
    on("[data-devname]", "change", (ev) => {
      this._edits.devices[ev.target.dataset.devname] = ev.target.value;
    });
    on("[data-entname]", "change", (ev) => {
      const id = ev.target.dataset.entname;
      this._edits.entities[id] = { ...this._edits.entities[id], name: ev.target.value };
    });
    on("[data-entid]", "change", (ev) => {
      const id = ev.target.dataset.entid;
      this._edits.entities[id] = { ...this._edits.entities[id], id: ev.target.value.trim().toLowerCase() };
      this._render();
    });
    on("[data-act]", "click", (ev) => {
      const act = ev.currentTarget.dataset.act;
      if (act === "all") this._devices().forEach((d) => this._selected.add(d.id));
      if (act === "none") this._selected.clear();
      if (act === "preview") return this._runPreview();
      if (act === "apply") return this._apply();
      if (act === "reset") this._edits = { devices: {}, entities: {}, skip: new Set() };
      if (act === "dismiss") this._result = null;
      if (act === "all" || act === "none") this._preview = null;
      this._render();
    });
  }
}

const STYLE = `
  :host { display: block; background: var(--primary-background-color); min-height: 100vh; color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
  .toolbar { display: flex; align-items: center; gap: 8px; height: var(--header-height, 56px); padding: 0 12px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); }
  .toolbar h1 { font-size: 20px; font-weight: 400; margin: 0; }
  main { max-width: 1000px; margin: 0 auto; padding: 16px; display: grid; gap: 16px; }
  .card { background: var(--card-background-color); border-radius: var(--ha-card-border-radius, 12px); box-shadow: var(--ha-card-box-shadow, none); border: 1px solid var(--divider-color); padding: 16px; display: grid; gap: 12px; }
  .card.done { border-color: var(--success-color, #43a047); }
  h2 { margin: 0; font-size: 18px; font-weight: 500; }
  h3 { margin: 8px 0 0; font-size: 15px; font-weight: 500; }
  label { display: grid; gap: 4px; font-size: 14px; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; }
  .grow { flex: 1 1 200px; }
  input, select { font: inherit; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--secondary-background-color, transparent); color: var(--primary-text-color); min-width: 0; }
  input[type="checkbox"] { width: 20px; height: 20px; padding: 0; accent-color: var(--primary-color); flex: none; }
  .check { display: flex; gap: 10px; align-items: flex-start; }
  .check span, .item span { display: grid; gap: 2px; }
  small { font-size: 12px; color: var(--secondary-text-color); }
  .muted { color: var(--secondary-text-color); margin: 0; font-size: 13px; }
  .list { max-height: 360px; overflow: auto; display: grid; gap: 2px; border: 1px solid var(--divider-color); border-radius: 8px; padding: 4px; }
  .item { display: flex; gap: 10px; align-items: center; padding: 6px 8px; border-radius: 6px; cursor: pointer; }
  .item:hover { background: var(--secondary-background-color); }
  button { font: inherit; cursor: pointer; }
  .primary { justify-self: start; background: var(--primary-color); color: var(--text-primary-color, #fff); border: 0; border-radius: 18px; padding: 8px 20px; }
  .primary[disabled] { opacity: 0.5; cursor: default; }
  .link { background: none; border: 0; color: var(--primary-color); padding: 0 4px; justify-self: start; }
  .device { border-top: 1px solid var(--divider-color); padding-top: 12px; display: grid; gap: 10px; }
  .device.skipped { opacity: 0.6; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th { text-align: left; font-weight: 500; color: var(--secondary-text-color); padding: 4px; }
  td { padding: 4px; vertical-align: top; }
  td input { width: 100%; box-sizing: border-box; }
  tr.conflict input[data-entid] { border-color: var(--error-color, #db4437); }
  .bad { color: var(--error-color, #db4437); display: block; }
  .error { background: rgba(219, 68, 55, 0.12); color: var(--error-color, #db4437); padding: 10px 12px; border-radius: 8px; }
  .refs { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
  .refs li { display: grid; gap: 2px; }
  .refs a { color: var(--primary-color); }
  .refs a.open { justify-self: start; font-size: 13px; }
  .refs code { font-size: 12px; }
  h3 .badge { font-size: 12px; margin-right: 4px; }
  .badge { justify-self: start; font-size: 11px; padding: 1px 8px; border-radius: 10px; background: var(--secondary-background-color); }
  .badge.ok { background: rgba(67, 160, 71, 0.15); color: var(--success-color, #43a047); }
  .badge.warn { background: rgba(255, 160, 0, 0.18); color: var(--warning-color, #ffa000); }
  .badge.info { background: rgba(3, 169, 244, 0.15); color: var(--info-color, #039be5); }
  @media (max-width: 600px) {
    main { padding: 8px; }
    table, tbody, tr, td { display: block; width: 100%; }
    thead { display: none; }
    tr { border-top: 1px solid var(--divider-color); padding: 6px 0; }
  }
`;

customElements.define("move-device-panel", MoveDevicePanel);
