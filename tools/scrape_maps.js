#!/usr/bin/env node
/**
 * scrape_maps.js — pull a Google Maps place page into raw JSON.
 *
 * Places API (New) is not enabled on this Google account, and the API never
 * exposes popular times or the 5..1 star breakdown anyway. This reads the place
 * page directly, the way the original seven were built.
 *
 *   node tools/scrape_maps.js --place-id ChIJ... --out raw/pals-lounge.json
 *   node tools/scrape_maps.js --cid 15489332774993295258 --out raw/x.json
 *
 * Emits the Places-API-ish fields tools/from_scrape.py feeds to fetch.py's
 * skeleton(), plus breakdown / popular_times / attributes the API lacks.
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require('/Users/davidrack/Projects/dckt-tools/node_modules/playwright');

const arg = (n, d) => { const i = process.argv.indexOf('--' + n); return i > -1 ? process.argv[i + 1] : d; };
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// strip Google's private-use icon glyphs and collapse whitespace
const clean = (s) => (s || '').replace(/[-]/g, '').replace(/\s+/g, ' ').trim();

async function scrollPane(p, times, px) {
  for (let i = 0; i < times; i++) {
    await p.evaluate((d) => {
      const e = document.querySelector('div[role="main"]');
      if (e) e.scrollTop += d;
    }, px);
    await sleep(600);
  }
}

async function scrollAll(p, times, px) {
  for (let i = 0; i < times; i++) {
    await p.evaluate((d) => {
      document.querySelectorAll('div[role="main"], .m6QErb, div').forEach(e => {
        if (e.scrollHeight > e.clientHeight + 150 && e.clientHeight > 250) e.scrollTop += d;
      });
    }, px);
    await sleep(650);
  }
}

async function scrape(url) {
  const b = await chromium.launch({ headless: true });
  const ctx = await b.newContext({
    locale: 'en-US', timezoneId: 'America/Chicago', userAgent: UA,
    viewport: { width: 1400, height: 1100 },
  });
  const p = await ctx.newPage();
  await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForSelector('h1', { timeout: 30000 }).catch(() => {});
  await sleep(4500);

  const placeUrl = p.url();

  // hours live behind a disclosure on some pages
  const hrs = await p.$('button[data-item-id="oh"], button[jsaction*="openhours"], [jsaction*="openhours.toggle"]');
  if (hrs) { await hrs.click().catch(() => {}); await sleep(1200); }

  const core = await p.evaluate(() => {
    const cl = (s) => (s || '').replace(/[-]/g, '').replace(/\s+/g, ' ').trim();
    const txt = (s) => { const e = document.querySelector(s); return e ? cl(e.textContent) : null; };
    const al = (s) => { const e = document.querySelector(s); return e ? cl(e.getAttribute('aria-label')) : null; };
    const strip = (s, pre) => s ? cl(s.replace(new RegExp('^' + pre + ':?\\s*', 'i'), '')) : null;
    const out = {};

    out.name = txt('h1');
    out.rating = parseFloat(txt('div.F7nice span[aria-hidden="true"]')
      || (cl((document.querySelector('[aria-label*="stars"]') || {}).getAttribute
           ? document.querySelector('[aria-label*="stars"]').getAttribute('aria-label') : '').match(/([\d.]+) stars?/) || [0, '0'])[1]) || 0;
    let rc = 0;
    document.querySelectorAll('[aria-label]').forEach(e => {
      if (rc) return;
      const m = cl(e.getAttribute('aria-label')).match(/^([\d,]+) reviews?$/i);
      if (m) rc = parseInt(m[1].replace(/,/g, ''), 10);
    });
    if (!rc) document.querySelectorAll('button, span').forEach(e => {
      if (rc) return;
      const m = cl(e.textContent).match(/^\(?([\d,]{2,})\)? reviews?$/i);
      if (m) rc = parseInt(m[1].replace(/,/g, ''), 10);
    });
    out.userRatingCount = rc;
    out.category = txt('button[jsaction*="category"]');
    out.formattedAddress = strip(al('button[data-item-id="address"]'), 'Address');
    out.nationalPhoneNumber = strip(al('button[data-item-id^="phone"]'), 'Phone');
    const web = document.querySelector('a[data-item-id="authority"]');
    out.websiteUri = web ? web.getAttribute('href') : null;
    out.plusCode = strip(al('button[data-item-id^="oloc"]'), 'Plus code');

    const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    out.hoursRaw = {};
    document.querySelectorAll('table tr').forEach(tr => {
      const t = cl(tr.innerText);
      const d = DAYS.find(x => t.startsWith(x));
      if (d && !out.hoursRaw[d]) out.hoursRaw[d] = cl(t.slice(d.length));
    });

    out.breakdown = [];
    document.querySelectorAll('[aria-label*="stars,"]').forEach(e => {
      const m = cl(e.getAttribute('aria-label')).match(/^(\d) stars?, ([\d,]+) reviews?/);
      if (m) out.breakdown.push([+m[1], parseInt(m[2].replace(/,/g, ''), 10)]);
    });

    // popular times bars, e.g. "67% busy at 11 AM."
    out.popular = [];
    document.querySelectorAll('[aria-label*="busy at"]').forEach(e => {
      const a = cl(e.getAttribute('aria-label'));
      const m = a.match(/(\d+)%\s+busy at\s+(\d+)\s*(AM|PM)/i);
      if (m) out.popular.push({ pct: +m[1], hour: +m[2], ap: m[3].toUpperCase() });
      else if (/Currently|Usually/i.test(a)) out.popular.push({ note: a });
    });
    return out;
  });

  // ---- breakdown + popular times load only once the panel is scrolled
  await scrollPane(p, 10, 900);
  const late = await p.evaluate(() => {
    const cl = (s) => (s || '').replace(/[\ue000-\uf8ff]/g, '').replace(/\s+/g, ' ').trim();
    const bd = [], pop = [];
    document.querySelectorAll('[aria-label*="stars,"]').forEach(e => {
      const m = cl(e.getAttribute('aria-label')).match(/^(\d) stars?, ([\d,]+) reviews?/);
      if (m) bd.push([+m[1], parseInt(m[2].replace(/,/g, ''), 10)]);
    });
    document.querySelectorAll('[aria-label*="busy at"]').forEach(e => {
      const a = cl(e.getAttribute('aria-label'));
      const m = a.match(/(\d+)%\s+busy at\s+(\d+)\s*(AM|PM)/i);
      if (m) pop.push({ pct: +m[1], hour: +m[2], ap: m[3].toUpperCase() });
    });
    const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
    const hrs = {};
    document.querySelectorAll('table tr').forEach(tr => {
      const t = cl(tr.innerText);
      const d = DAYS.find(x => t.startsWith(x));
      if (d && !hrs[d]) hrs[d] = cl(t.slice(d.length));
    });
    return { bd, pop, hrs };
  });
  if (late.bd.length) core.breakdown = late.bd;
  if (late.pop.length) core.popular = late.pop;
  if (Object.keys(late.hrs).length > Object.keys(core.hoursRaw || {}).length) core.hoursRaw = late.hrs;

  // ---- reviews: open the full list
  core.reviews = [];
  try {
    let rb = await p.$('button[jsaction*="reviewChart.moreReviews"]');
    if (!rb) {
      for (const el of await p.$$('button')) {
        const t = clean(await el.innerText().catch(() => ''));
        if (/^[\d,]+ reviews?$/i.test(t)) { rb = el; break; }
      }
    }
    if (rb) {
      await rb.click();
      await sleep(3500);
      await scrollAll(p, 16, 1300);
      // expand truncated review bodies
      for (const m of (await p.$$('button[aria-label="See more"], button[jsaction*="review.expandReview"]')).slice(0, 40)) {
        await m.click().catch(() => {});
      }
      await sleep(1200);
      core.reviews = await p.evaluate(() => {
        const cl = (s) => (s || '').replace(/[-]/g, '').replace(/\s+/g, ' ').trim();
        const seen = new Set(); const out = [];
        document.querySelectorAll('div[data-review-id]').forEach(el => {
          const body = el.querySelector('.MyEned, [class*="wiI7pd"]');
          const who = el.querySelector('[class*="d4r55"]');
          const star = el.querySelector('[role="img"][aria-label*="star"]');
          const t = body ? cl(body.innerText) : '';
          if (!t || t.length < 15 || seen.has(t)) return;
          seen.add(t);
          const sm = star ? cl(star.getAttribute('aria-label')).match(/(\d)/) : null;
          out.push({ text: t, author: who ? cl(who.innerText) : '', rating: sm ? +sm[1] : 5 });
        });
        return out;
      });
    }
  } catch (e) { core.reviewsError = e.message; }

  // ---- About tab: service options, payments, accessibility, atmosphere
  core.attributes = [];
  try {
    await p.goto(placeUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await sleep(4000);
    const about = await p.$('button[role="tab"][aria-label^="About"]');
    if (about) {
      await about.click();
      await sleep(3000);
      await scrollPane(p, 6, 900);
      core.attributes = await p.evaluate(() => {
        const cl = (s) => (s || '').replace(/[-]/g, '').replace(/\s+/g, ' ').trim();
        const groups = [];
        document.querySelectorAll('div[role="region"] h2, .iP2t7d h2, h2.iL3Qke').forEach(h => {
          const head = cl(h.innerText);
          if (!head || /^(Map|Layers)/i.test(head)) return;
          const items = [];
          const box = h.closest('div');
          if (box) box.querySelectorAll('li').forEach(li => {
            const t = cl(li.innerText);
            if (t && t.length < 70) items.push(t);
          });
          if (items.length) groups.push({ head, items: [...new Set(items)] });
        });
        return groups;
      });
    }
  } catch (e) { core.attributesError = e.message; }

  // ---- photos: "See photos" opens the grid
  core.photos = [];
  try {
    await p.goto(placeUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await sleep(4000);
    let sp = null;
    for (const el of await p.$$('button')) {
      const t = clean(await el.innerText().catch(() => ''));
      if (/^See photos$/i.test(t)) { sp = el; break; }
    }
    if (!sp) sp = await p.$('button[jsaction*="heroHeaderImage"]');
    if (sp) {
      await sp.click();
      await sleep(5000);
      await scrollAll(p, 18, 1400);
      const raw = await p.evaluate(() => {
        const s = new Set();
        const ok = (u) => u && /googleusercontent|ggpht/.test(u) && !/-rp-mo|br100|\/a\/|\/a-\//.test(u);
        document.querySelectorAll('img').forEach(i => { if (ok(i.src)) s.add(i.src); });
        document.querySelectorAll('[style*="background-image"]').forEach(d => {
          const m = (d.style.backgroundImage || '').match(/url\("?(.*?)"?\)/);
          if (m && ok(m[1])) s.add(m[1]);
        });
        return [...s];
      });
      // one entry per photo id, asked for at a usable size
      const byId = new Map();
      for (const u of raw) {
        const id = u.split('=')[0];
        if (!byId.has(id)) byId.set(id, id + '=w1600-h1200-k-no');
      }
      core.photos = [...byId.values()];
    }
  } catch (e) { core.photosError = e.message; }

  core.url = placeUrl;
  const cidm = placeUrl.match(/!1s(0x[0-9a-f]+):(0x[0-9a-f]+)/i);
  if (cidm) { core.ftid = cidm[1] + ':' + cidm[2]; core.cidHex = cidm[2]; }
  const ll = placeUrl.match(/@(-?[\d.]+),(-?[\d.]+)/);
  if (ll) { core.lat = parseFloat(ll[1]); core.lng = parseFloat(ll[2]); }

  await b.close();
  return core;
}

(async () => {
  const placeId = arg('place-id'), cid = arg('cid'), out = arg('out');
  if (!out || (!placeId && !cid)) {
    console.error('usage: scrape_maps.js (--place-id ChIJ... | --cid 123) --out file.json');
    process.exit(2);
  }
  const url = placeId
    ? `https://www.google.com/maps/place/?q=place_id:${placeId}&hl=en`
    : `https://maps.google.com/?cid=${cid}&hl=en`;
  const d = await scrape(url);
  d.place_id = placeId || null;
  d.cid_dec = cid || (d.cidHex ? BigInt(d.cidHex).toString() : null);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify(d, null, 1));
  console.error(`  ${d.name} · ${d.rating}★ ${d.userRatingCount} · ${d.photos.length} photos · ${d.reviews.length} reviews · breakdown ${d.breakdown.length} · popular ${d.popular.length} · attrs ${d.attributes.length}`);
})().catch(e => { console.error('ERR', e.message); process.exit(1); });
