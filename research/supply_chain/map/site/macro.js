/* The economic calendar page ("הבנקים והמחירים"): reads data/macro.json (research/macro/collect.py, daily run).
   The "what it means for me" band also reads the viewer's own wallet (same private storage as wallet.js). */
(async () => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const hd = (d) => (d ? d.slice(0, 10).split("-").reverse().map(Number).slice(0, 2).join(".") : "");
  const MON = ["ינו׳", "פבר׳", "מרץ", "אפר׳", "מאי", "יוני", "יולי", "אוג׳", "ספט׳", "אוק׳", "נוב׳", "דצמ׳"];
  const MONL = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];
  const WD = ["א׳", "ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳"];
  const TINT = { fed: "var(--t-stock)", boi: "var(--t-stock)", ecb: "var(--t-stock)", boj: "var(--t-stock)", uscpi: "var(--t-next)", ilcpi: "var(--t-next)" };
  const SUB = { fed: "מתפרסם ב־21:00 · אסיה וישראל מגיבות למחרת", uscpi: "מתפרסם ב־15:30 · הבורסה בתל אביב עוד פתוחה",
    ilcpi: "מתפרסם ב־18:30, אחרי סגירת הבורסה · משפיע על המס במניות ישראליות", boi: "מתפרסם ב־16:00",
    ecb: "מתפרסם ב־15:15", boj: "בבוקר שעון ישראל · משפיע על המובילות בניסוי התאום" };
  const page = $("page");
  $("foot").textContent = "מקורות: הפד, בנק ישראל, הבנק המרכזי האירופי, בנק יפן, הלמ״ס, הלשכה האמריקאית לסטטיסטיקה של העבודה. מתעדכן פעם ביום. ללמידה אישית, לא המלצה.";
  page.innerHTML = '<p class="lead">טוען...</p>';
  let M;
  try { M = await (await fetch("data/macro.json")).json(); } catch (e) { page.innerHTML = '<p class="lead">הנתונים של היומן עוד לא זמינים.</p>'; return; }
  const R = M.rates, N = M.noise;

  const upcoming = M.upcoming.length ? M.upcoming.map((u) => { const d = new Date(u.date + "T12:00:00Z");
    return `<div style="display:grid;grid-template-columns:64px minmax(0,1fr) auto;gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)">
      <div style="display:flex;flex-direction:column;align-items:center;background:${TINT[u.kind]};border-radius:14px;padding:6px 0"><b style="font-size:20px;line-height:1.1">${d.getUTCDate()}</b><span class="small">${MON[d.getUTCMonth()]} · ${WD[d.getUTCDay()]}</span></div>
      <div style="display:flex;flex-direction:column;min-width:0"><b>${esc(u.title)}</b><span class="small">${esc(SUB[u.kind])}</span></div>
      <span class="small" style="white-space:nowrap;font-weight:500;color:${u.loud ? "var(--down)" : "var(--muted)"}">${u.loud ? "יום רועש" : u.ratio ? "רגיל" : "–"}</span></div>`; }).join("")
    : '<p class="say" style="margin:0">אין אירועים ב־45 הימים הקרובים.</p>';
  const nz = Object.entries(N).map(([k, z]) => `${{ fed: "הפד", uscpi: "מדד בארה״ב", ilcpi: "מדד בישראל", boj: "בנק יפן" }[k] || k}: ${z.event_avg}% מול ${z.all_avg}%`).join(" · ");

  const chg = (c) => !c ? "" : `שינוי אחרון: ${c.delta > 0 ? "▲" : "▼"} ${Math.abs(c.delta).toFixed(2)} · ${hd(c.date)}.${c.date.slice(0, 4)}`;
  const tile = (bank, rate, r, tint, note) => `<div class="box" style="background:${tint};border-radius:18px;padding:14px;gap:2px">
      <span class="small" style="color:var(--fg)">${bank}</span><b class="num" style="font-size:30px;line-height:1.1;text-align:right">${rate}</b>
      <span style="font-size:13.5px;font-weight:500">${chg(r.last_change) || "&nbsp;"}</span>
      <span class="small" style="color:var(--fg)">${r.next ? `הבא${r.next_note ? " לפי הלוח שמצאנו" : ""}: ${hd(r.next)}.${r.next.slice(0, 4)}` : "המועד הבא לא ידוע"}${r.next_note ? ` · ${esc(r.next_note)}` : ""}${note ? ` · ${note}` : ""}</span></div>`;
  const rates = `<div class="band"><h2>הריבית עכשיו</h2><div class="grid2">
      ${tile("בנק ישראל", R.boi.rate.toFixed(2) + "%", R.boi, "var(--t-stock)", "")}
      ${tile("הפד (ארה״ב)", R.fed.rate + "%", R.fed, "var(--t-news)", "")}
      ${tile("הבנק האירופי (פיקדון)", R.ecb.rate.toFixed(2) + "%", R.ecb, "var(--t-chain)", "")}
      ${tile("בנק יפן", "–", R.boj, "var(--t-value)", "הריבית לא זמינה")}</div>
    <span class="small">ריבית גבוהה = כסף יקר: לחברות קשה יותר ללוות, ופיקדון בבנק מתחרה במניות. בבנק ישראל ובבנק האירופי התאריך הוא יום הכניסה לתוקף.</span></div>`;

  const il = M.cpi.il, last = il.months[il.months.length - 1], pos = Math.max(0, Math.min(100, last.yoy / 5 * 100));
  const us = M.cpi.us, ul = us.months[us.months.length - 1];
  const mname = (m) => MONL[+m.slice(5) - 1];
  const cpi = `<div class="band"><h2>המחירים בישראל · מדד המחירים לצרכן</h2>
    <div style="display:flex;flex-direction:column"><b class="num" style="font-size:40px;line-height:1.1;text-align:right">${last.yoy.toFixed(1)}%</b>
      <span class="say" style="font-size:15px">עליית מחירים ב־12 חודשים</span>
      <span class="small">מדד ${mname(last.m)}, פורסם ${hd(il.released)} · ב${mname(last.m)} עצמו: <span class="num">${last.mom > 0 ? "+" : ""}${last.mom.toFixed(1)}%</span></span></div>
    <div><div style="position:relative;height:26px;direction:ltr">
        <div style="position:absolute;left:0;right:0;top:10px;height:6px;background:var(--line);border-radius:3px"></div>
        <div style="position:absolute;left:${il.target[0] / 5 * 100}%;width:${(il.target[1] - il.target[0]) / 5 * 100}%;top:6px;height:14px;background:var(--t-chain);border:1.5px solid var(--c-chain);border-radius:7px;box-sizing:border-box"></div>
        <div style="position:absolute;left:${pos}%;top:3px;width:20px;height:20px;margin-left:-10px;border-radius:50%;background:var(--ink)"></div></div>
      <div class="ends" style="direction:ltr"><span>0%</span><span dir="rtl">יעד בנק ישראל: 1%–3%</span><span>5%</span></div></div>
    <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;font-size:13.5px">${il.months.slice(-3).map((m) => `<div class="box" style="background:var(--soft)"><b class="num" style="text-align:right">${m.yoy.toFixed(1)}%</b><span class="small">${mname(m.m)}</span></div>`).join("")}</div>
    <span class="small">ארה״ב: <b class="num">${ul ? ul.yoy.toFixed(1) + "%" : "–"}</b> ב־12 חודשים (${ul ? mname(ul.m) : ""}) · יעד הפד: 2%.</span></div>`;

  /* ---------- what it means for me: the viewer's own wallet ---------- */
  let mine = "<div>טוען את הארנק...</div>";
  const meBand = () => `<div class="band tint-value" style="border:0">${'<span class="tag" style="background:var(--c-value)">מה זה אומר לי</span>'}
    <div style="display:flex;flex-direction:column;gap:10px;font-size:15.5px">${mine}
      <div><b>ניסוי התאום:</b> בדקנו — ימי החלטות ריבית לא משנים את האות. הניסוי ממשיך כרגיל.</div>
      <div><b>לפני קנייה:</b> ביום רועש המחיר יכול לקפוץ לשני הכיוונים באותו יום. זה לא סיבה לא לקנות, רק לא להיבהל.</div></div></div>`;

  const ago = new Date(); ago.setUTCDate(ago.getUTCDate() - 92); const since = ago.toISOString().slice(0, 10);
  const KN = { fed: "הפד", uscpi: "מדד ארה״ב", ilcpi: "מדד ישראל", boj: "בנק יפן", ecb: "הבנק האירופי" };
  const home = { fed: "us", uscpi: "us", ilcpi: "il", boj: "jp", ecb: "eu" };
  const IDX = { us: "S&P 500", il: "ת״א 125", jp: "ניקיי", eu: "יורו סטוקס 50" };
  const recent = M.events.filter((e) => e.date >= since).reverse();
  const hist = `<details class="band"><summary>מה קרה ב־3 החודשים האחרונים (${recent.length})</summary><div class="now" style="margin-top:10px">
    ${recent.map((e) => { const r = e.react[home[e.kind]], ri = e.react.il;
      return `<div><b>${hd(e.date)} · ${esc(e.label)}</b><span class="small">${r ? `${IDX[home[e.kind]]} ביום התגובה: <span class="num">${r[1] > 0 ? "+" : ""}${r[1].toFixed(1)}%</span>` : ""}${ri && home[e.kind] !== "il" ? ` · ת״א 125: <span class="num">${ri[1] > 0 ? "+" : ""}${ri[1].toFixed(1)}%</span>` : ""}</span></div>`; }).join("")}</div>
    <span class="small">״יום התגובה״: היום הראשון שהבורסה יכלה להגיב. תנועה ביום כזה לא בהכרח נגרמה מהאירוע.</span></details>`;

  const render = () => {
    page.innerHTML = `<div style="display:flex;flex-direction:column;gap:8px"><span class="kicker">TrendVest · יומן כלכלי · עודכן ${hd(M.updated_utc)}</span><h1>הבנקים והמחירים</h1>
      <p class="lead">רוב הימים זה לא משנה למניה אחת. בימים שכן — כאן רואים מה קרה ומה עוד מחכה.</p></div>
      <div class="band"><h2>מה מחכה · 45 הימים הבאים</h2>${upcoming}
        <span class="small">״יום רועש״: בימים כאלה מאז 2016, מדד הבורסה הביתית זז בממוצע לפחות 15% יותר מביום רגיל (${nz}). השעות — שעון ישראל.</span></div>
      ${rates}${cpi}${meBand()}${hist}
      <p class="small" style="margin:0">חסר כרגע: ${M.missing.map(esc).join(" · ")}.</p>`;
  };
  render();

  try {
    const [px, F] = await Promise.all([fetch("data/wallet_px.json").then((r) => r.json()), fetch("data/wallet_fees.json").then((r) => r.json())]);
    if (!window.TVEngine) await new Promise((ok, no) => { const s = document.createElement("script"); s.src = "engine.js"; s.onload = ok; s.onerror = no; document.body.appendChild(s); });
    let store = null;
    try {
      const C = typeof claude !== "undefined" ? claude : null, db = C ? await C.use("db") : null, user = C ? await C.use("user") : null, uid = user ? await user.id() : null;
      if (db && uid) { const snap = await db.doc("data/users/" + uid + "/wallet").get(); if (snap.exists) store = snap.data(); }
    } catch (e) { store = null; }
    if (!store) { try { const x = localStorage.getItem("tv-wallet"); if (x) store = JSON.parse(x); } catch (e) {} }
    const ps = (store && store.portfolios) || [];
    let n = 0, exempt = 0, done = 0;
    for (const p of ps) {
      const fees = F.brokers.find((b) => b.id === p.broker) || F.brokers[0];
      const r = window.TVEngine.replay(p, px, { fees, service_fee_ils: +p.service_fee || 0 });
      r.positions.filter((x) => x.cur === "ILS" && x.shares > 0).forEach((x) => { n++; exempt += x.infl_exempt || 0; });
      r.log.filter((l) => l.kind === "sell" || l.kind === "rule").forEach((l) => { done += l.infl || 0; });
    }
    const ils = (v) => Math.round(v).toLocaleString("en-US") + " ₪";
    mine = n || done ? `<div><b>הארנק:</b> ${n ? `יש לך ${n} ${n === 1 ? "מניה ישראלית" : "מניות ישראליות"}. המדד קובע כמה מהרווח עליהן פטור ממס — כרגע ${ils(exempt)} מהרווח לא יחויבו במס בזכות האינפלציה.` : ""}${done ? ` במכירות שכבר עשית נחסך מס על ${ils(done)} של רווח אינפלציוני.` : ""}</div>`
      : `<div><b>הארנק:</b> אין לך עכשיו מניות ישראליות בארנק. כשיהיו — המדד יקבע כמה מהרווח עליהן פטור ממס, והחישוב יופיע כאן.</div>`;
  } catch (e) { mine = "<div><b>הארנק:</b> לא הצלחנו לטעון את הארנק כרגע.</div>"; }
  render();
})();
