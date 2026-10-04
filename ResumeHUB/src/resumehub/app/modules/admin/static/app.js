"use strict";
// Manifest-driven admin panel. All data is rendered through text nodes (never innerHTML):
// resume content originates from inbound email and must be treated as untrusted.
const API = "/api/v1";
const root = document.getElementById("app");
let manifest = null;

function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid);
  return el;
}

const tok = {
  get access() { return sessionStorage.getItem("access"); },
  get refresh() { return sessionStorage.getItem("refresh"); },
  set(p) { sessionStorage.setItem("access", p.access_token); sessionStorage.setItem("refresh", p.refresh_token); },
  clear() { sessionStorage.clear(); },
};

function errText(data, fallback) {
  if (!data) return fallback;
  const d = data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(e => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("\n");
  return fallback;
}

async function refreshTokens() {
  if (!tok.refresh) return false;
  const res = await fetch(`${API}/auth/refresh`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tok.refresh }),
  });
  if (!res.ok) return false;
  tok.set(await res.json());
  return true;
}

async function api(url, opts = {}, retry = true) {
  const headers = { ...(opts.headers || {}) };
  if (tok.access) headers.Authorization = `Bearer ${tok.access}`;
  let body = opts.body;
  if (opts.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.json); }
  const res = await fetch(url.startsWith("/") ? url : API + "/" + url, { method: opts.method || "GET", headers, body });
  if (res.status === 401 && retry && await refreshTokens()) return api(url, opts, false);
  if (res.status === 401) { tok.clear(); manifest = null; renderLogin(); throw new Error("Session expired"); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(errText(data, res.statusText));
  return data;
}

function show(v) {
  if (v == null) return "";
  if (Array.isArray(v)) return v.map(show).join(", ");
  if (typeof v === "object") return Object.entries(v).map(([k, x]) => `${k}=${show(x)}`).join(", ");
  return String(v);
}
const get = (o, path) => path.split(".").reduce((a, k) => (a == null ? a : a[k]), o);

// ---- login ----
function renderLogin(msg = "") {
  const email = h("input", { type: "text", placeholder: "Email", autocomplete: "username" });
  const pw = h("input", { type: "password", placeholder: "Password", autocomplete: "current-password" });
  const err = h("div", { class: "err" }, msg);
  const go = async () => {
    err.textContent = "";
    const res = await fetch(`${API}/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email.value, password: pw.value }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) { err.textContent = errText(data, "Login failed"); return; }
    tok.set(data);
    boot();
  };
  pw.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  root.replaceChildren(h("div", { class: "login" }, h("h2", {}, "Resume Hub"), email, pw, err, h("button", { class: "primary", onclick: go }, "Sign in")));
}

// ---- shell ----
function renderShell() {
  const nav = h("nav", { class: "side" }, h("h1", {}, manifest.app));
  const link = (hash, label) => nav.append(h("a", { href: hash, "data-hash": hash }, label));
  link("#/", "Dashboard");
  manifest.resources.forEach(r => link(`#/r/${r.key}`, r.label));
  link("#/permissions", "Permissions");
  nav.append(
    h("div", { class: "who" }, manifest.user.email, h("br"), manifest.user.roles.join(", ")),
    h("button", { onclick: async () => { try { await api("/auth/logout", { method: "POST" }); } catch (e) { /* already signed out */ } tok.clear(); renderLogin(); } }, "Sign out"),
  );
  const main = h("main", { id: "main" });
  root.replaceChildren(h("div", { class: "shell" }, nav, main));
  route();
}

async function route() {
  if (!manifest) return;
  const hash = location.hash || "#/";
  document.querySelectorAll(".side a").forEach(a => a.classList.toggle("active", a.dataset.hash === hash));
  const main = document.getElementById("main");
  try {
    if (hash.startsWith("#/r/")) {
      const res = manifest.resources.find(r => r.key === hash.slice(4));
      if (res) return await renderResource(main, res);
    }
    if (hash === "#/permissions") return renderPermissions(main);
    await renderDashboard(main);
  } catch (e) {
    main.replaceChildren(h("div", { class: "err" }, e.message));
  }
}

async function renderDashboard(main) {
  const stats = await api("/admin/stats");
  main.replaceChildren(
    h("h2", {}, "Dashboard"),
    h("div", { class: "cards" }, Object.entries(stats).map(([k, v]) =>
      h("div", { class: "card" }, h("b", {}, show(v)), h("span", { class: "muted" }, k.replaceAll("_", " "))))),
    h("h2", {}, "Modules"),
    h("table", {}, h("tr", {}, ["Module", "Version", "Description"].map(t => h("th", {}, t))),
      manifest.modules.map(m => h("tr", {}, h("td", {}, m.name), h("td", {}, m.version), h("td", {}, m.description)))),
  );
}

function renderPermissions(main) {
  main.replaceChildren(
    h("h2", {}, "Permission catalog"),
    h("p", { class: "muted" }, "Format resource:action. Wildcards: * , resumes:* , *:read. A deny always beats an allow. The mark shows whether you hold it."),
    h("table", {}, h("tr", {}, ["Permission", "Module", "Description", "You"].map(t => h("th", {}, t))),
      manifest.permissions.map(p => h("tr", {}, h("td", {}, p.key), h("td", {}, p.module || ""), h("td", {}, p.description),
        h("td", { class: p.granted ? "ok" : "no" }, p.granted ? "yes" : "no")))),
  );
}

// ---- generic resource view ----
async function renderResource(main, res) {
  const state = { page: 1, size: 20, q: "" };
  const holder = h("div", {});
  const search = h("input", { type: "search", placeholder: "Search…" });
  const reload = async () => {
    const qs = new URLSearchParams({ page: state.page, size: state.size });
    if (state.q) qs.set("q", state.q);
    const data = await api(`${res.endpoint}?${qs}`);
    holder.replaceChildren(table(data));
    pager.replaceChildren(
      h("button", { disabled: state.page <= 1, onclick: () => { state.page--; reload(); } }, "Prev"),
      h("span", { class: "muted" }, ` page ${data.page} · ${data.total} total `),
      h("button", { disabled: data.page * data.size >= data.total, onclick: () => { state.page++; reload(); } }, "Next"),
    );
  };
  const table = data => h("table", {},
    h("tr", {}, res.columns.map(c => h("th", {}, c[0])), h("th", {})),
    data.items.map(item => h("tr", {},
      res.columns.map(c => h("td", {}, show(get(item, c[1])))),
      h("td", { class: "actions" },
        h("button", { onclick: () => openEditor(res, item._id, reload) }, res.can.update ? "Edit" : "View"),
        res.can.delete && h("button", { class: "danger", onclick: async () => {
          if (!confirm(`Delete ${item._id}?`)) return;
          try { await api(`${res.endpoint}/${encodeURIComponent(item._id)}`, { method: "DELETE" }); reload(); } catch (e) { alert(e.message); }
        } }, "Delete"))))
  );
  const pager = h("div", { class: "bar" });
  search.addEventListener("keydown", e => { if (e.key === "Enter") { state.q = search.value; state.page = 1; reload().catch(x => alert(x.message)); } });
  main.replaceChildren(
    h("h2", {}, res.label), res.description && h("div", { class: "muted" }, res.description),
    h("div", { class: "bar" }, search, res.can.create && h("button", { class: "primary", onclick: () => openEditor(res, null, reload) }, "New")),
    holder, pager);
  await reload();
}

async function openEditor(res, id, onSaved) {
  let doc = res.create_template || {};
  if (id) {
    try { doc = await api(`${res.endpoint}/${encodeURIComponent(id)}`); } catch (e) { alert(e.message); return; }
    for (const f of res.readonly_fields) delete doc[f];
  }
  const writable = id ? res.can.update : res.can.create;
  const area = h("textarea", { spellcheck: "false", readonly: !writable }, JSON.stringify(doc, null, 2));
  const err = h("div", { class: "err" });
  const close = () => overlay.remove();
  const save = async () => {
    err.textContent = "";
    let payload;
    try { payload = JSON.parse(area.value); } catch (e) { err.textContent = "Invalid JSON: " + e.message; return; }
    try {
      if (id) await api(`${res.endpoint}/${encodeURIComponent(id)}`, { method: res.update_method, json: payload });
      else await api(res.endpoint, { method: "POST", json: payload });
      close(); onSaved();
    } catch (e) { err.textContent = e.message; }
  };
  const overlay = h("div", { class: "overlay" }, h("div", { class: "modal" },
    h("h2", {}, `${id ? (writable ? "Edit" : "View") : "New"} · ${res.label}${id ? " · " + id : ""}`),
    area, err,
    h("div", { class: "row" }, h("button", { onclick: close }, writable ? "Cancel" : "Close"), writable && h("button", { class: "primary", onclick: save }, "Save"))));
  document.body.append(overlay);
}

async function boot() {
  if (!tok.access) return renderLogin();
  try {
    manifest = await api("/admin/manifest");
  } catch (e) {
    if (tok.access) { tok.clear(); renderLogin(e.message.includes("admin:access") ? "This account has no admin panel access." : e.message); }
    return;
  }
  renderShell();
}

window.addEventListener("hashchange", route);
boot();
