// node research/wallet/tests/engine.test.js
const assert = require("assert");
const E = require("../engine.js");
const px = require("../../supply_chain/map/site/data/wallet_px.json");
const free = { id: "free", commission: { US: null, TA: null, other: null }, fx_pct: 0, custody: null };
const noTax = { rate: 0, dividend_total: 0 };
const i0 = px.dates.findIndex((d) => d >= "2024-11-22");
const d0 = px.dates[i0], last = px.dates.length - 1;
const mu = px.co.MU;
let pass = 0; const ok = (c, m) => { assert(c, m); pass++; };

// 1. No costs, no tax, no rules: value follows price x shekel rate exactly.
{
  const r = E.replay({ events: [{ type: "deposit", date: d0, amount: 5000 }, { type: "buy", date: d0, ticker: "MU", amount: 5000 }] }, px, { fees: free, tax: noTax });
  const divsIls = mu.div.filter(([d]) => d > d0).reduce((s, [d, a]) => s + a * px.fx.USD[px.dates.indexOf(d)] * (5000 / (mu.px[i0] * px.fx.USD[i0])), 0);
  const expect = 5000 * (mu.px[last] * px.fx.USD[last]) / (mu.px[i0] * px.fx.USD[i0]);
  ok(Math.abs(r.summary.holdings - expect) < 1, `holdings ${r.summary.holdings} vs ${expect}`);
  ok(Math.abs(r.summary.profits - divsIls * 0.75) < 1, "dividends paid into profits after the 25% US withholding");
}
// 2. Return principal at x2: exactly the invested amount lands in principal, after fees and tax.
const fees = { id: "test", commission: { US: { per_share: 0.005, min: 1, max_pct: 0.01, cur: "USD" }, TA: { pct: 0.001, min: 5, cur: "ILS" }, other: { pct: 0.001, min: 5, cur: "USD" } }, fx_pct: 0.002, custody: null };
const evs = [{ type: "deposit", date: d0, amount: 5000 }, { type: "buy", date: d0, ticker: "MU", amount: 5000 },
  { type: "rule", date: d0, id: "r1", ticker: "MU", kind: "return_principal", params: { multiple: 2 } },
  { type: "rule", date: d0, id: "r2", ticker: "MU", kind: "trailing_stop", params: { pct: 25, after: "principal" } }];
const r = E.replay({ events: evs }, px, { fees, service_fee_ils: 5 });
const rp = r.log.find((l) => l.kind === "rule" && l.text.includes("הקרן"));
ok(rp && Math.abs(rp.toPrincipal - 5000) < 2, `principal back ${rp && rp.toPrincipal}`);
ok(Math.abs(r.summary.principal - 5000) < 2, "principal bucket holds 5000");
ok(rp.tax > 0 && rp.fees > 0 && rp.service === 5, "tax, fees and service fee charged");
const ts = r.log.find((l) => l.kind === "rule" && l.text.includes("מהשיא"));
ok(ts && ts.date > rp.date, "trailing stop fires after principal came back");
// 3. Money is conserved: worth = deposited + result, and every shekel is in a bucket.
const s = r.summary;
ok(Math.abs(s.worth - (s.cash + s.principal + s.profits + s.holdings)) < 0.05, "buckets add up");
// 4. Without rules the same events just hold.
const nr = E.replay({ events: evs }, px, { fees, rules: false });
ok(nr.summary.principal === 0 && nr.positions[0].shares > 0, "rules off: nothing sold");
// 5. A loss offsets a gain in the same year: tax refunded.
{
  const y = px.dates.findIndex((d) => d >= "2025-01-02"), ye = px.dates.findIndex((d) => d >= "2025-12-01");
  const pr = E.replay({ events: [{ type: "deposit", date: px.dates[y], amount: 20000 },
    { type: "buy", date: px.dates[y], ticker: "MU", amount: 10000 }, { type: "buy", date: px.dates[y], ticker: "INTC", amount: 10000 },
    { type: "sell", date: px.dates[ye], ticker: "MU", fraction: 1 }, { type: "sell", date: px.dates[ye], ticker: "INTC", fraction: 1 }] }, px, { fees: free, tax: { rate: 0.25, dividend_total: 0 } });
  const gains = pr.log.filter((l) => l.kind === "sell").reduce((a, l) => a + l.gain, 0);
  ok(Math.abs(pr.summary.capital_tax - Math.max(0, gains) * 0.25) < 1, `year tax on net gain ${pr.summary.tax_paid} vs ${gains * 0.25}`);
}
// 7. Israeli shares: only the gain beyond inflation (known CPI at sale vs. purchase) is taxed.
{
  const t = "ESLT.TA", c = px.co[t], ctx = E._ctx ? null : null;
  const b = px.dates.findIndex((d) => d >= "2024-11-22"), e = px.dates.findIndex((d) => d >= "2026-10-20");
  const known = (d) => { const [y, m, dd] = d.split("-").map(Number); const k = new Date(Date.UTC(y, m - 1 - (dd > 15 ? 1 : 2), 1)).toISOString().slice(0, 7);
    return px.cpi_il[Object.keys(px.cpi_il).filter((x) => x <= k).sort().pop()]; };
  const r7 = E.replay({ events: [{ type: "deposit", date: px.dates[b], amount: 10000 }, { type: "buy", date: px.dates[b], ticker: t, amount: 10000 },
    { type: "sell", date: px.dates[e], ticker: t, fraction: 1 }] }, px, { fees: free, tax: { rate: 0.25, dividend_total: 0 } });
  const s7 = r7.log.find((l) => l.kind === "sell");
  const nominal = 10000 * (c.px[e] / c.px[b]) - 10000, infl = Math.max(0, 10000 * (known(px.dates[e]) / known(px.dates[b]) - 1));
  const expect = nominal > 0 ? Math.max(0, nominal - infl) : nominal;
  ok(infl > 0, "inflation over the holding period is positive");
  ok(Math.abs(s7.gain - expect) < 1, `Israeli real gain ${s7.gain} vs ${expect.toFixed(2)} (nominal ${nominal.toFixed(2)})`);
  ok(Math.abs(s7.tax - Math.max(0, expect) * 0.25) < 1, "tax on the real gain only");
}
// 8. A loss carries into the next year and offsets that year's gain.
{
  const t = "ESLT.TA", c = px.co[t];
  const y1 = px.dates.findIndex((d) => d >= "2025-12-29"), y2 = px.dates.findIndex((d) => d >= "2026-03-02");
  const sells = [], evs8 = [{ type: "deposit", date: px.dates[0], amount: 40000 }];
  // pick a stock that lost in 2025 (bought early, sold late Dec), and one that gained in early 2026
  const loser = Object.keys(px.co).find((k) => { const p = px.co[k]; return p.cur === "USD" && p.px[y1] && p.px[5] && p.px[y1] / p.px[5] < 0.8; });
  const winner = Object.keys(px.co).find((k) => { const p = px.co[k]; return p.cur === "USD" && p.px[y1 + 2] && p.px[y2] && p.px[y2] / p.px[y1 + 2] > 1.15; });
  evs8.push({ type: "buy", date: px.dates[5], ticker: loser, amount: 10000 }, { type: "sell", date: px.dates[y1], ticker: loser, fraction: 1 },
    { type: "buy", date: px.dates[y1 + 2], ticker: winner, amount: 10000 }, { type: "sell", date: px.dates[y2], ticker: winner, fraction: 1 });
  const r8 = E.replay({ events: evs8 }, px, { fees: free, tax: { rate: 0.25, dividend_total: 0 } });
  const [l1, l2] = r8.log.filter((l) => l.kind === "sell");
  ok(l1.gain < 0 && l2.gain > 0, `a loss in ${l1.date} (${loser}) then a gain in ${l2.date} (${winner})`);
  ok(Math.abs(l2.tax - Math.max(0, l2.gain + l1.gain) * 0.25) < 1, `next year's tax ${l2.tax} offset by last year's loss`);
}
// 6. Two portfolios do not affect each other (pure function).
const a = E.replay({ events: evs }, px, { fees }), b = E.replay({ events: evs }, px, { fees });
ok(JSON.stringify(a.summary) === JSON.stringify(b.summary), "deterministic");
console.log(`${pass} checks passed`);
console.log(JSON.stringify(r.summary), rp.date, ts.date);
