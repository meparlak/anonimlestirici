// Anonimleştirici Windows arayüzü. Python tarafı (anonimlestirici/desktop/app.py) window.pywebview.api
// üzerinden çağrılır. İnternete hiçbir istek yapılmaz.
"use strict";

const TYPE_HELP = {
  "KİŞİ": "Türkçe ad sözlüğü, unvanlar (Sayın, Dr., Bey, Hanım), sütun başlıkları ve dil modeli",
  "TC": "11 hane ve TC kimlik numarası doğrulama algoritması",
  "TELEFON": "Cep ve sabit hat, +90 / 0 önekli ya da öneksiz",
  "EPOSTA": "ad@alan.com biçimindeki adresler",
  "ADRES": "Mah., Cad., Sok., No: gibi ipuçları ve il/ilçe",
  "BİRİM": "Müdürlüğü, Daire Başkanlığı, Birimi, Bölümü… ile biten adlar",
  "KURUM": "Üniversitesi, Belediyesi, A.Ş., Ltd. Şti.… ile biten adlar ve dil modeli",
  "IBAN": "TR ile başlayan, doğrulaması tutan IBAN'lar",
  "PLAKA": "54 ABC 123 gibi araç plakaları",
  "TARİH": "12.03.1985 gibi tarihler. Analizde gerekli olabileceği için varsayılan kapalı.",
  "VERGİ": "Vergi kimlik no, MERSİS no, e-fatura ETTN",
  "FİNANS": "Kart ve hesap numaraları, SWIFT kodu",
  "BELGE": "Pasaport, ehliyet ve kimlik belgesi numaraları (dil modeli)",
  "IP": "IP adresleri",
  "SAĞLIK": "Hastalık, tanı, tedavi gibi sağlık bilgileri (KVKK özel nitelikli veri, dil modeli)",
  "HASSAS": "Din, etnik köken, siyasi görüş ifadeleri (KVKK özel nitelikli veri, dil modeli)",
  "ÖZEL": "Listeler sekmesinde girdiğiniz terimler",
};
const EXTS = [".xlsx", ".xlsm", ".csv", ".docx", ".pptx", ".txt", ".md"];
const MAX_ROWS = 1500;

const S = {
  tab: "anon", view: "home", hello: null, prefs: null, types: [],
  cands: [], docs: [], warnings: [], selected: null, search: "", filter: "",
  saved: null, progress: null, workingTitle: "", t0: 0,
  rev: { path: null, name: "", count: 0, text: "", html: "", plain: "", status: "Önce eşleştirme tablosunu seçin." },
  settingsTab: "types",
};
let api = null;
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const typeLabel = (v) => (S.types.find((t) => t.value === v) || { label: v }).label;
const isEnabled = (t) => (S.prefs.enabled && t.value in S.prefs.enabled ? S.prefs.enabled[t.value] : t.defaultEnabled);

// Python'un çağırdığı işlevler
window.app = {
  onProgress(p) { S.progress = p; if (S.view === "working") renderWorking(); },
  onFilesDropped(paths) { analyze(paths); },
};

// ---------------------------------------------------------------- başlangıç

async function start() {
  const h = await api.hello();
  S.hello = h; S.prefs = h.prefs; S.types = h.types;
  render();
}
window.addEventListener("pywebviewready", () => { api = window.pywebview.api; start(); });
window.addEventListener("DOMContentLoaded", () => {
  const demo = new URLSearchParams(location.search).get("demo");
  if (demo && !window.pywebview) { api = demoApi(demo); start(); }
});

// ---------------------------------------------------------------- yardımcılar

let prefsTimer = null;
function savePrefs() {
  clearTimeout(prefsTimer);
  prefsTimer = setTimeout(() => api.set_prefs(S.prefs), 250);
}
function showAlert(title, message) {
  openDialog(`<h3>${esc(title)}</h3><p>${esc(message)}</p><div class="row"><span class="spacer"></span><button class="btn primary" data-action="close-dialog">Tamam</button></div>`);
}
function openDialog(html, wide = false) {
  const o = $("#overlay");
  o.innerHTML = `<div class="dialog${wide ? " wide" : ""}" role="dialog" aria-modal="true">${html}</div>`;
  o.hidden = false;
  const f = o.querySelector("input,textarea,button.primary");
  if (f) f.focus();
}
function closeDialog() { $("#overlay").hidden = true; $("#overlay").innerHTML = ""; }
function badgeColor(name) {
  const e = name.split(".").pop().toLowerCase();
  return { xlsx: "#107c41", xlsm: "#107c41", csv: "#107c41", docx: "#185abd", pptx: "#c43e1c" }[e] || "#6b7280";
}
const baseName = (p) => p.split(/[\\/]/).pop();
const dirName = (p) => p.slice(0, Math.max(p.lastIndexOf("\\"), p.lastIndexOf("/")));

// ---------------------------------------------------------------- işlemler

async function analyze(paths) {
  if (!paths || !paths.length) return;
  S.view = "working"; S.progress = null; S.t0 = Date.now();
  S.workingTitle = paths.length === 1 ? `${baseName(paths[0])} taranıyor` : `${paths.length} dosya taranıyor`;
  render();
  const r = await api.analyze(paths);
  if (!r.ok) {
    S.view = "home"; render();
    if (!r.cancelled) showAlert("Dosya taranamadı", r.error);
    return;
  }
  applyCands(r);
  S.selected = S.cands.length ? S.cands[0].id : null;
  S.search = ""; S.filter = "";
  S.view = "review"; render();
  if (r.problems && r.problems.length) showAlert("Bazı dosyalar eklenmedi", r.problems.join("\n\n"));
}
function applyCands(r) { S.cands = r.candidates; S.docs = r.documents; S.warnings = r.warnings || []; }
async function call(fn, ...args) {
  const r = await api[fn](...args);
  if (!r.ok) { if (!r.cancelled) showAlert("İşlem tamamlanamadı", r.error); return null; }
  return r;
}
async function save() {
  const t0 = Date.now();
  S.view = "working"; S.workingTitle = "Kaydediliyor"; S.progress = null; render();
  const r = await api.save();
  if (!r.ok) { S.view = "review"; render(); if (!r.cancelled) showAlert("Kaydedilemedi", r.error); return; }
  S.saved = { ...r, seconds: (Date.now() - t0) / 1000 };
  S.prefs = (await api.hello()).prefs;
  S.view = "result"; render();
}

// ---------------------------------------------------------------- çizim

function render() {
  document.querySelectorAll(".segmented button").forEach((b) => b.classList.toggle("on", b.dataset.tab === S.tab));
  if (!S.hello) { $("#main").innerHTML = `<div class="working"><div class="progress indet"><i></i></div><div class="muted">Hazırlanıyor…</div></div>`; return; }
  if (S.tab === "rev") return renderReverse();
  ({ home: renderHome, working: renderWorking, review: renderReview, result: renderResult })[S.view]();
}

function renderHome() {
  const chips = S.types.filter((t) => t.value !== "ÖZEL").map((t) =>
    `<button class="chip${isEnabled(t) ? "" : " off"}" data-action="toggle-type" data-type="${esc(t.value)}" title="${isEnabled(t) ? "Aranıyor. Kapatmak için tıklayın." : "Aranmıyor. Açmak için tıklayın."}">${esc(t.label)}</button>`).join("");
  const recent = (S.prefs.recent || []).map((r) =>
    `<tr><td>${esc(r.name)}</td><td>${esc(r.when)}</td><td class="num">${esc(r.found)}</td><td><button class="link" data-action="reveal" data-path="${esc(r.path)}">Klasörde göster</button></td></tr>`).join("");
  $("#main").innerHTML = `
    <div class="drop" id="drop" data-action="choose" tabindex="0" role="button" aria-label="Dosya seç ya da sürükle">
      <svg viewBox="0 0 24 24" width="48" height="48" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="1.2" d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8l-5-5Zm0 0v5h5M8.5 12.5h7M8.5 15.5h7M8.5 9.5h3"/></svg>
      <strong>Dosyaları buraya sürükleyin</strong>
      <span class="muted">${EXTS.join(" · ")} · birden fazla dosya olabilir</span>
      <button class="btn" data-action="choose">Dosya Seç…</button>
    </div>
    <div class="row"><span class="muted">Aranacak türler:</span><div class="chips">${chips}</div><span class="spacer"></span><button class="btn" data-action="open-settings">Değiştir…</button></div>
    ${recent ? `<div class="muted small">Son işlemler</div><div class="panel" style="max-height:160px"><table><thead><tr><th>Dosya</th><th>Tarih</th><th class="num">Bulunan</th><th></th></tr></thead><tbody>${recent}</tbody></table></div>` : ""}
    <div class="muted small">🔒 Bu uygulama internete bağlanmaz. Dosyalarınız bu bilgisayardan çıkmaz.</div>`;
  const d = $("#drop");
  d.addEventListener("dragenter", () => d.classList.add("hover"));
  d.addEventListener("dragleave", () => d.classList.remove("hover"));
  d.addEventListener("drop", () => d.classList.remove("hover"));
}

function renderWorking() {
  const p = S.progress;
  const bar = p && p.total ? `<div class="progress"><i style="width:${Math.round((100 * p.done) / p.total)}%"></i></div>` : `<div class="progress indet"><i></i></div>`;
  $("#main").innerHTML = `<div class="working"><h2>${esc(S.workingTitle)}</h2>${bar}
    <div class="muted small">${esc(p ? p.message : " ")}</div><div><button class="btn" data-action="cancel">İptal</button></div></div>`;
}

function filtered() {
  const q = S.search.toLocaleLowerCase("tr");
  return S.cands.filter((c) => (!S.filter || c.type === S.filter) &&
    (!q || c.value.toLocaleLowerCase("tr").includes(q) || (c.code || "").toLocaleLowerCase("tr").includes(q)));
}

function renderReview() {
  const occ = S.cands.filter((c) => c.accepted).reduce((a, c) => a + c.count, 0);
  const skipped = S.cands.filter((c) => !c.accepted).length;
  const opts = [`<option value="">Tümü (${S.cands.length})</option>`].concat(S.types.map((t) => {
    const n = S.cands.filter((c) => c.type === t.value).length;
    return n ? `<option value="${esc(t.value)}"${S.filter === t.value ? " selected" : ""}>${esc(t.label)} (${n})</option>` : "";
  })).join("");
  $("#main").innerHTML = `
    <h2>${esc(S.docs.join(", "))} · ${S.cands.length} farklı değer, ${occ} geçiş</h2>
    ${S.warnings.length ? `<div class="warnings">${S.warnings.map((w) => `<div>⚠ ${esc(w)}</div>`).join("")}</div>` : ""}
    <div class="row">
      <input type="search" id="search" placeholder="Ara" value="${esc(S.search)}" style="width:240px">
      <select id="filter">${opts}</select>
      <span class="spacer"></span><button class="btn" data-action="add-value">+ Değer ekle</button>
    </div>
    <div class="split">
      <div class="panel tablewrap" id="table"></div>
      <div class="panel detail" id="detail"></div>
    </div>
    <div class="row"><span class="muted small">${skipped ? `${skipped} değer atlanacak. Atlananlar eşleştirme tablosunun "Atlananlar" sayfasına yazılır.` : "Bütün değerler anonimleştirilecek."}</span>
      <span class="spacer"></span><button class="btn" data-action="back">Geri</button>
      <button class="btn primary" data-action="save"${S.cands.length ? "" : " disabled"}>Anonimleştir ve Kaydet</button></div>`;
  renderTable(); renderDetail();
  $("#search").addEventListener("input", (e) => { S.search = e.target.value; renderTable(); });
  $("#filter").addEventListener("change", (e) => { S.filter = e.target.value; renderTable(); });
}

function renderTable() {
  const rows = filtered();
  const typeOpts = (sel) => S.types.map((t) => `<option value="${esc(t.value)}"${t.value === sel ? " selected" : ""}>${esc(t.label)}</option>`).join("");
  const body = rows.slice(0, MAX_ROWS).map((c) => `
    <tr data-id="${c.id}" class="${c.id === S.selected ? "sel" : ""}">
      <td><input type="checkbox" data-action="accept" data-id="${c.id}"${c.accepted ? " checked" : ""} aria-label="Anonimleştir"></td>
      <td><select class="inline" data-action="set-type" data-id="${c.id}">${typeOpts(c.type)}</select></td>
      <td style="${c.accepted ? "" : "color:var(--muted)"}">${esc(c.value)}</td>
      <td class="code${c.code ? "" : " skip"}">${esc(c.code || "atlanacak")}</td>
      <td class="num">${c.count}</td>
      <td class="muted">${c.lowConfidence ? `<span class="warnicon" title="Düşük güven: kişisel veri olmayabilir. Kontrol edip işaretleyin.">⚠</span>` : ""}${esc(c.sources.join(", "))}</td>
    </tr>`).join("");
  $("#table").innerHTML = `<table><thead><tr><th style="width:32px"></th><th style="width:150px">Tür</th><th>Değer</th><th style="width:130px">Kod</th><th class="num" style="width:56px">Adet</th><th style="width:210px">Yöntem</th></tr></thead><tbody>${body}</tbody></table>
    ${rows.length > MAX_ROWS ? `<div class="muted small" style="padding:8px">İlk ${MAX_ROWS} satır gösteriliyor; aramayla daraltabilirsiniz.</div>` : ""}`;
}

function highlight(o) {
  // konumlar UTF-16 birimi; JavaScript dizeleri de UTF-16 olduğu için doğrudan kullanılır
  return esc(o.context.slice(0, o.start)) + "<mark>" + esc(o.context.slice(o.start, o.end)) + "</mark>" + esc(o.context.slice(o.end));
}

function renderDetail() {
  const c = S.cands.find((x) => x.id === S.selected);
  if (!c) { $("#detail").innerHTML = `<span class="muted">Bir satır seçin.</span>`; return; }
  const multi = S.docs.length > 1;
  $("#detail").innerHTML = `<div class="lbl">Geçtiği yerler</div>
    ${c.occurrences.map((o) => `<div><div class="muted small">${esc(multi ? `${o.file} · ${o.location}` : o.location)}</div><div>${highlight(o)}</div></div>`).join("")}
    ${c.count > c.occurrences.length ? `<div class="muted">… ve ${c.count - c.occurrences.length} geçiş daha</div>` : ""}
    ${c.variants.length ? `<div class="lbl">Diğer yazımlar</div><div>${esc(c.variants.join(", "))}</div>` : ""}
    <span class="spacer"></span>
    <button class="btn" data-action="exclude" data-id="${c.id}" title="Bu değer bundan sonra hiçbir dosyada anonimleştirilmez.">Asla listesine ekle</button>`;
}

function renderResult() {
  const r = S.saved;
  const fileRow = (p, note, warn) => `<div class="panel file"><div class="badge" style="background:${badgeColor(p)}">${esc(p.split(".").pop().toUpperCase())}</div>
    <div class="meta"><div>${esc(baseName(p))}</div><div class="small" style="color:${warn ? "var(--warn)" : "var(--muted)"}">${esc(note)}</div></div>
    <button class="btn" data-action="open" data-path="${esc(p)}">Aç</button><button class="btn" data-action="reveal" data-path="${esc(p)}">Klasörde göster</button></div>`;
  $("#main").innerHTML = `<h2 class="ok-title">✓ ${r.outputs.length} dosya anonimleştirildi</h2>
    ${r.outputs.map((p) => fileRow(p, "Yapay zekâya verebileceğiniz dosya · " + dirName(p), false)).join("")}
    ${fileRow(r.mapping, "Gerçek değerleri içerir. Yapay zekâya vermeyin, paylaşmayın.", true)}
    <div class="stats">
      <div class="panel stat"><b>${r.replaced}</b><span class="muted small">değiştirilen geçiş</span></div>
      <div class="panel stat"><b>${r.distinct}</b><span class="muted small">farklı değer</span></div>
      <div class="panel stat"><b>${r.skipped}</b><span class="muted small">atlanan değer</span></div>
      <div class="panel stat"><b>${r.seconds.toFixed(1).replace(".", ",")} sn</b><span class="muted small">süre</span></div>
    </div>
    <div class="muted small">Hatırlatma: Kişinin az olduğu birimlerde “birim + unvan + tarih” birlikte kişiyi ele verebilir. Göndermeden önce anonim dosyaya bir kez göz atın.</div>
    ${(r.warnings || []).map((w) => `<div class="warnings">⚠ ${esc(w)}</div>`).join("")}
    <span class="spacer"></span>
    <div class="row"><span class="spacer"></span><button class="btn" data-action="same-session" title="Bir sonraki dosyada da aynı kişi aynı kodu alır.">Aynı kodlarla başka dosya ekle</button>
      <button class="btn primary" data-action="new-session">Yeni işlem</button></div>`;
}

function renderReverse() {
  const R = S.rev;
  $("#main").innerHTML = `
    <div class="row"><span class="muted">Eşleştirme tablosu:</span>
      <span class="panel" style="padding:4px 10px">${R.name ? `${esc(R.name)} · ${R.count} kod` : "seçilmedi"}</span>
      <button class="btn" data-action="pick-mapping">Seç…</button><span class="spacer"></span>
      <button class="btn" data-action="reverse-file" title=".docx, .xlsx, .pptx, .csv, .txt dosyasını aynı biçimde geri çevirir.">Dosyadan çevir…</button></div>
    <div class="two">
      <div style="display:flex;flex-direction:column;gap:4px;min-height:0"><span class="muted small">Yapay zekânın cevabı (yapıştırın)</span>
        <textarea id="revin" placeholder="Örnek: Gecikmenin kök nedeni [BİRİM_1]'nin [KURUM_1] ile teyit sürecinin olmaması.">${esc(R.text)}</textarea></div>
      <div style="display:flex;flex-direction:column;gap:4px;min-height:0"><span class="muted small">Gerçek değerlerle</span>
        <div class="panel out" id="revout">${R.html}</div></div>
    </div>
    <div class="row"><span class="muted small" id="revstatus">${esc(R.status)}</span><span class="spacer"></span>
      <button class="btn primary" data-action="copy"${R.plain ? "" : " disabled"}>Kopyala</button></div>`;
  let timer;
  $("#revin").addEventListener("input", (e) => { R.text = e.target.value; clearTimeout(timer); timer = setTimeout(convert, 150); });
}

async function convert() {
  const R = S.rev;
  if (!R.path) { R.status = "Önce eşleştirme tablosunu seçin."; $("#revstatus").textContent = R.status; return; }
  const text = R.text;
  const r = await api.reverse_text(text, R.path);
  if (!r.ok || text !== R.text) return;
  let html = "", pos = 0;
  for (const s of r.spans) { html += esc(text.slice(pos, s.start)) + "<mark>" + esc(s.replacement) + "</mark>"; pos = s.end; }
  R.html = html + esc(text.slice(pos)); R.plain = r.text;
  R.status = `${r.replaced} kod çevrildi` + (r.unknown.length ? " · tabloda olmayan: " + r.unknown.join(", ") : " · bilinmeyen kod yok");
  $("#revout").innerHTML = R.html; $("#revstatus").textContent = R.status;
  document.querySelector('[data-action="copy"]').disabled = !R.plain;
}

// ---------------------------------------------------------------- ayarlar

function renderSettings() {
  const tabs = [["types", "Veri türleri"], ["lists", "Listeler"], ["headers", "Excel başlıkları"], ["output", "Çıktı"]];
  const P = S.prefs;
  let pane = "";
  if (S.settingsTab === "types") {
    pane = S.types.map((t) => `<div class="toggle-row"><input type="checkbox" id="t-${esc(t.value)}" data-action="pref-type" data-type="${esc(t.value)}"${isEnabled(t) ? " checked" : ""}>
      <label for="t-${esc(t.value)}">${esc(t.label)}<div class="muted small">${esc(TYPE_HELP[t.value] || "")}</div></label></div>`).join("") +
      `<h3 style="margin:10px 0 0;font-size:14px">İnce ayarlar</h3>
      ${prefToggle("nerEnabled", "Dil modeli (NER) ile ikinci kontrol", S.hello.ner ? "Uygulamanın içindeki Türkçe model, sözlükte olmayan isimleri ve KVKK veri türlerini bulur. Çok büyük dosyalarda kapatırsanız tarama hızlanır." : "Bu pakette dil modeli yok.")}
      ${prefToggle("tcChecksum", "TC numarasında doğrulama algoritması tutmayanları atla", "")}
      ${prefToggle("nameAliases", "Adın ya da soyadın tek başına geçtiği yerleri de aynı kişi say (\"Ahmet Bey\", \"Yılmaz'ın\")", "")}`;
  } else if (S.settingsTab === "lists") {
    pane = `<div class="muted small">Her satıra bir terim yazın. Her zaman anonimleştirilecek terimlerde türü "terim | TÜR" biçiminde verebilirsiniz (ör. "Yılmaz Makine | KURUM"). Tür yazmazsanız ÖZEL kabul edilir.</div>
      <div class="lists"><div><b>Her zaman anonimleştir</b><textarea data-list="customTerms" placeholder="Proje Atlas | ÖZEL&#10;Hat-3">${esc((P.customTerms || []).join("\n"))}</textarea></div>
      <div><b>Asla anonimleştirme</b><textarea data-list="excludeTerms" placeholder="Kalite Müdürlüğü&#10;ISO 9001">${esc((P.excludeTerms || []).join("\n"))}</textarea></div></div>`;
  } else if (S.settingsTab === "headers") {
    const h = P.headers || S.hello.defaults.headers;
    const text = Object.entries(h).sort((a, b) => (a[1] + a[0]).localeCompare(b[1] + b[0], "tr")).map(([k, v]) => `${k} = ${v}`).join("\n");
    pane = `<div class="muted small">Başlığı bu listedeki gibi olan sütunlardaki bütün hücreler o türle anonimleştirilir. Her satıra "başlık = TÜR" yazın. Büyük/küçük harf ve Türkçe karakter fark etmez.</div>
      <textarea id="headers">${esc(text)}</textarea><div><button class="btn" data-action="reset-headers">Varsayılana dön</button></div>`;
  } else {
    pane = `<div class="field"><span>Çıktı klasörü</span><div>
        <label><input type="radio" name="ask" data-action="ask" value="1"${P.askOutputFolder ? " checked" : ""}> Her seferinde sor</label><br>
        <label><input type="radio" name="ask" data-action="ask" value="0"${P.askOutputFolder ? "" : " checked"}> Hep aynı klasöre kaydet</label></div></div>
      ${P.askOutputFolder ? "" : `<div class="field"><span></span><div class="row"><span class="muted" style="overflow-wrap:anywhere">${esc(P.outputFolder || "Klasör seçilmedi")}</span><button class="btn" data-action="choose-folder">Seç…</button></div></div>`}
      <div class="field"><label for="suffix">Dosya adı eki</label><input type="text" id="suffix" value="${esc(P.outputSuffix)}"></div>
      <div class="field"><label for="fmt">Kod biçimi</label><select id="fmt">
        ${[["bracket", "[KİŞİ_1]"], ["plain", "KİŞİ_1"], ["letter", "Kişi A"]].map(([v, l]) => `<option value="${v}"${P.codeFormat === v ? " selected" : ""}>${l}</option>`).join("")}</select></div>
      <div class="muted small">Unvanlar kodun dışında kalır: "Ahmet Bey" → "[KİŞİ_1] Bey". Aynı oturumda işlenen dosyalarda aynı değer hep aynı kodu alır.</div>
      ${prefToggle("cleanMetadata", "Belge bilgilerini temizle (yazar, son değiştiren, yorum yazarları)", "")}`;
  }
  openDialog(`<div class="row"><h3>Ayarlar</h3><span class="spacer"></span><button class="btn" data-action="close-settings">Kapat</button></div>
    <div class="tabs">${tabs.map(([k, l]) => `<button data-action="settings-tab" data-tab="${k}" class="${S.settingsTab === k ? "on" : ""}">${l}</button>`).join("")}</div>
    <div class="pane">${pane}</div>`, true);
  bindSettingsInputs();
}
function prefToggle(key, label, help) {
  return `<div class="toggle-row"><input type="checkbox" id="p-${key}" data-action="pref-bool" data-key="${key}"${S.prefs[key] ? " checked" : ""}>
    <label for="p-${key}">${esc(label)}${help ? `<div class="muted small">${esc(help)}</div>` : ""}</label></div>`;
}
function bindSettingsInputs() {
  document.querySelectorAll("textarea[data-list]").forEach((t) => t.addEventListener("input", () => {
    S.prefs[t.dataset.list] = t.value.split("\n").map((s) => s.trim()).filter(Boolean); savePrefs();
  }));
  const h = $("#headers");
  if (h) h.addEventListener("input", () => {
    const out = {};
    for (const line of h.value.split("\n")) { const i = line.lastIndexOf("="); if (i > 0) { const k = line.slice(0, i).trim(), v = line.slice(i + 1).trim(); if (k && v) out[k] = v; } }
    S.prefs.headers = out; savePrefs();
  });
  const sfx = $("#suffix"); if (sfx) sfx.addEventListener("input", () => { S.prefs.outputSuffix = sfx.value || "_anonim"; savePrefs(); });
  const fmt = $("#fmt"); if (fmt) fmt.addEventListener("change", () => { S.prefs.codeFormat = fmt.value; savePrefs(); });
}

// ---------------------------------------------------------------- olaylar

document.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-action]");
  const row = e.target.closest("tr[data-id]");
  if (row && !el) { S.selected = Number(row.dataset.id); document.querySelectorAll("tr[data-id]").forEach((r) => r.classList.toggle("sel", r === row)); renderDetail(); return; }
  if (!el) return;
  const a = el.dataset.action;
  if (a === "choose") { e.stopPropagation(); analyze(await api.choose_files()); }
  else if (a === "tab") { S.tab = el.dataset.tab; render(); }
  else if (a === "open-settings") { S.settingsTab = "types"; renderSettings(); }
  else if (a === "close-settings") { closeDialog(); render(); }
  else if (a === "settings-tab") { S.settingsTab = el.dataset.tab; renderSettings(); }
  else if (a === "close-dialog") closeDialog();
  else if (a === "toggle-type") { const t = S.types.find((x) => x.value === el.dataset.type); S.prefs.enabled = { ...S.prefs.enabled, [t.value]: !isEnabled(t) }; savePrefs(); render(); }
  else if (a === "cancel") api.cancel();
  else if (a === "back" || a === "same-session") { S.view = "home"; render(); }
  else if (a === "new-session") { await api.new_session(); S.saved = null; S.cands = []; S.view = "home"; render(); }
  else if (a === "save") save();
  else if (a === "open") api.open_path(el.dataset.path);
  else if (a === "reveal") api.reveal(el.dataset.path);
  else if (a === "exclude") {
    const c = S.cands.find((x) => x.id === Number(el.dataset.id));
    const r = await call("exclude", c.id, c.value);
    if (r) { applyCands(r); S.prefs.excludeTerms = [...new Set([...(S.prefs.excludeTerms || []), c.value])]; renderReview(); }
  }
  else if (a === "add-value") openAddDialog();
  else if (a === "add-confirm") {
    const v = $("#addv").value.trim(), t = $("#addt").value;
    closeDialog();
    if (!v) return;
    const r = await call("add_manual", v, t);
    if (r) { applyCands(r); S.selected = r.addedId; renderReview(); if (!r.addedCount) showAlert("Bulunamadı", `"${v}" dosyada geçmiyor. Yine de listeye eklendi.`); }
  }
  else if (a === "pick-mapping") {
    const r = await call("pick_mapping");
    if (r) { Object.assign(S.rev, { path: r.path, name: r.name, count: r.count }); renderReverse(); convert(); }
  }
  else if (a === "reverse-file") {
    if (!S.rev.path) return showAlert("Eşleştirme tablosu gerekli", "Önce eşleştirme tablosunu seçin.");
    const r = await call("reverse_file", S.rev.path);
    if (r) { S.rev.status = `${r.replaced} kod çevrildi: ${r.name}` + (r.unknown.length ? " · tabloda olmayan: " + r.unknown.join(", ") : ""); $("#revstatus").textContent = S.rev.status; }
  }
  else if (a === "copy") { await api.copy_text(S.rev.plain); $("#revstatus").textContent = S.rev.status + " · kopyalandı"; }
  else if (a === "pref-bool") { S.prefs[el.dataset.key] = el.checked; savePrefs(); }
  else if (a === "pref-type") { S.prefs.enabled = { ...S.prefs.enabled, [el.dataset.type]: el.checked }; savePrefs(); }
  else if (a === "ask") { S.prefs.askOutputFolder = el.value === "1"; savePrefs(); renderSettings(); }
  else if (a === "choose-folder") { const r = await api.choose_output_folder(); S.prefs = r.prefs; renderSettings(); }
  else if (a === "reset-headers") { S.prefs.headers = null; savePrefs(); renderSettings(); }
});
document.addEventListener("change", async (e) => {
  const el = e.target;
  if (el.dataset.action === "accept") { const r = await call("set_accepted", [Number(el.dataset.id)], el.checked); if (r) { applyCands(r); renderReview(); } }
  else if (el.dataset.action === "set-type") { const r = await call("set_type", Number(el.dataset.id), el.value); if (r) { applyCands(r); renderReview(); } }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("#overlay").hidden) { closeDialog(); if (S.view !== "working") render(); }
  if (e.key === "Enter" && e.target.id === "addv") document.querySelector('[data-action="add-confirm"]').click();
  if ((e.key === "Enter" || e.key === " ") && e.target.id === "drop") { e.preventDefault(); e.target.click(); }
  if (e.ctrlKey && e.key.toLowerCase() === "o" && S.tab === "anon" && S.view === "home") { e.preventDefault(); api.choose_files().then(analyze); }
  if (e.ctrlKey && e.key === ",") { e.preventDefault(); renderSettings(); }
});

function openAddDialog() {
  openDialog(`<h3>Değer ekle</h3>
    <label>Metin<br><input type="text" id="addv" style="width:100%" placeholder="ör. Hat-3, Proje Atlas, Gülşah" value="${esc(S.search)}"></label>
    <label>Tür<br><select id="addt" style="width:100%">${S.types.map((t) => `<option value="${esc(t.value)}"${t.value === "ÖZEL" ? " selected" : ""}>${esc(t.label)}</option>`).join("")}</select></label>
    <div class="muted small">Metin bütün dosyada aranır; büyük/küçük harf fark etmez.</div>
    <div class="row"><span class="spacer"></span><button class="btn" data-action="close-dialog">Vazgeç</button><button class="btn primary" data-action="add-confirm">Ekle</button></div>`);
}

// ---------------------------------------------------------------- tanıtım görüntüleri için örnek veri (?demo=...)

function demoApi(view) {
  const types = [["KİŞİ", "Ad soyad", true], ["TC", "TC kimlik no", true], ["TELEFON", "Telefon", true], ["EPOSTA", "E-posta", true],
    ["ADRES", "Adres", true], ["BİRİM", "Birim", true], ["KURUM", "Kurum", true], ["IBAN", "IBAN", true], ["PLAKA", "Plaka", false],
    ["TARİH", "Tarih", false], ["VERGİ", "Vergi/MERSİS no", true], ["FİNANS", "Kart/hesap no", true], ["BELGE", "Belge no", true],
    ["IP", "IP adresi", true], ["SAĞLIK", "Sağlık bilgisi", true], ["HASSAS", "Din/etnik/siyasi", true], ["ÖZEL", "Özel liste", true]]
    .map(([value, label, defaultEnabled]) => ({ value, label, defaultEnabled }));
  const c = (id, type, value, code, count, source, extra = {}) => {
    const ctx = extra.ctx || value, s = ctx.indexOf(value);
    return { id, type, typeLabel: types.find((t) => t.value === type).label, value, code, count, accepted: !!code, lowConfidence: !!extra.low,
      confidence: 0.9, sources: [source], files: ["sikayet_kayitlari_ekim.xlsx"], variants: extra.variants || [],
      occurrences: [{ file: "sikayet_kayitlari_ekim.xlsx", location: "Ekim!E2", context: ctx, start: s, end: s + value.length }] };
  };
  const cands = [
    c(1, "KİŞİ", "Ahmet Yılmaz", "[KİŞİ_1]", 3, "Sütun başlığı, Ad sözlüğü", { ctx: "Ahmet Yılmaz siparişin 2 hafta geciktiğini, satın almaya ulaşamadığını söyledi.", variants: ["AHMET YILMAZ", "Ahmet"] }),
    c(2, "TELEFON", "0532 123 45 67", "[TELEFON_1]", 1, "Kalıp"),
    c(3, "BİRİM", "Satın Alma Birimi", "[BİRİM_1]", 4, "Sonek kalıbı"),
    c(4, "KİŞİ", "Ayşe Kaya", "[KİŞİ_2]", 2, "NER modeli, Ad sözlüğü"),
    c(5, "KURUM", "Yıldız Makine A.Ş.", "[KURUM_1]", 2, "Sonek kalıbı, NER modeli"),
    c(6, "TC", "10000000078", "[TC_1]", 1, "Kalıp"),
    c(7, "SAĞLIK", "bel fıtığı ameliyatı", "[SAĞLIK_1]", 1, "NER modeli"),
    c(8, "EPOSTA", "a.yilmaz@ornek.com.tr", "[EPOSTA_1]", 1, "Kalıp"),
    c(9, "ADRES", "Esentepe Mah. Üniversite Cad. No:12 Serdivan/Sakarya", "[ADRES_1]", 1, "Adres ipuçları"),
    c(10, "KİŞİ", "Umut", "", 1, "Ad sözlüğü", { low: true, ctx: "Umut ediyoruz ki sorun bu hafta çözülür." }),
  ];
  const prefs = { enabled: {}, tcChecksum: true, nameAliases: true, nerEnabled: true, customTerms: [], excludeTerms: [], headers: null,
    codeFormat: "bracket", outputSuffix: "_anonim", cleanMetadata: true, askOutputFolder: true, outputFolder: "",
    recent: [{ name: "uygunsuzluk_kayitlari_eylul_anonim.xlsx", path: "C:\\Belgeler\\a.xlsx", when: "20.10.2026 14:12", found: 84 },
      { name: "ic_denetim_raporu_anonim.docx", path: "C:\\Belgeler\\b.docx", when: "18.10.2026 09:40", found: 31 }] };
  const ok = (x) => Promise.resolve({ ok: true, ...x });
  setTimeout(() => {
    if (view === "review" || view === "result") { applyCands({ candidates: cands, documents: ["sikayet_kayitlari_ekim.xlsx"], warnings: [] }); S.selected = 1; S.view = view; }
    if (view === "result") S.saved = { outputs: ["C:\\Users\\ornek\\Belgeler\\Kalite\\sikayet_kayitlari_ekim_anonim.xlsx"], mapping: "C:\\Users\\ornek\\Belgeler\\Kalite\\sikayet_kayitlari_ekim_eslestirme.xlsx", replaced: 16, distinct: 9, skipped: 1, seconds: 0.8, warnings: [] };
    if (view === "reverse") {
      S.tab = "rev";
      const t = "Kök neden: [BİRİM_1] ile [KURUM_1] arasında teslim tarihi teyit süreci yok. [KİŞİ_1]'in şikâyeti ikinci kez geldi. Öneri: [KİŞİ_2] haftalık tedarikçi toplantısını yönetsin.";
      const map = { "[BİRİM_1]": "Satın Alma Birimi", "[KURUM_1]": "Yıldız Makine A.Ş.", "[KİŞİ_1]": "Ahmet Yılmaz", "[KİŞİ_2]": "Ayşe Kaya" };
      Object.assign(S.rev, { path: "x", name: "sikayet_kayitlari_ekim_eslestirme.xlsx", count: 9, text: t, status: "4 kod çevrildi · bilinmeyen kod yok",
        plain: "x", html: esc(t).replace(/\[[^\]]+\]/g, (m) => (map[m] ? `<mark>${esc(map[m])}</mark>` : m)) });
    }
    render();
    if (view === "settings") renderSettings();
  }, 0);
  return {
    hello: () => ok({ version: "0.2.0", ner: true, types, defaults: { headers: { "ad soyad": "KİŞİ", "telefon": "TELEFON", "tc kimlik no": "TC", "birim": "BİRİM" } }, prefs }),
    set_prefs: (p) => ok({ prefs: p }), choose_files: () => Promise.resolve([]), cancel: () => ok({}),
  };
}
