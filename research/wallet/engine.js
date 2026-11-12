/* TrendVest virtual wallet engine.

   A portfolio is an append-only list of events the owner wrote (deposit, buy, sell, rule, rule_off, withdraw).
   The engine replays it over real daily closes, so the result is the same on every device and every day:
   the server stores only what the owner decided, never a computed balance that could drift.

   Timing: an owner's buy or sell executes at the close of its date (or the next trading day).
   A rule is checked at each close and executes at the NEXT close, so it never uses a price it could not have known.

   Money buckets, as the owner thinks of them:
     cash       deposited and not invested
     principal  money that came back from sales, up to what was invested in that stock ("the 5,000 came back")
     profits    everything a sale returned beyond that, after tax and fees, plus dividends after tax
   Tax is computed separately, on average cost, as an Israeli broker would (see tax()).

   Works in the browser (window.TVEngine) and in node (module.exports). No dependencies. */
(function (root) {
  "use strict";

  const DEFAULT_TAX = { rate: 0.25, foreign_rule: "real_fx", dividend_total: 0.25 };

  // Fee profile shape (rates per side; see fees_il.json for researched presets):
  // {id, name, commission: {US: {per_share, min, max_pct, cur}, TA: {pct, min, cur}, other: {pct, min, cur}},
  //  fx_pct, custody: {pct_year, min_quarter_ils} | null}
  const MARKET_COSTS = {   // exchange taxes on top of the broker, fraction of the trade (fees_il.json market_costs)
    US: { buy: 0, sell: 0.0000206 }, L: { buy: 0.005, sell: 0 }, PA: { buy: 0.004, sell: 0 }, MI: { buy: 0.002, sell: 0 },
    HK: { buy: 0.001, sell: 0.001 }, TW: { buy: 0, sell: 0.003 }, TWO: { buy: 0, sell: 0.003 },
    KS: { buy: 0, sell: 0.002 }, KQ: { buy: 0, sell: 0.002 }, SS: { buy: 0, sell: 0.0005 }, SZ: { buy: 0, sell: 0.0005 }
  };
  // dividend tax withheld abroad (fees_il.json dividends.withholding); Israel tops up to 25%, a higher foreign rate is not refunded
  const WITHHOLD = { US: 0.25, T: 0.15315, DE: 0.26375, AS: 0.15, SW: 0.35, L: 0, TW: 0.21, TWO: 0.21, KS: 0.22, KQ: 0.22,
    HK: 0, SS: 0.1, SZ: 0.1, CO: 0.27, PA: 0.128 };

  const round2 = (x) => Math.round(x * 100) / 100;
  const exch = (t) => (t.includes(".") ? t.split(".").pop() : "US");

  function context(px) {
    const idx = new Map(px.dates.map((d, i) => [d, i]));
    const at = (date) => {               // first trading day on or after date
      if (idx.has(date)) return idx.get(date);
      for (let i = 0; i < px.dates.length; i++) if (px.dates[i] >= date) return i;
      return -1;
    };
    const fx = (cur, i) => (cur === "ILS" ? 1 : px.fx[cur] ? px.fx[cur][i] : NaN);
    const price = (t, i) => { const c = px.co[t]; return c ? c.px[i] : null; };
    return { px, at, fx, price, n: px.dates.length };
  }

  function commission(fees, t, sharesN, valueLocal, cur, i, ctx) {
    const ex = exch(t), c = ex === "US" ? fees.commission.US : ex === "TA" ? fees.commission.TA : fees.commission.other;
    if (!c) return 0;
    let local = c.per_share != null ? c.per_share * sharesN : (c.pct || 0) * valueLocal;
    const feeCur = c.cur || cur, conv = feeCur === cur ? 1 : ctx.fx(feeCur, i) / ctx.fx(cur, i);   // fee currency -> trade currency
    if (c.min) local = Math.max(local, c.min * conv);
    if (c.max_pct) local = Math.min(local, c.max_pct * valueLocal);
    if (c.fixed) local += c.fixed * conv;
    return local;
  }

  function replay(portfolio, px, opts) {
    opts = opts || {};
    const ctx = context(px), fees = opts.fees, tax = Object.assign({}, DEFAULT_TAX, opts.tax || {});
    const serviceFee = opts.service_fee_ils || 0, useRules = opts.rules !== false;
    const ev = [...(portfolio.events || [])].map((e, k) => ({ ...e, _k: k }))
      .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a._k - b._k));
    const S = { cash: 0, principal: 0, profits: 0, deposited: 0, withdrawn: 0,
      fee: { commission: 0, fx: 0, market: 0, custody: 0, service: 0 }, taxPaid: 0, divTax: 0, pos: {}, rules: {}, log: [] };
    const year = {};                       // calendar year -> {gain, paid}: losses offset gains in the same year
    const log = (i, kind, text, extra) => S.log.push(Object.assign({ date: px.dates[i], kind, text }, extra || {}));
    const posValue = (t, i) => { const p = S.pos[t]; const pr = ctx.price(t, i); return p && pr != null ? p.shares * pr * ctx.fx(p.cur, i) : 0; };

    function settleTax(i, gain) {         // returns shekels charged (+) or refunded (-) for this sale
      const y = px.dates[i].slice(0, 4), Y = year[y] || (year[y] = { gain: 0, paid: 0 });
      Y.gain += gain;
      const due = Math.max(0, Y.gain) * tax.rate, delta = due - Y.paid;
      Y.paid = due; S.taxPaid += delta;
      return delta;
    }

    function buy(i, t, amountIls, why) {
      const c = px.co[t], pr = ctx.price(t, i);
      if (!c || pr == null) { log(i, "error", `אין מחיר ל-${t} בתאריך הזה`); return; }
      const fx = ctx.fx(c.cur, i);
      amountIls = Math.min(amountIls, S.cash);
      if (amountIls <= 0) { log(i, "error", "אין מספיק מזומן בקופה"); return; }
      const fxFee = c.cur === "ILS" ? 0 : amountIls * (fees.fx_pct || 0);
      const mk = (MARKET_COSTS[exch(t)] || {}).buy || 0;
      // solve for shares so that price + commission + market tax + fx fee = amount
      let shares = (amountIls - fxFee) / (pr * fx * (1 + mk));
      for (let k = 0; k < 3; k++) {
        const com = commission(fees, t, shares, shares * pr, c.cur, i, ctx) * fx;
        shares = Math.max(0, (amountIls - fxFee - com) / (pr * fx * (1 + mk)));
      }
      const com = commission(fees, t, shares, shares * pr, c.cur, i, ctx) * fx, mkt = shares * pr * fx * mk;
      const p = S.pos[t] || (S.pos[t] = { t, name: c.name, cur: c.cur, shares: 0, costIls: 0, costLocal: 0, invested: 0, returned: 0, peak: 0 });
      p.shares += shares; p.costIls += amountIls; p.costLocal += shares * pr + (com + mkt + fxFee) / fx; p.invested += amountIls;
      S.cash -= amountIls;
      S.fee.commission += com; S.fee.fx += fxFee; S.fee.market += mkt;
      log(i, "buy", why || `קנית ${c.name}`, { ticker: t, amount: round2(amountIls), shares: +shares.toFixed(4), price: pr, cur: c.cur,
        fees: round2(com + fxFee + mkt) });
    }

    function sell(i, t, shares, why, isRule) {
      const p = S.pos[t], pr = ctx.price(t, i);
      if (!p || p.shares <= 0 || pr == null) return null;
      shares = Math.min(shares, p.shares);
      const fx = ctx.fx(p.cur, i), grossLocal = shares * pr;
      const com = commission(fees, t, shares, grossLocal, p.cur, i, ctx);
      const mkt = grossLocal * ((MARKET_COSTS[exch(t)] || {}).sell || 0);
      const netLocal = grossLocal - com - mkt;
      const fxFee = p.cur === "ILS" ? 0 : netLocal * fx * (fees.fx_pct || 0);
      const netIls = netLocal * fx - fxFee;
      const part = shares / p.shares, costIls = p.costIls * part, costLocal = p.costLocal * part;
      // Israeli rule for foreign securities (simplified): the part of the gain that only reflects the shekel/currency
      // change is not taxed. Real gain = gain in the trade currency at today's rate; a nominal shekel loss is never a gain.
      const nominal = netIls - costIls;
      const real = p.cur === "ILS" || tax.foreign_rule !== "real_fx" ? nominal : (netLocal - costLocal) * fx - fxFee;
      const taxable = nominal > 0 ? Math.max(0, Math.min(nominal, real)) : nominal;   // fees_il.json: foreign_currency_rule
      const taxIls = settleTax(i, taxable);
      const svc = isRule ? serviceFee : 0;
      let back = netIls - taxIls - svc;
      p.shares -= shares; p.costIls -= costIls; p.costLocal -= costLocal;
      const toPrincipal = Math.max(0, Math.min(back, p.invested - p.returned));
      p.returned += toPrincipal;
      const toProfit = back - toPrincipal;
      S.principal += toPrincipal; S.profits += toProfit;
      S.fee.commission += com * fx; S.fee.market += mkt * fx; S.fee.fx += fxFee; S.fee.service += svc;
      log(i, isRule ? "rule" : "sell", why || `מכרת ${p.name}`, { ticker: t, shares: +shares.toFixed(4), price: pr, cur: p.cur,
        gross: round2(grossLocal * fx), fees: round2((com + mkt) * fx + fxFee), tax: round2(taxIls), service: round2(svc),
        toPrincipal: round2(toPrincipal), toProfit: round2(toProfit), gain: round2(taxable) });
      return back;
    }

    function dividends(i) {
      for (const p of Object.values(S.pos)) {
        if (p.shares <= 0) continue;
        for (const [d, amt] of px.co[p.t].div || []) {
          if (d !== px.dates[i]) continue;
          const rate = Math.max(tax.dividend_total, WITHHOLD[exch(p.t)] || 0);
          const gross = p.shares * amt * ctx.fx(p.cur, i), net = gross * (1 - rate);
          S.profits += net; S.divTax += gross - net;
          log(i, "dividend", `דיבידנד מ-${p.name}`, { ticker: p.t, gross: round2(gross), tax: round2(gross - net), net: round2(net) });
        }
      }
    }

    function custody(i) {               // charged at the last trading day of each quarter
      if (!fees.custody || i + 1 >= ctx.n) return;
      const m = +px.dates[i].slice(5, 7), mNext = +px.dates[i + 1].slice(5, 7);
      if (m === mNext || m % 3 !== 0) return;
      let fee = 0;
      for (const t of Object.keys(S.pos)) {
        const v = posValue(t, i), pct = exch(t) === "TA" ? fees.custody.pct_year : (fees.custody.pct_year_foreign || fees.custody.pct_year);
        fee += v * pct / 4;
      }
      if (fee <= 0) return;
      fee = Math.max(fee, fees.custody.min_ils_quarter || 0);
      S.fee.custody += fee;
      const fromCash = Math.min(S.cash, fee); S.cash -= fromCash; S.profits -= fee - fromCash;
      log(i, "custody", "דמי ניהול חשבון לרבעון", { fee: round2(fee) });
    }

    const pendingRules = [];
    function checkRules(i) {             // decide at close i, act at close i+1
      for (const r of Object.values(S.rules)) {
        if (!r.active) continue;
        const p = S.pos[r.ticker]; if (!p || p.shares <= 0) continue;
        const v = posValue(r.ticker, i), left = p.invested - p.returned;
        if (r.trackPeak) r.peak = Math.max(r.peak || 0, v);
        const P = r.params || {};
        if (r.kind === "return_principal" && left > 0 && v >= (P.multiple || 2) * p.invested) pendingRules.push(r);
        else if (r.kind === "trailing_stop" && r.trackPeak && v <= (1 - (P.pct || 25) / 100) * r.peak) pendingRules.push(r);
        else if (r.kind === "stop_loss" && v <= (1 - (P.pct || 20) / 100) * left && left > 0) pendingRules.push(r);
        else if (r.kind === "take_profit" && v >= (P.multiple || 2) * p.invested) pendingRules.push(r);
        else if (r.kind === "sweep_profit" && v - Math.max(0, left) >= (P.amount || 1000) * 1.02) pendingRules.push(r);
      }
    }
    function runRules(i) {
      const todo = pendingRules.splice(0);
      for (const r of todo) {
        const p = S.pos[r.ticker]; if (!p || p.shares <= 0 || !r.active) continue;
        const pr = ctx.price(r.ticker, i), fx = ctx.fx(p.cur, i), P = r.params || {};
        if (r.kind === "return_principal") {
          const want = p.invested - p.returned;          // aim: this much lands in the principal bucket, after costs
          let sh = want / (pr * fx);
          for (let k = 0; k < 4; k++) {                    // gross up for fees and tax
            const trial = estimate(i, r.ticker, sh); sh *= want / Math.max(1, trial);
          }
          sell(i, r.ticker, sh, `פקודה: ההשקעה ב-${p.name} הגיעה לפי ${P.multiple || 2}. הקרן חזרה אליך`, true);
          r.active = false;
          for (const o of Object.values(S.rules)) if (o.ticker === r.ticker && o.kind === "trailing_stop" && o.params && o.params.after === "principal") { o.trackPeak = true; o.peak = posValue(r.ticker, i); }
        } else if (r.kind === "trailing_stop") {
          sell(i, r.ticker, p.shares, `פקודה: ${p.name} ירדה ${P.pct || 25}% מהשיא. נמכר הכול`, true); r.active = false;
        } else if (r.kind === "stop_loss") {
          sell(i, r.ticker, p.shares, `פקודה: ${p.name} ירדה ${P.pct || 20}% ממה שהשקעת. נמכר הכול`, true); r.active = false;
        } else if (r.kind === "take_profit") {
          sell(i, r.ticker, p.shares, `פקודה: ההשקעה ב-${p.name} הגיעה לפי ${P.multiple || 2}. נמכר הכול`, true); r.active = false;
        } else if (r.kind === "sweep_profit") {
          const sh = (P.amount || 1000) / (pr * fx);
          sell(i, r.ticker, sh, `פקודה: ${round2(P.amount || 1000)} ₪ רווח מ-${p.name} עברו לקופת הרווחים`, true);
        }
      }
    }
    function estimate(i, t, shares) {    // net shekels a sale would bring, without changing state
      const save = JSON.stringify({ S: { ...S, log: [] }, year });
      const keep = { log: S.log, pos: JSON.parse(JSON.stringify(S.pos)) };
      const before = S.principal + S.profits;
      sell(i, t, shares, "", true);
      const got = S.principal + S.profits - before;
      const back = JSON.parse(save); Object.assign(S, back.S, { log: keep.log, pos: keep.pos });
      for (const k of Object.keys(year)) delete year[k]; Object.assign(year, back.year);
      return got;
    }

    const daily = [];
    let k = 0;
    const startI = ev.length ? Math.max(0, ctx.at(ev[0].date)) : ctx.n;
    for (let i = startI; i < ctx.n; i++) {
      if (useRules) runRules(i);
      dividends(i);
      while (k < ev.length && ctx.at(ev[k].date) === i) {
        const e = ev[k++];
        if (e.type === "deposit") { S.cash += +e.amount; S.deposited += +e.amount; log(i, "deposit", "הפקדה לקופה", { amount: +e.amount }); }
        else if (e.type === "withdraw") {
          const from = e.from || "profits", amt = Math.min(+e.amount, S[from]); S[from] -= amt; S.withdrawn += amt;
          log(i, "withdraw", "משיכה מהארנק", { amount: round2(amt), from });
        } else if (e.type === "buy") buy(i, e.ticker, +e.amount, e.note);
        else if (e.type === "sell") { const p = S.pos[e.ticker]; if (p) sell(i, e.ticker, e.shares != null ? +e.shares : p.shares * (e.fraction != null ? +e.fraction : 1), e.note, false); }
        else if (e.type === "rule" && useRules) {
          S.rules[e.id] = { id: e.id, ticker: e.ticker, kind: e.kind, params: e.params || {}, active: true,
            trackPeak: !(e.kind === "trailing_stop" && (e.params || {}).after === "principal"), peak: posValue(e.ticker, i) };
          log(i, "rule_set", e.label || "נקבעה פקודה", { ticker: e.ticker, ruleKind: e.kind, params: e.params });
        } else if (e.type === "rule_off" && S.rules[e.id]) { S.rules[e.id].active = false; log(i, "rule_off", "פקודה בוטלה", { id: e.id }); }
      }
      while (k < ev.length && ctx.at(ev[k].date) < 0) k++;   // events after the last price day wait for data
      custody(i);
      if (useRules) checkRules(i);
      const hold = Object.keys(S.pos).reduce((s, t) => s + posValue(t, i), 0);
      daily.push([px.dates[i], round2(hold), round2(S.cash + S.principal + S.profits)]);
    }

    const last = ctx.n - 1;
    const positions = Object.values(S.pos).filter((p) => p.shares > 1e-9 || p.returned > 0).map((p) => {
      const v = posValue(p.t, last);
      return { ticker: p.t, name: p.name, cur: p.cur, shares: +p.shares.toFixed(4), value: round2(v), invested: round2(p.invested),
        returned: round2(p.returned), cost_left: round2(p.costIls), unrealized: round2(v - p.costIls) };
    });
    const holdings = positions.reduce((s, p) => s + p.value, 0);
    // tax still owed if everything were sold today (shown, not charged)
    const openGain = positions.reduce((s, p) => s + p.unrealized, 0);
    const fees_total = Object.values(S.fee).reduce((a, b) => a + b, 0);
    const worth = holdings + S.cash + S.principal + S.profits;
    return {
      as_of: px.dates[last],
      summary: { deposited: round2(S.deposited), withdrawn: round2(S.withdrawn), cash: round2(S.cash), principal: round2(S.principal),
        profits: round2(S.profits), holdings: round2(holdings), worth: round2(worth),
        result: round2(worth + S.withdrawn - S.deposited), tax_paid: round2(S.taxPaid + S.divTax),
        capital_tax: round2(S.taxPaid), dividend_tax: round2(S.divTax),
        tax_if_sold_today: round2(Math.max(0, openGain) * tax.rate), fees: Object.fromEntries(Object.entries(S.fee).map(([a, b]) => [a, round2(b)])),
        fees_total: round2(fees_total) },
      positions, log: S.log, daily,
      rules: Object.values(S.rules).map((r) => ({ id: r.id, ticker: r.ticker, kind: r.kind, params: r.params, active: r.active }))
    };
  }

  // Plain-language description of a rule, for the page and the log.
  function describe(r, name) {
    const P = r.params || {};
    return {
      return_principal: `כשההשקעה ב-${name} תהיה שווה פי ${P.multiple || 2}: להחזיר לי את מה שהשקעתי. השאר נשאר במניה.`,
      trailing_stop: `אם ${name} תרד ${P.pct || 25}% מהשיא שלה${P.after === "principal" ? " (אחרי שהקרן חזרה)" : ""}: למכור הכול.`,
      stop_loss: `אם ${name} תרד ${P.pct || 20}% ממה שהשקעתי: למכור הכול.`,
      take_profit: `כשההשקעה ב-${name} תהיה שווה פי ${P.multiple || 2}: למכור הכול.`,
      sweep_profit: `בכל פעם שיש ${P.amount || 1000} ₪ רווח ב-${name}: להעביר אותם לקופת הרווחים.`
    }[r.kind] || "פקודה";
  }

  const api = { replay, describe, MARKET_COSTS, WITHHOLD, DEFAULT_TAX };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.TVEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
