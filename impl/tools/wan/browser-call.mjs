// A browser call on the WAN (client stage 5): one headless Chromium as one person, driven like dsip-rs web/test does,
// against a deployed relay (a real certificate, TURN from /turn, hints on the nodes). Run one as Bob on a NAT'd host
// and one as Alice on another, through two relays: Alice finds Bob's relay from his hint.
//
//   ROLE=bob   URL=https://<relay-b>/ NAME=Bob              node browser-call.mjs   → prints {"did": …} then waits, answers, reports
//   ROLE=alice URL=https://<relay-a>/ NAME=Alice PEER=<did> node browser-call.mjs   → calls, measures, hangs up, reports
//
// Needs the `playwright` package beside it (npm install playwright; npx playwright install --with-deps chromium) and,
// as root, --no-sandbox; BROWSER=firefox uses Firefox instead. Output: one JSON record on the last line (the WAN
// record's shape), the page's log before it.
import { chromium, firefox } from 'playwright';

const role = process.env.ROLE || 'alice', url = process.env.URL, name = process.env.NAME || role, peer = process.env.PEER;
const hold = Number(process.env.HOLD_S || 20);
const t = () => Date.now();
const which = process.env.BROWSER || 'chromium';   // chromium, or firefox (fake media through prefs, as web/test/lib.mjs)
const browser = which === 'firefox'
  ? await firefox.launch({ headless: true, firefoxUserPrefs: { 'media.navigator.streams.fake': true, 'media.navigator.permission.disabled': true, 'media.peerconnection.ice.obfuscate_host_addresses': false } })
  : await chromium.launch({ headless: true, args: ['--no-sandbox', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--disable-features=WebRtcHideLocalIpsWithMdns'] });
const ctx = await browser.newContext({ permissions: which === 'chromium' ? ['camera', 'microphone'] : [] });
const page = await ctx.newPage();
const out = { role, browser: which, url, started: new Date().toISOString() };
const until = (fn, arg = null, timeout = 60000) => page.waitForFunction(fn, arg, { timeout });
try {
  const t0 = t();
  await page.goto(url);
  await page.waitForSelector('#view-welcome:not(.hidden)');
  await page.fill('#welcome-name', name);
  await page.click('#welcome-continue');
  await page.waitForSelector('#view-contacts:not(.hidden)');
  await until(() => window.dsip && window.dsip.relay());
  out.bound_ms = t() - t0;
  out.did = await page.evaluate(() => window.dsip.identity());
  out.relay = await page.evaluate(() => window.dsip.relay());
  await until(() => /hint published → .*(accepted|wins)/.test(document.getElementById('log').textContent), null, 30000).catch(() => {});
  out.hint = (await page.textContent('#log')).split('\n').filter((l) => /hint published/.test(l)).map((l) => l.replace(/^\S+\s+/, '')).at(-1) || null;
  out.ice = await page.evaluate(() => window.dsip.iceServers());
  console.log(JSON.stringify({ did: out.did, relay: out.relay }));
  if (role === 'bob') {
    await page.waitForSelector('#view-incoming:not(.hidden)', { timeout: Number(process.env.WAIT_S || 600) * 1000 });
    const tRing = t();
    out.caller = await page.textContent('#in-did');
    out.basis = await page.textContent('#in-basis');
    await page.click('#btn-accept');
    await until(() => window.dsip.state() === 'ACTIVE');
    out.answer_to_active_ms = t() - tRing;
    const tA = t();
    await until(() => /webrtc: connected/.test(document.getElementById('log').textContent), null, 60000);
    out.ice_ms = t() - tA;
    out.path = await page.evaluate(() => window.dsip.mediaPath());
    // sampled while the call is up: the peer connection is gone once it ends
    out.inbound_packets = 0;
    for (let i = 0; i < (hold + 60) / 2; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      if ((await page.evaluate(() => window.dsip.state())) !== 'ACTIVE') break;
      out.inbound_packets = Math.max(out.inbound_packets, await page.evaluate(() => window.dsip.inboundPackets()));
      out.path_at_end = await page.evaluate(() => window.dsip.mediaPath());
    }
    await until(() => window.dsip.state() === null, null, 60000);
  } else {
    await page.fill('#contact-name', 'Bob');
    await page.fill('#contact-did', peer);
    await page.click('#contact-add button[type=submit]');
    await page.waitForSelector('#contact-list li .name:text("Bob")');
    const tCall = t();
    await page.click('#contact-list li button:text("Call")');
    await until(() => /hint for .*HINT-SOURCED|hints for .*: 0 record/.test(document.getElementById('log').textContent), null, 30000);
    out.lookup_ms = t() - tCall;
    out.route = await page.evaluate(() => window.dsip.route());
    out.call_relay = await page.evaluate(() => window.dsip.callRelay());
    // ringing, or already answered: a callee that answers at once takes the call past PROCEEDING between two polls
    await until(() => ['PROCEEDING', 'ACTIVE'].includes(window.dsip.state()), null, 60000);
    out.ringing_ms = t() - tCall;
    await until(() => window.dsip.state() === 'ACTIVE', null, Number(process.env.WAIT_S || 600) * 1000);
    out.active_ms = t() - tCall;
    const tA = t();
    await until(() => /webrtc: connected/.test(document.getElementById('log').textContent), null, 60000);
    out.ice_ms = t() - tA;
    out.path = await page.evaluate(() => window.dsip.mediaPath());
    await new Promise((r) => setTimeout(r, hold * 1000));
    out.inbound_packets = await page.evaluate(() => window.dsip.inboundPackets());
    out.path_at_end = await page.evaluate(() => window.dsip.mediaPath());
    await page.click('#btn-hangup');
    await until(() => window.dsip.state() === null);
  }
  out.ok = true;
} catch (e) {
  out.ok = false; out.error = String(e.message || e).split('\n')[0];
} finally {
  const log = await page.textContent('#log').catch(() => '');
  console.log(log.trim().split('\n').map((l) => '  ' + l).join('\n'));
  await browser.close();
}
console.log(JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
