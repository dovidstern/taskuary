// Did anyone open the demo, and did they do anything once they were in it?
//
// The landing page can be counted by any host's log. The demo cannot: it is one HTML file and
// every click after that is JavaScript, so a page-view counter records a visit and learns
// nothing about whether the visitor got as far as opening a message. This sends a handful of
// named events to our own Pages Function (functions/api/ev.js) and nothing else - no cookie, no
// third-party script, an id that dies with the tab, and never a word the visitor typed.
//
// Off outside the static demo: a local `taskuary --demo` and the real app send nothing, and a
// demo served from anywhere but taskuary.com has no endpoint to send to.
const ENDPOINT = "/api/ev";
const KEY = "tq_demo_sid";

const on = () => {
  try { return import.meta.env.VITE_DEMO === "1" && /(^|\.)taskuary\.com$/.test(location.hostname); }
  catch { return false; }
};

const sid = () => {
  try {
    let s = sessionStorage.getItem(KEY);
    if (!s) { s = Math.random().toString(36).slice(2) + Date.now().toString(36); sessionStorage.setItem(KEY, s); }
    return s;
  } catch { return "nostore"; }
};

let queue = [], timer = null, started = Date.now(), live = false;

// batched, because a demo generates a click every second or two and forty requests to count
// forty clicks is a worse citizen than one request carrying forty
const flush = (beacon) => {
  if (!queue.length) return;
  const body = JSON.stringify({ sid: sid(), page: location.pathname.slice(0, 120),
    ref: (document.referrer || "").split("/").slice(0, 3).join("/").slice(0, 200),
    mobile: matchMedia("(max-width: 900px)").matches, events: queue.splice(0, 40) });
  try {
    if (beacon && navigator.sendBeacon) navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
    else fetch(ENDPOINT, { method: "POST", body, keepalive: true, headers: { "content-type": "application/json" } }).catch(() => {});
  } catch { /* counting is never worth an error in the page */ }
};

export const track = (kind, what = "", n = 0) => {
  if (!live) return;
  queue.push({ kind, what: String(what).slice(0, 80), n });
  clearTimeout(timer);
  timer = setTimeout(() => flush(false), 2500);
};

export const startTracking = () => {
  if (live || !on()) return;
  live = true; started = Date.now();
  track("open", document.title.slice(0, 60));
  // how long they stayed is the whole question - a 4-second visit and a 4-minute one are
  // different verdicts on the demo, and only the second one is worth the build
  const marks = [15, 60, 180, 600];
  marks.forEach((s) => setTimeout(() => track("dwell", `${s}s`, s), s * 1000));
  addEventListener("pagehide", () => {
    track("leave", "", Math.round((Date.now() - started) / 1000));
    flush(true);
  });
  document.addEventListener("visibilitychange", () => { if (document.hidden) flush(true); });
};
