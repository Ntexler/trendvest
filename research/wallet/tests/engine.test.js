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
// 6. Two portfolios do not affect each other (pure function).
const a = E.replay({ events: evs }, px, { fees }), b = E.replay({ events: evs }, px, { fees });
ok(JSON.stringify(a.summary) === JSON.stringify(b.summary), "deterministic");
console.log(`${pass} checks passed`);
console.log(JSON.stringify(r.summary), rp.date, ts.date);
