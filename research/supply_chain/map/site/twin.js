/* The twin experiment page: reads data/twin_live.json (written by research/twin_live/live.py on every daily run).
   Nothing here decides anything; the rules are locked in research/twin_live/rules.json. */
(async () => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const hd = (d) => (d ? d.slice(0, 10).split("-").reverse().map(Number).slice(0, 2).join(".") : "");
  const pct = (v, d = 1) => v == null ? "–" : `<span class="num ${v > 0 ? "up" : v < 0 ? "down" : "flat"}">${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}%</span>`;
  const page = $("page");
  $("foot").textContent = "כסף וירטואלי בלבד. ניסוי למידה אישי, לא המלצה לקנות או למכור. המחירים מ-Yahoo Finance, מתעדכנים פעם ביום.";
  page.innerHTML = '<p class="lead">טוען...</p>';
  let D;
  try { D = await (await fetch("data/twin_live.json")).json(); } catch (e) { page.innerHTML = '<p class="lead">הנתונים של הניסוי עוד לא זמינים.</p>'; return; }
  const E = D.experiment, Cn = D.control, B = D.backtest, n = E.closed || 0;
  const lock = '<svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path></svg>';
  const why = { opened_up: (g) => `לא נקנה: נפתח בעלייה של ${Math.abs(g).toFixed(1)}%`, already_holding: () => "לא נקנה: כבר מחזיקים אותה" };

  const status = `<div class="band"><h2>איפה אנחנו עומדים</h2>
    <div class="tiles">
      <div class="tile"><span class="big num">${n}</span><span class="w">עסקאות נסגרו</span><span class="l">מתוך כ־${D.need} שצריך</span></div>
      <div class="tile"><span class="big">${n ? pct(E.mean_net_pct) : "–"}</span><span class="w">ממוצע לעסקה</span><span class="l">מעבר לרגיל, אחרי עמלות</span></div>
      <div class="tile"><span class="big num muted">+${B.mean_net_pct.toFixed(1)}%</span><span class="w">מה שהעבר הבטיח</span><span class="l">${B.trades.toLocaleString("en-US")} עסקאות, ${B.years}</span></div>
    </div>
    <div><div class="meter" style="direction:rtl"><i style="right:${Math.min(100, n / D.need * 100)}%;margin-left:0;margin-right:-9px"></i></div>
      <div class="ends"><span>התחלה · ${hd(D.start)}</span><span>אפשר לשפוט · בערך שנה וחצי</span></div></div>
    <p class="say" style="margin:0;background:var(--soft);border-radius:14px;padding:12px 14px">${n ? "" : "עוד אין עסקאות שנסגרו: הראשונה תיסגר 10 ימי מסחר אחרי הקנייה הראשונה. "}עד שיהיו כ־${D.need} עסקאות, כל תוצאה — טובה או רעה — יכולה להיות מזל. רק בערך אחת מכל שתיים מרוויחה; הרווח בא מעודף קטן על פני הרבה עסקאות.</p>
    ${n ? `<span class="small">${E.won_pct}% מהעסקאות הרוויחו · סה״כ ${E.sum_usd >= 0 ? "+" : "−"}$${Math.abs(E.sum_usd).toLocaleString("en-US")} על עסקאות של $10,000</span>` : ""}</div>`;

  const card = (p) => `<div class="band tint-chain" style="border:0;gap:10px">
      <div class="chain3" style="grid-template-columns:1fr auto 1fr">
        <div class="col"><span>קפצה · ${esc(p.city)} · ${hd(p.leader_date)}</span><b style="font-size:18px">${esc(p.leader)}</b>${pct(p.jump)} <span>מעבר למדד</span></div>
        <span class="to" aria-hidden="true">←</span>
        <div class="col"><span>התאום · ניו יורק</span><b style="font-size:18px">${esc(p.twin)} · <span class="num">${esc(p.twin_t)}</span></b><span>אותו תחום</span></div>
      </div>
      <div style="display:flex;flex-direction:column;gap:4px;font-size:15px">
        <span>✓ נסחר בניו יורק</span>
        ${p.holding ? "<span>✗ כבר מחזיקים אותה — לא תיקנה שוב</span>" : "<span>○ נפתח בלי עלייה? ייבדק בפתיחה בניו יורק (16:30 שעון ישראל)</span>"}
      </div>
      <span class="small">${p.holding ? "" : "אם יעבור: קנייה וירטואלית ב־$10,000 במחיר הפתיחה. התוצאה תופיע מחר."}</span></div>`;
  const today = `<div class="band"><h2>היום · עודכן ${hd(D.updated_utc)} ${esc(D.updated_utc.slice(11))} UTC</h2>
    ${D.pending.length ? D.pending.map(card).join("") : '<p class="say" style="margin:0">אין היום אות. זה רוב הימים.</p>'}
    ${D.recent.length ? `<details><summary>ההחלטות האחרונות</summary><div class="now" style="margin-top:10px">${D.recent.map((r) => `<div><b>${hd(r.entry)} · ${esc(r.twin)} <span class="num">${esc(r.twin_t)}</span></b><span>${r.bought ? "נקנה בפתיחה" : why[r.why](r.gap)}</span><small>בעקבות ${esc(r.leader)} (${esc(r.city)}) ${pct(r.jump)}</small></div>`).join("")}</div></details>` : ""}</div>`;

  const dots = (k) => `<span class="dots" role="img" aria-label="יום ${k} מתוך 10">${Array.from({ length: 10 }, (_, i) => `<i class="${i < k ? "on" : "off"}" style="border-color:${i < k ? "var(--ink)" : "var(--line)"};background:${i < k ? "var(--ink)" : "none"};width:14px;height:14px"></i>`).join("")}</span>`;
  const open = `<div class="band"><h2>פתוחות עכשיו · ${D.open.length}</h2>
    ${D.open.length ? `<div style="display:flex;flex-direction:column;gap:12px">${D.open.map((o) => `<div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px 12px;padding-bottom:10px;border-bottom:1px solid var(--line)"><div style="display:flex;flex-direction:column;min-width:0;flex:1 1 180px"><b>${esc(o.twin)} <span class="num small">${esc(o.twin_t)}</span></b><span class="small">בעקבות ${esc(o.leader)} · נקנתה ${hd(o.entry)}</span></div><div style="display:flex;align-items:center;gap:12px">${dots(o.days)}<b style="min-width:58px;text-align:left">${pct(o.net_pct)}</b></div></div>`).join("")}</div>
    <span class="small">נקודה = יום מסחר מתוך 10. המספר: עד כה, מעבר לרגיל של המניה, לפני עמלות.</span>` : '<span class="small">אין עסקאות פתוחות.</span>'}</div>`;

  const rows = [["ניסוי התאום", E.closed ? E.mean_net_pct : null, "var(--ink)"], ["כל התאומים, בלי סינון", Cn.closed ? Cn.mean_net_pct : null, "var(--flat)"]];
  const mx = Math.max(1, ...rows.map((r) => Math.abs(r[1] || 0)));
  const compare = `<div class="band"><h2>מול מה משווים</h2>
    <p class="say" style="margin:0">כדי לדעת שהסינון עוזר, ארנק וירטואלי שני רץ לידו באותם ימים: קונה כל תאום, בכל בורסה, בלי לבדוק את הפתיחה.</p>
    <div class="cmp">${rows.map((r) => `<span>${r[0]}</span><div class="t"><i style="width:${Math.abs(r[1] || 0) / mx * 100}%;background:${r[2]}"></i></div><b>${r[1] == null ? "–" : pct(r[1])}</b>`).join("")}</div>
    <span class="small">ממוצע לעסקה שנסגרה, אחרי עמלות. ניסוי: ${E.closed || 0} עסקאות · השוואה: ${Cn.closed || 0}. בעבר: ${pct(B.mean_net_pct)} מול ${pct(B.control_mean_net_pct)}.</span></div>`;

  const rules = `<div class="band"><div style="display:flex;justify-content:space-between;align-items:center"><h2>הכללים · נעולים מ־${hd(D.start)}.${D.start.slice(0, 4)}</h2><span class="muted">${lock}</span></div>
    <ol style="margin:0;padding-inline-start:20px;display:flex;flex-direction:column;gap:8px">${D.rules_he.map((r) => `<li>${esc(r)}</li>`).join("")}</ol>
    <p class="small" style="margin:0;background:var(--soft);border-radius:14px;padding:10px 14px">שינוי כלל מתחיל ניסוי חדש מאפס. ככה אי אפשר ״לתקן״ אחרי שרואים תוצאות. מזהה הניסוי: <span class="num">${esc(D.id)} · ${esc(D.hash)}</span></p></div>`;

  const closed = `<div class="band"><h2>נסגרו · ${D.closed.length}</h2>
    ${D.closed.length ? `<div class="cmp" style="grid-template-columns:auto minmax(0,1fr) auto">${D.closed.map((c) => `<span class="small num">${hd(c.exit)}</span><span><b>${esc(c.twin)}</b> <span class="small">בעקבות ${esc(c.leader)}</span></span><b>${pct(c.net_pct)}</b>`).join("")}</div>` : '<span class="small">עוד לא נסגרה אף עסקה.</span>'}</div>`;

  page.innerHTML = `<div style="display:flex;flex-direction:column;gap:8px"><a class="kicker" href="#wallet" id="back">הארנק שלי ›</a><h1>ניסוי התאום</h1>
    <p class="lead">כשחברה באסיה קופצת בגלל חדשות שלה, קונים בכסף וירטואלי את ״התאום״ שלה בניו יורק — אם הוא עוד לא זז — ומוכרים אחרי 10 ימי מסחר.</p>
    <span class="small">ניסוי מכאן והלאה, על ימים שעוד לא ראינו. רץ לבד כל יום; אין מה ללחוץ.</span></div>
    ${status}${today}${open}${compare}${rules}${closed}`;
  $("back").addEventListener("click", (e) => { e.preventDefault(); location.hash = "wallet"; location.reload(); });
})();
