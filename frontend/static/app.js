/* astrolog dashboard — fetch, render wheel, manage natal charts */

const GLYPHS = {
  Sun: "☉", Moon: "☽", Mercury: "☿", Venus: "♀", Mars: "♂",
  Jupiter: "♃", Saturn: "♄", Uranus: "♅", Neptune: "♆", Pluto: "♇",
  "North Node": "☊", Chiron: "⚷",
};
const SIGN_GLYPHS = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"];
const ELEMENT_COLOR = [
  "var(--red)", "var(--green)", "var(--yellow)", "var(--teal)", // fire earth air water
];
const NS = "http://www.w3.org/2000/svg";

let selectedChart = null;   // name of active natal chart
let natalData = null;       // cached natal chart object

/* ---------- geometry helpers ---------- */
function polar(cx, cy, r, deg) {
  const rad = (deg * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)];
}
// Ascendant sits at 9 o'clock; zodiac runs counterclockwise.
function screenAngle(lon, asc) {
  return 180 + (lon - asc);
}

function el(tag, attrs, text) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}

/* ---------- wheel ---------- */
function drawWheel(sky, natal) {
  const svg = document.getElementById("wheel");
  svg.innerHTML = "";
  const C = 320, R_OUT = 300, R_SIGN = 262, R_TRANSIT = 226, R_NATAL = 150, R_HUB = 96;
  const asc = sky.houses.ascendant.longitude;

  svg.appendChild(el("circle", { cx: C, cy: C, r: R_OUT, fill: "var(--mantle)", stroke: "var(--surface1)" }));
  svg.appendChild(el("circle", { cx: C, cy: C, r: R_SIGN, fill: "none", stroke: "var(--surface0)" }));
  svg.appendChild(el("circle", { cx: C, cy: C, r: R_HUB, fill: "var(--crust)", stroke: "var(--surface0)" }));

  // sign boundaries + glyphs
  for (let i = 0; i < 12; i++) {
    const a = screenAngle(i * 30, asc);
    const [x1, y1] = polar(C, C, R_SIGN, a);
    const [x2, y2] = polar(C, C, R_OUT, a);
    svg.appendChild(el("line", { x1, y1, x2, y2, stroke: "var(--surface1)" }));
    const [gx, gy] = polar(C, C, (R_SIGN + R_OUT) / 2, screenAngle(i * 30 + 15, asc));
    svg.appendChild(el("text", {
      x: gx, y: gy, "text-anchor": "middle", "dominant-baseline": "central",
      "font-size": "22", fill: ELEMENT_COLOR[i % 4],
    }, SIGN_GLYPHS[i]));
  }

  // house cusps
  for (const cusp of sky.houses.cusps) {
    const a = screenAngle(cusp.longitude, asc);
    const [x1, y1] = polar(C, C, R_HUB, a);
    const [x2, y2] = polar(C, C, R_SIGN, a);
    const angle = cusp.house === 1 || cusp.house === 10;
    svg.appendChild(el("line", {
      x1, y1, x2, y2,
      stroke: angle ? "var(--lavender)" : "var(--surface0)",
      "stroke-width": angle ? 2 : 1,
      "stroke-dasharray": angle ? "" : "3 4",
    }));
    const [hx, hy] = polar(C, C, R_HUB - 14, screenAngle(cusp.longitude + 12, asc));
    svg.appendChild(el("text", {
      x: hx, y: hy, "text-anchor": "middle", "dominant-baseline": "central",
      "font-size": "10", fill: "var(--overlay0)", "font-family": "var(--font-mono)",
    }, cusp.house));
  }

  // aspect lines in the hub (transiting sky)
  const aspectColor = {
    Conjunction: "var(--lavender)", Sextile: "var(--teal)", Square: "var(--red)",
    Trine: "var(--green)", Opposition: "var(--peach)",
  };
  for (const asp of sky.aspects) {
    const pa = sky.positions[asp.a], pb = sky.positions[asp.b];
    if (!pa || !pb || asp.aspect === "Conjunction") continue;
    const [x1, y1] = polar(C, C, R_HUB, screenAngle(pa.longitude, asc));
    const [x2, y2] = polar(C, C, R_HUB, screenAngle(pb.longitude, asc));
    svg.appendChild(el("line", { x1, y1, x2, y2, stroke: aspectColor[asp.aspect], "stroke-width": 1, opacity: 0.55 }));
  }

  // planet rings
  const drawBodies = (positions, radius, color, cls) => {
    for (const [name, pos] of Object.entries(positions)) {
      const a = screenAngle(pos.longitude, asc);
      const [x, y] = polar(C, C, radius, a);
      const [tx, ty] = polar(C, C, radius - 18, a);
      svg.appendChild(el("line", {
        x1: tx, y1: ty, x2: polar(C, C, radius - 8, a)[0], y2: polar(C, C, radius - 8, a)[1],
        stroke: "var(--overlay0)", "stroke-width": 0.6,
      }));
      const g = el("text", {
        x, y, class: cls, "text-anchor": "middle", "dominant-baseline": "central",
        "font-size": cls === "planet" ? "19" : "15",
        fill: pos.retrograde ? "var(--red)" : color,
      }, GLYPHS[name] || "?");
      g.appendChild(el("title", {}, `${name}${pos.retrograde ? " Rx" : ""} — ${pos.sign} ${pos.pretty}`));
      svg.appendChild(g);
    }
  };
  if (natal) drawBodies(natal.positions, R_NATAL, "var(--blue)", "natal");
  drawBodies(sky.positions, R_TRANSIT, "var(--text)", "planet");

  // legend when natal ring shown
  if (natal) {
    svg.appendChild(el("text", {
      x: C, y: C, "text-anchor": "middle", "dominant-baseline": "central",
      "font-size": "11", fill: "var(--blue)", "font-family": "var(--font-mono)",
    }, `inner: ${selectedChart}`));
  }
}

/* ---------- tables ---------- */
function renderPlanets(positions) {
  const tbody = document.querySelector("#planet-table tbody");
  tbody.innerHTML = "";
  for (const [name, pos] of Object.entries(positions)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="glyph">${GLYPHS[name] || ""}</td>
      <td>${name}${pos.retrograde ? '<span class="rx">Rx</span>' : ""}</td>
      <td>${pos.sign}</td>
      <td class="mono">${pos.pretty}</td>`;
    tbody.appendChild(tr);
  }
}

function renderAspects(list, mountId, emptyText) {
  const tbody = document.querySelector(`#${mountId} tbody`);
  tbody.innerHTML = "";
  if (!list || list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty">${emptyText}</td></tr>`;
    return;
  }
  for (const a of list.slice(0, 14)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${a.a}</td>
      <td class="aspect-${a.aspect}">${a.aspect}</td>
      <td>${a.b}</td>
      <td class="mono">${a.orb.toFixed(2)}°</td>`;
    tbody.appendChild(tr);
  }
}

function renderMoon(moon) {
  document.getElementById("moon-pill").textContent =
    `☽ ${moon.phase} · ${moon.illumination_pct}%`;
}

function renderAngles(houses) {
  document.getElementById("angles").textContent =
    `ASC ${houses.ascendant.sign} ${houses.ascendant.pretty} · MC ${houses.midheaven.sign} ${houses.midheaven.pretty}`;
}

/* ---------- data flow ---------- */
async function refresh() {
  try {
    const url = selectedChart
      ? `/api/transits/${encodeURIComponent(selectedChart)}`
      : "/api/now";
    const sky = await (await fetch(url)).json();
    drawWheel(sky, natalData ? natalData.chart : null);
    renderPlanets(sky.positions);
    renderMoon(sky.moon);
    renderAngles(sky.houses);
    renderAspects(sky.aspects, "aspect-table", "No aspects in orb");
    renderAspects(sky.transit_aspects, "transit-table",
      selectedChart ? "No transits in orb" : "Select a natal chart to see transits");
    document.getElementById("clock").textContent =
      new Date().toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
  } catch (e) {
    document.getElementById("clock").textContent = "connection lost — retrying";
  }
}

async function loadChartList() {
  const charts = await (await fetch("/api/charts")).json();
  const sel = document.getElementById("chart-select");
  const current = sel.value;
  sel.innerHTML = '<option value="">— current sky only —</option>';
  for (const c of charts) {
    const opt = document.createElement("option");
    opt.value = c.name;
    opt.textContent = c.name;
    sel.appendChild(opt);
  }
  if ([...sel.options].some(o => o.value === current)) sel.value = current;
}

async function selectChart(name) {
  selectedChart = name || null;
  natalData = null;
  if (selectedChart) {
    natalData = await (await fetch(`/api/charts/${encodeURIComponent(selectedChart)}`)).json();
  }
  document.getElementById("delete-chart").disabled = !selectedChart;
  refresh();
}

/* ---------- events ---------- */
document.getElementById("chart-select").addEventListener("change", e => selectChart(e.target.value));

document.getElementById("delete-chart").addEventListener("click", async () => {
  if (!selectedChart) return;
  if (!confirm(`Delete natal chart "${selectedChart}"?`)) return;
  await fetch(`/api/charts/${encodeURIComponent(selectedChart)}`, { method: "DELETE" });
  await loadChartList();
  selectChart("");
});

document.getElementById("save-chart").addEventListener("click", async () => {
  const msg = document.getElementById("form-msg");
  const body = {
    name: document.getElementById("f-name").value,
    date: document.getElementById("f-date").value,
    time: document.getElementById("f-time").value,
    tz: document.getElementById("f-tz").value,
    lat: document.getElementById("f-lat").value,
    lon: document.getElementById("f-lon").value,
  };
  const res = await fetch("/api/charts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (res.ok) {
    msg.textContent = `Saved "${data.saved}"`;
    msg.className = "ok";
    await loadChartList();
    document.getElementById("chart-select").value = data.saved;
    selectChart(data.saved);
  } else {
    msg.textContent = data.error;
    msg.className = "err";
  }
  msg.id = "form-msg";
});

/* ---------- boot ---------- */
try { document.getElementById("f-tz").value = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch {}
loadChartList().then(() => refresh());
setInterval(refresh, 60_000);
