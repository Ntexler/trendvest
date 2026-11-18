/* The virtual wallet page. Storage: the artifact's server-side database, in the viewer's private area
   (data/users/<id>/wallet). Only the owner's decisions are stored (an event list per portfolio);
   every balance is recomputed by engine.js from real daily closes, so all devices agree. */
(async () => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const ils = (v) => (v < 0 ? "−" : "") + Math.abs(Math.round(v)).toLocaleString("en-US") + " ₪";
  const hd = (d) => (d ? d.split("-").reverse().map(Number).join(".") : "");
  const page = $("page"), E = window.TVEngine;
  document.getElementById("foot").textContent = "כסף וירטואלי בלבד. החישוב לפי מחירי סוף יום אמיתיים, עמלות לפי מחירוני הברוקרים, ומס רווח הון לפי הכללים בישראל (בפישוט). זה כלי ללמידה, לא המלצה.";
  page.innerHTML = '<p class="lead">טוען מחירים...</p>';
  const [px, F] = await Promise.all([fetch("data/wallet_px.json").then((r) => r.json()), fetch("data/wallet_fees.json").then((r) => r.json())]);
  const last = px.dates[px.dates.length - 1], first = px.dates[0];
  const names = Object.entries(px.co).map(([t, c]) => [t, c.name]).sort((a, b) => a[1].localeCompare(b[1]));
  const broker = (id) => F.brokers.find((b) => b.id === id) || F.brokers[0];

  /* ---------- storage: server first, this browser as a fallback ---------- */
  let store = { portfolios: [], active: null }, where = "local", ref = null;
  try {
    const C = typeof claude !== "undefined" ? claude : null; const db = C ? await C.use("db") : null, user = C ? await C.use("user") : null;
    const uid = user ? await user.id() : null;
    if (db && uid) {
      ref = db.doc("data/users/" + uid + "/wallet");
      const snap = await ref.get();
      if (snap.exists) store = Object.assign(store, snap.data());
      where = "server";
    }
  } catch (e) { where = "local"; }
  if (where === "local") { try { const x = localStorage.getItem("tv-wallet"); if (x) store = JSON.parse(x); } catch (e) {} }
  async function save() {
    if (ref) { try { await ref.set(store); return; } catch (e) { where = "local"; } }
    try { localStorage.setItem("tv-wallet", JSON.stringify(store)); } catch (e) {}
  }

  let ui = { form: null, msg: "" };
  const P = () => store.portfolios.find((p) => p.id === store.active) || store.portfolios[0];
  const uid = () => Math.random().toString(36).slice(2, 10);

  /* ---------- pieces ---------- */
  const tag = (t, c) => `<span class="tag" style="background:${c}">${t}</span>`;
  const kindLbl = { deposit: "הפקדה", buy: "קנייה", sell: "מכירה", rule: "פקודה בוצעה", rule_set: "פקודה נקבעה", rule_off: "פקודה בוטלה", dividend: "דיבידנד", custody: "דמי ניהול", withdraw: "משיכה", error: "לא בוצע" };
  function brokerOptions(sel) { return F.brokers.map((b) => `<option value="${b.id}" ${b.id === sel ? "selected" : ""}>${esc(b.name)}</option>`).join(""); }
  function chart(daily) {
    const pts = daily.filter((_, k) => k % 3 === 0 || k === daily.length - 1), W = 700, H = 120;
    const v = pts.map((d) => d[1] + d[2]), lo = Math.min(...v), hi = Math.max(...v);
    const X = (k) => (k / (pts.length - 1 || 1)) * W, Y = (x) => H - 6 - ((x - lo) / (hi - lo || 1)) * (H - 12);
    return `<svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto;direction:ltr" role="img" aria-label="שווי התיק לאורך זמן"><path d="M${v.map((x, k) => `${X(k).toFixed(1)} ${Y(x).toFixed(1)}`).join("L")}" fill="none" stroke="var(--ink)" stroke-width="2.5"/></svg>
      <div class="hrow small"><span>${hd(pts[0][0])}</span><span>${hd(pts[pts.length - 1][0])}</span></div>`;
  }
  function form() {
    const p = P(), r = ui.res, pos = r ? r.positions.filter((x) => x.shares > 0) : [];
    const evd = (p.events || []).map((e) => e.date).sort(), dflt = ui.date || evd[evd.length - 1] || last;
    const date = `<label class="fl">תאריך<input type="date" name="date" value="${dflt}" min="${first}" max="${last}"></label><span class="small">אפשר לבחור תאריך בעבר, כדי לראות מה היה קורה.</span>`;
    const co = `<label class="fl">חברה<input name="co" list="wl-names" placeholder="שם או סימול" required></label><datalist id="wl-names">${names.map(([t, n]) => `<option value="${esc(n)} · ${t}">`).join("")}</datalist>`;
    const f = ui.form;
    if (f === "deposit") return `<form data-f="deposit" class="wform"><label class="fl">סכום בשקלים<input name="amount" type="number" min="1" step="1" value="5000" required></label>${date}<button class="go">להפקיד</button></form>`;
    if (f === "withdraw") return `<form data-f="withdraw" class="wform"><label class="fl">מאיזו קופה<select name="from"><option value="profits">קופת רווחים</option><option value="principal">הקרן שחזרה</option><option value="cash">מזומן</option></select></label><label class="fl">סכום<input name="amount" type="number" min="1" required></label>${date}<button class="go">למשוך</button></form>`;
    if (f === "buy") return `<form data-f="buy" class="wform">${co}<label class="fl">כמה שקלים להשקיע (כולל עמלות)<input name="amount" type="number" min="1" value="5000" required></label>${date}<button class="go">לקנות</button></form>`;
    if (f === "sell") return pos.length ? `<form data-f="sell" class="wform"><label class="fl">מה למכור<select name="ticker">${pos.map((x) => `<option value="${x.ticker}">${esc(x.name)}</option>`).join("")}</select></label><label class="fl">כמה<select name="fraction"><option value="1">הכול</option><option value="0.5">חצי</option><option value="0.25">רבע</option></select></label>${date}<button class="go">למכור</button></form>` : `<p class="small">אין מה למכור.</p>`;
    if (f === "rule") return `<form data-f="rule" class="wform">${pos.length ? `<label class="fl">על איזו מניה<select name="ticker">${pos.map((x) => `<option value="${x.ticker}">${esc(x.name)}</option>`).join("")}</select></label>` : co}
      <label class="fl">הפקודה<select name="kind">
        <option value="return_principal">כשההשקעה תכפיל את עצמה: להחזיר לי את הקרן</option>
        <option value="trailing_stop">אם תרד ממה שהיה השיא: למכור הכול</option>
        <option value="stop_loss">אם תרד ממה שהשקעתי: למכור הכול</option>
        <option value="take_profit">כשההשקעה תגיע לפי X: למכור הכול</option>
        <option value="sweep_profit">בכל פעם שיש רווח של X שקלים: להעביר לקופת רווחים</option></select></label>
      <label class="fl">כמה (פי, אחוז או שקלים, לפי הפקודה)<input name="param" type="number" step="any" placeholder="למשל 2, או 25, או 1000"></label>
      <label class="ck"><input type="checkbox" name="after" checked> בירידה מהשיא: להתחיל לעקוב רק אחרי שהקרן חזרה</label>${date}<button class="go">לקבוע פקודה</button></form>`;
    return "";
  }

  function render() {
    const p = P();
    if (!p) {
      page.innerHTML = `<div><span class="kicker">כסף וירטואלי · ${where === "server" ? "נשמר בשרת" : "נשמר רק בדפדפן הזה"}</span><h1>הארנק שלי</h1></div>
        <p class="lead">כאן משקיעים כסף לא אמיתי במניות אמיתיות, וקובעים מראש פקודות: מתי להחזיר את הקרן, מתי למכור, ולאן יעבור הרווח.</p>${newForm(true)}`;
      return;
    }
    const fees = broker(p.broker), opts = { fees, service_fee_ils: +p.service_fee || 0 };
    const r = (ui.res = E.replay(p, px, opts)), s = r.summary, nr = E.replay(p, px, Object.assign({}, opts, { rules: false })).summary;
    const hasRules = (p.events || []).some((e) => e.type === "rule");
    page.innerHTML = `
      <div><span class="kicker">כסף וירטואלי · ${where === "server" ? "נשמר בשרת, זמין מכל מכשיר" : "נשמר רק בדפדפן הזה"} · מחירים נכון ל-${hd(last)}</span><h1>הארנק שלי</h1></div>
      <div class="chips">${store.portfolios.map((x) => `<button data-pf="${x.id}" aria-pressed="${x.id === p.id}">${esc(x.name)}</button>`).join("")}<button data-act="new">+ תיק חדש</button></div>
      ${ui.form === "new" ? newForm(false) : ""}
      ${ui.msg ? `<div class="band tint-next">${esc(ui.msg)}</div>` : ""}
      <section class="band tint-stock">${tag(esc(p.name), "var(--c-stock)")}
        <span class="small">יש לך היום</span><b style="font-size:38px;font-weight:800;line-height:1">${ils(s.worth)}</b>
        <span>${s.deposited ? `הפקדת ${ils(s.deposited)}${s.withdrawn ? `, משכת ${ils(s.withdrawn)}` : ""}. ${s.result >= 0 ? "▲ רווח" : "▼ הפסד"} של ${ils(Math.abs(s.result))} אחרי מס ועמלות.` : "עוד לא הפקדת כסף לתיק הזה."}</span>
        ${r.daily.length > 2 && s.deposited ? chart(r.daily) : ""}</section>
      <div class="grid2">
        <div class="box tint-chain"><span class="small">מושקע עכשיו</span><b>${ils(s.holdings)}</b></div>
        <div class="box"><span class="small">מזומן שלא הושקע</span><b>${ils(s.cash)}</b></div>
        <div class="box tint-stock"><span class="small">הקרן שחזרה אליך</span><b>${ils(s.principal)}</b></div>
        <div class="box tint-value"><span class="small">קופת רווחים</span><b>${ils(s.profits)}</b><span class="small">אחרי מס ועמלות</span></div></div>
      <div class="band">${tag("פעולות", "var(--c-next)")}
        <div class="chips">${[["deposit", "הפקדה"], ["buy", "קנייה"], ["sell", "מכירה"], ["rule", "פקודה חדשה"], ["withdraw", "משיכה"]].map(([k, t]) => `<button data-form="${k}" aria-pressed="${ui.form === k}">${t}</button>`).join("")}</div>
        ${form()}</div>
      ${r.positions.length ? `<div class="band">${tag("מה בתיק", "var(--c-stock)")}${r.positions.map((x) => `<div class="kv"><span><b>${esc(x.name)}</b> <span class="small">${x.shares > 0 ? `${x.shares} מניות` : "נמכרה"}</span></span><span>${x.shares > 0 ? `${ils(x.value)} <span class="small">${x.unrealized >= 0 ? "▲" : "▼"} ${ils(Math.abs(x.unrealized))}</span>` : `<span class="small">חזרו ${ils(x.returned)} מתוך ${ils(x.invested)}</span>`}</span></div>`).join("")}</div>` : ""}
      ${r.rules.length ? `<div class="band">${tag("הפקודות שלך", "var(--c-next)")}${r.rules.map((x) => `<div class="why ${x.active ? "" : "unk"}"><span>${esc(E.describe(x, (px.co[x.ticker] || {}).name || x.ticker))}</span>
        <span class="small">${x.done ? `בוצעה ב-${hd(x.done)}` : x.active ? "פעילה. נבדקת בכל סוף יום, ומבוצעת במחיר הסגירה של היום שאחרי." : "בוטלה"}</span>
        ${x.active ? `<button class="linkbtn" data-off="${x.id}" style="align-self:flex-start">לבטל</button>` : ""}</div>`).join("")}
        ${hasRules ? `<div class="bottom"><b>ומה אם לא היו פקודות?</b><span>אותן פעולות בלי הפקודות: ${ils(nr.worth)} היום, לעומת ${ils(s.worth)} עם הפקודות. פקודות לא מרוויחות יותר. הן קובעות מראש כמה סיכון לוקחים.</span></div>` : ""}</div>` : ""}
      <div class="band tint-value">${tag("מה זה עלה לך", "var(--c-value)")}
        <div class="kv"><span>עמלות קנייה ומכירה</span><b>${ils(s.fees.commission)}</b></div>
        <div class="kv"><span>המרת מטבע</span><b>${ils(s.fees.fx)}</b></div>
        <div class="kv"><span>מסים של הבורסות</span><b>${ils(s.fees.market)}</b></div>
        ${s.fees.custody ? `<div class="kv"><span>דמי ניהול חשבון</span><b>${ils(s.fees.custody)}</b></div>` : ""}
        <div class="kv"><span>עמלת שירות על פקודות אוטומטיות</span><b>${ils(s.fees.service)}</b></div>
        <div class="kv"><span>מס רווח הון ששולם</span><b>${ils(s.capital_tax)}</b></div>
        <div class="kv"><span>מס על דיבידנדים</span><b>${ils(s.dividend_tax)}</b></div>
        ${s.tax_if_sold_today ? `<div class="kv"><span>מס שתשלם אם תמכור הכול היום</span><b>${ils(s.tax_if_sold_today)}</b></div>` : ""}
        <span class="small">ברוקר: ${esc(fees.name)}${fees.other_assumed ? ". למניות מחוץ לארה\"ב ולתל אביב לא מצאנו מחירון, וחישבנו כמו בארה\"ב" : ""}. מחירונים נבדקו ב-${hd(F.checked)}. המס: 25% על הרווח האמיתי, בניכוי שינויי שער המטבע, עם קיזוז הפסדים באותה שנה. לא כולל מס יסף.</span></div>
      <div class="band">${tag("מה קרה, לפי הסדר", "var(--c-news)")}${r.log.slice().reverse().slice(0, ui.allLog ? 999 : 12).map((l) => `<div class="kv"><span><span class="small">${hd(l.date)} · ${kindLbl[l.kind] || l.kind}</span><br>${esc(l.text)}</span><b>${l.amount != null ? ils(l.amount) : l.toPrincipal != null ? ils(l.toPrincipal + l.toProfit) : l.net != null ? ils(l.net) : l.fee != null ? ils(-l.fee) : ""}</b></div>`).join("") || '<span class="small">עוד לא קרה כלום.</span>'}
        ${r.log.length > 12 && !ui.allLog ? `<button class="pillbtn" data-act="alllog" style="align-self:flex-start">עוד ${r.log.length - 12}</button>` : ""}</div>
      <div class="band">${tag("הגדרות התיק", "var(--muted)")}
        <label class="fl">ברוקר<select data-set="broker">${brokerOptions(p.broker)}</select></label>
        <label class="fl">עמלת שירות לכל פקודה אוטומטית שמתבצעת (בשקלים)<input data-set="service_fee" type="number" min="0" step="0.5" value="${+p.service_fee || 0}"></label>
        <span class="small">כשזה יהיה מוצר, ביצוע אוטומטי של פקודה יעלה עמלת שירות. כאן אפשר לראות כמה זה היה מוריד מהרווח.</span>
        <div class="chips"><button data-act="undo">לבטל את הפעולה האחרונה</button><button data-act="delete">למחוק את התיק</button></div></div>`;
  }
  function newForm(firstOne) {
    return `<form data-f="new" class="band wform">${tag(firstOne ? "התיק הראשון שלך" : "תיק חדש", "var(--c-stock)")}
      <label class="fl">שם התיק<input name="name" value="${firstOne ? "התיק שלי" : "תיק " + (store.portfolios.length + 1)}" required></label>
      <label class="fl">דרך איזה ברוקר (קובע את העמלות)<select name="broker">${brokerOptions("ibkr")}</select></label>
      <label class="fl">סכום התחלתי בשקלים<input name="amount" type="number" min="0" value="5000"></label>
      <label class="fl">מאיזה תאריך<input type="date" name="date" value="${last}" min="${first}" max="${last}"></label>
      <button class="go">ליצור</button></form>`;
  }

  /* ---------- actions ---------- */
  function tickerOf(v) { const m = String(v || "").match(/·\s*(\S+)\s*$/); if (m && px.co[m[1]]) return m[1];
    const q = String(v || "").trim().toLowerCase(); const hit = names.find(([t, n]) => t.toLowerCase() === q || n.toLowerCase() === q) || names.find(([t, n]) => n.toLowerCase().includes(q));
    return hit ? hit[0] : null; }
  page.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target, kind = f.dataset.f, x = Object.fromEntries(new FormData(f)), p = P();
    // validate everything that comes from the form before it is stored
    if (x.date && (x.date < first || x.date > last || !/^\d{4}-\d{2}-\d{2}$/.test(x.date))) { ui.msg = "התאריך מחוץ לטווח שיש לנו מחירים עבורו."; render(); return; }
    if (x.amount != null && !(+x.amount >= 0 && +x.amount <= 1e9)) { ui.msg = "הסכום לא תקין."; render(); return; }
    if (x.name != null) x.name = String(x.name).slice(0, 60);
    if (x.ticker && !px.co[x.ticker]) { ui.msg = "בחרו מניה מהרשימה."; render(); return; }
    if (x.date) ui.date = x.date;
    ui.msg = "";
    if (kind === "new") {
      const id = uid(), events = +x.amount > 0 ? [{ type: "deposit", date: x.date, amount: +x.amount }] : [];
      store.portfolios.push({ id, name: x.name, broker: x.broker, service_fee: 0, events, created: new Date().toISOString() });
      store.active = id; ui.form = +x.amount > 0 ? "buy" : "deposit";
    } else if (kind === "deposit") p.events.push({ type: "deposit", date: x.date, amount: +x.amount });
    else if (kind === "withdraw") p.events.push({ type: "withdraw", date: x.date, amount: +x.amount, from: x.from });
    else if (kind === "buy") { const t = tickerOf(x.co); if (!t) { ui.msg = "לא מצאנו את החברה. בחרו מהרשימה."; render(); return; }
      p.events.push({ type: "buy", date: x.date, ticker: t, amount: +x.amount }); ui.form = "rule"; }
    else if (kind === "sell") p.events.push({ type: "sell", date: x.date, ticker: x.ticker, fraction: +x.fraction });
    else if (kind === "rule") { const t = x.ticker || tickerOf(x.co); if (!t) { ui.msg = "בחרו מניה."; render(); return; }
      const k = x.kind, v = +x.param, params = k === "return_principal" || k === "take_profit" ? { multiple: v || 2 } : k === "sweep_profit" ? { amount: v || 1000 } : { pct: v || 25, after: k === "trailing_stop" && x.after ? "principal" : undefined };
      p.events.push({ type: "rule", date: x.date, id: uid(), ticker: t, kind: k, params }); ui.form = null; }
    await save(); render();
  });
  page.addEventListener("click", async (ev) => {
    const b = ev.target.closest("[data-pf],[data-act],[data-form],[data-off]"); if (!b) return;
    const p = P(), d = b.dataset;
    if (d.pf) { store.active = d.pf; ui.form = null; await save(); }
    else if (d.form) ui.form = ui.form === d.form ? null : d.form;
    else if (d.off) { p.events.push({ type: "rule_off", date: last, id: d.off }); await save(); }
    else if (d.act === "new") ui.form = ui.form === "new" ? null : "new";
    else if (d.act === "alllog") ui.allLog = true;
    else if (d.act === "undo") { p.events.pop(); await save(); }
    else if (d.act === "delete") { if (!confirm(`למחוק את "${p.name}"? אי אפשר לשחזר.`)) return; store.portfolios = store.portfolios.filter((x) => x.id !== p.id); store.active = null; await save(); }
    render();
  });
  page.addEventListener("change", async (ev) => {
    const el = ev.target.closest("[data-set]"); if (!el) return;
    const k = el.dataset.set;
    if (k === "service_fee") P().service_fee = Math.min(1000, Math.max(0, +el.value || 0));
    else if (k === "broker" && F.brokers.some((b) => b.id === el.value)) P().broker = el.value;
    await save(); render();
  });
  render();
})();
