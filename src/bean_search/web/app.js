/* Bean Search map UI. Talks to /api/goals and /api/search. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CIRCUITY = 1.25; // must match config.CIRCUITY_FACTOR

  // ---------- SVG art ----------
  const CAN_SVG = `
    <svg width="26" height="32" viewBox="0 0 28 34">
      <rect x="2" y="4" width="24" height="27" rx="4" fill="#e4572e" stroke="#2a1a0f" stroke-width="2.5"/>
      <rect x="2" y="12" width="24" height="11" fill="#ffd23f" stroke="#2a1a0f" stroke-width="2"/>
      <ellipse cx="14" cy="4.5" rx="12" ry="3" fill="#ddd" stroke="#2a1a0f" stroke-width="2.5"/>
      <ellipse cx="10" cy="17.5" rx="3.2" ry="2.2" fill="#8a4b22"/>
      <ellipse cx="17.5" cy="17.5" rx="3.2" ry="2.2" fill="#8a4b22"/>
    </svg>`;
  const SCULPTURE_SVG = `
    <svg width="40" height="28" viewBox="0 0 40 28">
      <path d="M4 22 C2 10 12 3 20 8 C28 3 38 10 36 22 Z" fill="#cfd8e3" stroke="#2a1a0f" stroke-width="2.5"/>
      <path d="M9 12 C13 8 17 9 19 11" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
    </svg>`;
  const CITY_SVG = `
    <svg width="34" height="34" viewBox="0 0 34 34">
      <path d="M5 14 H29 L27 30 H7 Z" fill="#8a4b22" stroke="#2a1a0f" stroke-width="2.5"/>
      <rect x="3" y="10" width="28" height="5" rx="2" fill="#b86b38" stroke="#2a1a0f" stroke-width="2.5"/>
      <circle cx="12" cy="7" r="3" fill="#8a4b22" stroke="#2a1a0f" stroke-width="2"/>
      <circle cx="20" cy="5" r="3" fill="#8a4b22" stroke="#2a1a0f" stroke-width="2"/>
    </svg>`;
  const BUDDY_SVG = `
    <svg width="40" height="40" viewBox="0 0 40 40">
      <path d="M8 22 C4 10 16 2 24 6 C34 10 38 22 30 32 C24 38 12 36 8 22 Z"
            fill="#b86b38" stroke="#2a1a0f" stroke-width="3"/>
      <path d="M13 13 C15 10 18 9 21 10" fill="none" stroke="#e7a873" stroke-width="3" stroke-linecap="round"/>
      <circle cx="18" cy="20" r="4.5" fill="#fff" stroke="#2a1a0f" stroke-width="2"/>
      <circle cx="27" cy="20" r="4.5" fill="#fff" stroke="#2a1a0f" stroke-width="2"/>
      <circle cx="19" cy="21" r="2" fill="#2a1a0f"/>
      <circle cx="28" cy="21" r="2" fill="#2a1a0f"/>
      <path d="M19 28 Q23 31 27 28" fill="none" stroke="#2a1a0f" stroke-width="2.2" stroke-linecap="round"/>
    </svg>`;

  const ART = {
    canned: { svg: CAN_SVG, size: [26, 32] },
    sculpture: { svg: SCULPTURE_SVG, size: [40, 28] },
    city: { svg: CITY_SVG, size: [34, 34] },
  };

  const beanIcon = (type) => {
    const a = ART[type] || ART.canned;
    return L.divIcon({
      className: "bean-marker",
      html: a.svg,
      iconSize: a.size,
      iconAnchor: [a.size[0] / 2, a.size[1] / 2],
    });
  };
  const buddyIcon = L.divIcon({ className: "buddy", html: BUDDY_SVG, iconSize: [40, 40], iconAnchor: [20, 30] });

  // ---------- map ----------
  const map = L.map("map", { zoomControl: false }).setView([40.05, -105.25], 11);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  // ---------- state ----------
  const markers = new Map(); // goal id -> L.Marker
  let goals = [];
  let meanEdgeM = 170;
  let start = null; // L.LatLng
  let buddy = null;
  let routeLayers = [];
  let anim = null;
  let busy = false;

  // ---------- helpers ----------
  const haversine = (a, b) => {
    const R = 6371008.8, toR = Math.PI / 180;
    const dp = (b.lat - a.lat) * toR, dl = (b.lng - a.lng) * toR;
    const h = Math.sin(dp / 2) ** 2 + Math.cos(a.lat * toR) * Math.cos(b.lat * toR) * Math.sin(dl / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(h));
  };
  const fmt = (n) => Math.round(n).toLocaleString();

  const bump = (el) => {
    el.classList.remove("bump");
    void el.offsetWidth;
    el.classList.add("bump");
  };

  const toast = (msg) => {
    const t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (t.hidden = true), 3500);
  };

  const setHud = ({ beans, moves, km, budget }) => {
    if (beans !== undefined) $("beans").textContent = beans;
    if (moves !== undefined) $("moves").textContent = moves;
    if (km !== undefined) $("km").textContent = km.toFixed(1);
    if (budget !== undefined) $("budget-echo").textContent = budget;
    const b = Number($("budget-echo").textContent) || 1;
    const used = Number($("moves").textContent) || 0;
    const left = Math.max(0, 1 - used / b);
    const fill = $("moves-fill");
    fill.style.width = `${left * 100}%`;
    fill.classList.toggle("low", left < 0.25);
  };

  // ---------- load beans ----------
  async function loadGoals() {
    const res = await fetch("/api/goals");
    const data = await res.json();
    goals = data.goals;
    meanEdgeM = data.mean_edge_m || meanEdgeM;
    const canned = goals.filter((g) => g.bean_type === "canned");
    $("total-beans").textContent = goals.length;
    for (const g of goals) {
      const m = L.marker([g.lat, g.lon], { icon: beanIcon(g.bean_type), keyboard: false })
        .bindTooltip(`${g.name || "Mystery beans"}`, { direction: "top", offset: [0, -14] })
        .on("click", (e) => {
          if (busy) return;
          clearRun();
          placeBuddy(e.latlng);
        })
        .addTo(map);
      markers.set(g.id, m);
    }
    if (canned.length) {
      map.fitBounds(L.latLngBounds(canned.map((g) => [g.lat, g.lon])).pad(0.1));
    }
  }

  function updateFarAway() {
    const far = goals.filter((g) => g.bean_type !== "canned");
    if (!start || !far.length) return ($("far").hidden = true);
    $("far-list").innerHTML = "";
    for (const g of far) {
      const d = haversine(start, L.latLng(g.lat, g.lon));
      const li = document.createElement("li");
      li.innerHTML = `<b></b><span></span>`;
      li.querySelector("b").textContent = g.bean_type === "sculpture" ? "The Bean" : "Beantown";
      li.querySelector("span").textContent = `${fmt(d / 1000)} km · ~${fmt((d * CIRCUITY) / meanEdgeM)} moves`;
      $("far-list").appendChild(li);
    }
    $("far").hidden = false;
  }

  // ---------- reset ----------
  function clearRun() {
    if (anim) cancelAnimationFrame(anim);
    anim = null;
    routeLayers.forEach((l) => map.removeLayer(l));
    routeLayers = [];
    for (const m of markers.values()) {
      const el = m.getElement();
      if (el) el.classList.remove("got", "pop", "target");
    }
    $("banner").hidden = true;
    setHud({ beans: 0, moves: 0, km: 0 });
  }

  function placeBuddy(latlng) {
    start = latlng;
    if (buddy) buddy.setLatLng(latlng);
    else buddy = L.marker(latlng, { icon: buddyIcon, zIndexOffset: 1000, keyboard: false }).addTo(map);
    $("go").disabled = false;
    $("hint").textContent = "Pick your moves, then hit GO!";
    updateFarAway();
  }

  // ---------- run ----------
  async function go() {
    if (!start || busy) return;
    busy = true;
    clearRun();
    const budget = Number($("budget").value);
    setHud({ budget });
    const btn = $("go");
    btn.disabled = true;
    btn.classList.add("loading");
    btn.textContent = "Sniffing…";
    try {
      const q = new URLSearchParams({ lat: start.lat, lon: start.lng, moves: budget });
      const res = await fetch(`/api/search?${q}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "search failed");
      buddy.setLatLng([data.start.lat, data.start.lon]);
      btn.classList.remove("loading");
      btn.textContent = "Go go go!";
      await play(data);
    } catch (err) {
      toast(`Oops! ${err.message}`);
    } finally {
      btn.classList.remove("loading");
      btn.textContent = "GO!";
      btn.disabled = false;
      busy = false;
    }
  }

  function play(data) {
    const pts = data.path.map(([lat, lon]) => L.latLng(lat, lon));
    const shadow = L.polyline([], { color: "#2a1a0f", weight: 10, opacity: 0.85, lineCap: "round", lineJoin: "round" }).addTo(map);
    const line = L.polyline([], { color: "#ffd23f", weight: 5, lineCap: "round", lineJoin: "round" }).addTo(map);
    routeLayers.push(shadow, line);
    buddy.setZIndexOffset(1000);

    for (const c of data.collected) {
      const el = markers.get(c.id)?.getElement();
      if (el) el.classList.add("target");
    }
    if (pts.length > 1) map.fitBounds(L.latLngBounds(pts).pad(0.15), { maxZoom: 16 });

    // cumulative distance along polyline
    const cum = [0];
    for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + haversine(pts[i - 1], pts[i]));
    const total = cum[cum.length - 1] || 1;
    const events = data.collected.map((c, i) => ({ ...c, at: cum[c.path_index], n: i + 1 }));
    // moves shown = interpolate between exact move counts at each bean
    const movesAt = (d) => {
      let i = 0;
      while (i < events.length && events[i].at <= d) i++;
      const prev = i ? events[i - 1] : { at: 0, moves: 0 };
      if (i >= events.length) return prev.moves;
      const nxt = events[i];
      const f = (d - prev.at) / Math.max(1, nxt.at - prev.at);
      return Math.floor(prev.moves + f * (nxt.moves - prev.moves));
    };

    const collect = (ev) => {
      const el = markers.get(ev.id)?.getElement();
      if (el) {
        el.classList.remove("target");
        el.classList.add("got", "pop");
        const plus = document.createElement("span");
        plus.className = "plus-one";
        plus.textContent = "+1";
        el.appendChild(plus);
        setTimeout(() => plus.remove(), 900);
      }
      setHud({ beans: ev.n });
      bump($("beans"));
    };

    const finish = () => {
      line.setLatLngs(pts);
      shadow.setLatLngs(pts);
      if (pts.length) buddy.setLatLng(pts[pts.length - 1]);
      setHud({ beans: data.collected.length, moves: data.moves, km: data.meters / 1000 });
      showBanner(data);
    };

    if (REDUCED_MOTION || pts.length < 2) {
      events.forEach(collect);
      finish();
      return Promise.resolve();
    }

    const duration = Math.min(14000, Math.max(3000, events.length * 650));
    return new Promise((resolve) => {
      let t0 = null, seg = 0, next = 0;
      const frame = (ts) => {
        if (t0 === null) t0 = ts;
        const p = Math.min(1, (ts - t0) / duration);
        const d = p * total;
        while (seg < pts.length - 2 && cum[seg + 1] < d) seg++;
        const segLen = cum[seg + 1] - cum[seg] || 1;
        const f = Math.min(1, (d - cum[seg]) / segLen);
        const pos = L.latLng(
          pts[seg].lat + (pts[seg + 1].lat - pts[seg].lat) * f,
          pts[seg].lng + (pts[seg + 1].lng - pts[seg].lng) * f,
        );
        const drawn = pts.slice(0, seg + 1).concat([pos]);
        line.setLatLngs(drawn);
        shadow.setLatLngs(drawn);
        buddy.setLatLng(pos);

        while (next < events.length && events[next].at <= d) collect(events[next++]);
        setHud({ moves: movesAt(d), km: d / 1000 });

        if (p < 1) anim = requestAnimationFrame(frame);
        else {
          anim = null;
          finish();
          resolve();
        }
      };
      anim = requestAnimationFrame(frame);
    });
  }

  function showBanner(data) {
    const n = data.collected.length;
    $("banner-title").textContent = n === 0 ? "No beans…" : n >= 25 ? "BEAN LEGEND!" : n >= 10 ? "Bean-tastic!" : "Level complete!";
    $("banner-text").textContent = n === 0
      ? `Nothing within ${data.budget} moves. Try more moves or a new spot!`
      : `You grabbed ${n} bean stop${n === 1 ? "" : "s"} in ${data.moves} of ${data.budget} moves (${(data.meters / 1000).toFixed(1)} km).`;
    const ol = $("banner-list");
    ol.innerHTML = "";
    for (const c of data.collected) {
      const li = document.createElement("li");
      li.textContent = c.name || "Mystery beans";
      ol.appendChild(li);
    }
    $("banner").hidden = false;
    $("again").focus();
  }

  // ---------- wiring ----------
  map.on("click", (e) => {
    if (busy) return;
    clearRun();
    placeBuddy(e.latlng);
  });
  $("budget").addEventListener("input", (e) => {
    $("budget-out").textContent = e.target.value;
    if (!busy) setHud({ budget: Number(e.target.value) });
  });
  $("go").addEventListener("click", go);
  $("reset").addEventListener("click", () => {
    if (busy) return;
    clearRun();
    if (buddy) map.removeLayer(buddy);
    buddy = null;
    start = null;
    $("go").disabled = true;
    $("far").hidden = true;
    $("hint").textContent = "Click the map to drop your bean buddy!";
  });
  $("again").addEventListener("click", () => ($("banner").hidden = true));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") $("banner").hidden = true;
  });

  setHud({ beans: 0, moves: 0, km: 0, budget: Number($("budget").value) });
  loadGoals().catch(() => toast("Couldn't load beans. Is the server running?"));
})();
