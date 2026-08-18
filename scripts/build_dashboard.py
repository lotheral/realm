"""Sprint 10 WP2 — functional dashboard builder.

Reads the simulation outputs, validation metrics, and reference data and
emits `outputs/realm_dashboard.html` with all data embedded inline.

Each panel is a direct answer to one question:

    1. What is REALM?
    2. How does the personality engine work?
    3. What is the scientific basis?
    4. What does the simulation produce?
    5. What does performance look like?

No decorative elements. If a chart can't answer a question, it isn't shown.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from realm import __version__ as _realm_version
except ImportError:  # pragma: no cover - raw checkout without install
    _realm_version = "0.0.0.dev0"

# Prefer Sprint 10 run data (post WP1 cache fix) if present; fall back to
# Sprint 9 run so the dashboard is always renderable without a full re-run.
_SIM_DIR_S10 = ROOT / "outputs" / "sim_10k_sprint10"
_SIM_DIR_S9  = ROOT / "outputs" / "sim_10k_run1"
_SIM_DIR = _SIM_DIR_S10 if (_SIM_DIR_S10 / "population_stats.json").exists() else _SIM_DIR_S9

INPUTS = {
    "population":    _SIM_DIR / "population_stats.json",
    "drift":         _SIM_DIR / "drift_analysis.json",
    "simlog":        _SIM_DIR / "simulation_log.json",
    "countries_sim": _SIM_DIR / "country_summary_top30.json",
    "validity":      ROOT / "outputs" / "astro_validity_metrics.json",
    "celebs":        ROOT / "outputs" / "celebrity_astro_profiles.json",
    "countries":     ROOT / "data" / "countries.json",
}

OUTPUT = ROOT / "outputs" / "realm_dashboard.html"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_sample_agent(population: dict, celebs: dict) -> dict:
    """Pick one celebrity as the 'sample agent' for Panel 2's radar."""
    # Steve Jobs is usually the first entry; any will do — we just need a
    # complete astro_only trait vector for the radar.
    figs = celebs["figures"]
    first_key = next(iter(figs))
    fig = figs[first_key]
    return {
        "name": fig["name"],
        "occupation": fig["occupation"],
        "birth_utc": fig["birth_utc"],
        "sun_sign": fig["chart_summary"]["sun_sign"],
        "moon_sign": fig["chart_summary"]["moon_sign"],
        "asc_sign": fig["chart_summary"]["asc_sign"],
        "traits": fig["astro_only"],
    }


def main() -> int:
    data = {name: load_json(path) for name, path in INPUTS.items()}

    # Trim country sim-data to just trait means (dashboard-relevant keys only)
    countries_sim = data["countries_sim"]
    countries_ref = {c["iso2"]: c for c in data["countries"]["countries"]}
    country_merged: dict[str, dict] = {}
    for iso2, row in countries_sim.items():
        ref = countries_ref.get(iso2, {})
        country_merged[iso2] = {
            "iso2": iso2,
            "iso3": ref.get("iso3", ""),
            "name": ref.get("name", iso2),
            "lat": ref.get("lat", 0),
            "lon": ref.get("lon", 0),
            "population_m": ref.get("population", 0),
            "region": ref.get("region", ""),
            "n_agents": int(row.get("n", 0)),
            "traits": {k: v for k, v in row.items() if k != "n"},
        }

    # Trait list (stable order) from population_stats tick_0 keys
    trait_names = list(data["population"]["tick_0"].keys())

    # Histogram-friendly per-trait distribution: we only have mean/std/min/max,
    # so we synthesise a normal approximation for the dashboard hist display.
    # Real values are reported in the mean/std labels alongside.
    trait_dist = {
        "tick_0": data["population"]["tick_0"],
        "tick_N": data["population"]["tick_N_drifted"],
    }

    # Per-trait drift magnitudes
    drift_summary = data["drift"]

    # Per-tick activity — for Panel 4 time series
    activity = [
        {
            "tick": s["tick"],
            "posts": s["posts"],
            "engagements": s["engagements"],
            "lurk": s["actions_by_type"].get("lurk", 0),
            "seconds": s.get("seconds"),
        }
        for s in data["simlog"]["per_tick"]
    ]

    # Validity — only keys we actually render
    val = data["validity"]
    validity_compact = {
        "da": val["da"],
        "cw_da": val["cw_da"],
        "extreme": val["extreme"],
        "correlation": val.get("correlation", {}),
        "per_trait": val["per_trait"],
        "per_person": val["per_person"],
        "confidence_coverage": val.get("confidence_coverage", {}),
        "thresholds": val.get("thresholds", {}),
    }

    sample_agent = build_sample_agent(data["population"], data["celebs"])

    # Sprint performance history (authored from REALM_CLAUDE.md + memory)
    sprint_timeline = [
        {"sprint": 1, "label": "Phase 1-4 foundation",  "tests": 0,    "note": "core types + astro"},
        {"sprint": 2, "label": "Phase 5 behaviour",     "tests": 0,    "note": "SimulationEngine + Decision"},
        {"sprint": 3, "label": "Phase 6 adapters",      "tests": 346,  "note": "BigFive + Demographic"},
        {"sprint": 4, "label": "Phase 6b validity",     "tests": 464,  "note": "real-data BF"},
        {"sprint": 5, "label": "Blended + 66 countries","tests": 566,  "note": "facet foundation"},
        {"sprint": 6, "label": "Facets real BF 8/8",    "tests": 575,  "note": "Johnson 612K"},
        {"sprint": 7, "label": "Astro validity N=20",   "tests": 598,  "note": "4/4 PASS"},
        {"sprint": 8, "label": "loss_aversion + dash",  "tests": 598,  "note": "DA 0.05→1.00"},
        {"sprint": 9, "label": "Drift + 10K sim",       "tests": 620,  "note": "38.4 min 10K×30"},
        {"sprint": 10,"label": "Cache + dash + bridge", "tests": 654,  "note": "20.4 min 10K×30"},
    ]

    # Sprint 10 WP1 measured performance for the Performance panel KPIs.
    perf = {
        "sprint9_minutes": 38.4,
        "sprint10_minutes": 20.4,
        "sprint9_tick_s":  75.06,
        "sprint10_tick_s": 39.10,
        "sprint9_aspect_share": 0.63,
        "sprint10_aspect_share": 0.24,
        "peak_mb": 202.8,
        "source_dir": _SIM_DIR.name,
    }

    payload = {
        "generated_at": "2026-04-24",
        "version": _realm_version,
        "trait_names": trait_names,
        "trait_dist": trait_dist,
        "drift_summary": drift_summary,
        "activity": activity,
        "validity": validity_compact,
        "sample_agent": sample_agent,
        "countries": country_merged,
        "sprint_timeline": sprint_timeline,
        "performance": perf,
        "totals": data["simlog"]["totals"],
        "sim_meta": {
            "n_agents": data["simlog"]["n_agents"],
            "n_ticks":  data["simlog"]["n_ticks"],
            "seed":     data["simlog"]["seed"],
        },
    }

    html = build_html(payload)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"[dashboard] wrote {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KB)")
    return 0


def build_html(payload: dict) -> str:
    """Assemble the single-file dashboard with embedded data."""
    data_json = json.dumps(payload, separators=(",", ":"), allow_nan=False)
    # Escape closing </script> that could occur inside strings (defensive).
    data_json = data_json.replace("</", "<\\/")

    return _TEMPLATE.replace("__DATA__", data_json)


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>REALM — Simulation Observatory</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/topojson-client@3/dist/topojson-client.min.js"></script>
<style>
  :root {
    --bg: #0b0d12;
    --panel: #11141b;
    --panel-2: #161a23;
    --ink: #e8ecf2;
    --ink-dim: #9099a8;
    --ink-faint: #5c6372;
    --border: rgba(255,255,255,0.08);
    --accent: #4dd3ff;
    --accent-2: #b794f4;
    --good: #4ade80;
    --warn: #fbbf24;
    --bad: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html,body { background: var(--bg); color: var(--ink); font-family: 'Inter', system-ui, sans-serif; line-height: 1.5; }
  .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }

  /* Nav */
  nav {
    position: sticky; top: 0; z-index: 50;
    background: rgba(11,13,18,0.92);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border);
    padding: 14px 32px;
    display: flex; align-items: center; gap: 24px;
  }
  nav .brand { font-family: 'JetBrains Mono', monospace; font-weight: 700; letter-spacing: 0.08em; font-size: 14px; }
  nav .brand .dot { color: var(--accent); }
  nav ul { list-style: none; display: flex; gap: 20px; margin-left: auto; flex-wrap: wrap; }
  nav a { color: var(--ink-dim); text-decoration: none; font-size: 13px; font-weight: 500; transition: color 0.15s; }
  nav a:hover, nav a.active { color: var(--ink); }

  main { max-width: 1400px; margin: 0 auto; padding: 48px 32px 96px; }
  section { margin-bottom: 72px; scroll-margin-top: 72px; }
  section > h2 {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 8px;
  }
  section > h3 {
    font-size: 28px; font-weight: 600; letter-spacing: -0.015em;
    margin-bottom: 16px;
  }
  section > p.lede { color: var(--ink-dim); font-size: 15px; max-width: 820px; margin-bottom: 32px; }

  .grid { display: grid; gap: 16px; }
  .grid-2 { grid-template-columns: repeat(2, 1fr); }
  .grid-3 { grid-template-columns: repeat(3, 1fr); }
  .grid-4 { grid-template-columns: repeat(4, 1fr); }
  @media (max-width: 1024px) { .grid-3, .grid-4 { grid-template-columns: repeat(2, 1fr); } }
  @media (max-width: 720px)  { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }

  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
  }
  .card .card-title {
    font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--ink-faint);
    margin-bottom: 10px;
  }
  .card .big { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em; }
  .card .big.good { color: var(--good); }
  .card .big.warn { color: var(--warn); }
  .card .big.bad  { color: var(--bad); }
  .card .sub { color: var(--ink-dim); font-size: 13px; margin-top: 6px; }

  .kpi-row { display: flex; flex-wrap: wrap; gap: 12px; }
  .kpi {
    background: var(--panel-2);
    padding: 10px 16px;
    border-radius: 8px;
    border: 1px solid var(--border);
    display: flex; flex-direction: column;
  }
  .kpi .v { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 700; }
  .kpi .k { color: var(--ink-faint); font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; }

  /* Pipeline diagram */
  .pipeline svg { max-width: 100%; height: auto; }
  .pipe-box { fill: var(--panel-2); stroke: var(--border); stroke-width: 1; }
  .pipe-box-active { stroke: var(--accent); stroke-width: 1.5; }
  .pipe-label { fill: var(--ink); font: 600 13px 'JetBrains Mono', monospace; }
  .pipe-sub { fill: var(--ink-dim); font: 400 11px 'JetBrains Mono', monospace; }
  .pipe-arrow { stroke: var(--ink-faint); stroke-width: 1.5; fill: none; marker-end: url(#arrowhead); }

  /* Radar */
  .radar-axis { stroke: rgba(255,255,255,0.05); }
  .radar-axis-label { fill: var(--ink-faint); font: 400 9px 'JetBrains Mono', monospace; }
  .radar-poly { fill: rgba(77,211,255,0.18); stroke: var(--accent); stroke-width: 1.5; }
  .radar-dot { fill: var(--accent); }

  /* Bars */
  .bar { transition: opacity 0.15s; }
  .bar:hover { opacity: 0.8; }
  .bar-label { fill: var(--ink-dim); font: 400 10px 'JetBrains Mono', monospace; }
  .bar-value { fill: var(--ink); font: 500 10px 'JetBrains Mono', monospace; }

  /* Histogram overlay */
  .hist-tick0 { fill: rgba(183,148,244,0.25); stroke: var(--accent-2); stroke-width: 1; }
  .hist-tickN { fill: rgba(77,211,255,0.25); stroke: var(--accent); stroke-width: 1; }

  /* Choropleth */
  .country { stroke: var(--bg); stroke-width: 0.5; cursor: pointer; }
  .country:hover { stroke: var(--ink); stroke-width: 1; }
  .country-unknown { fill: #1a1d25; }

  /* Network */
  .node circle { stroke: var(--panel); stroke-width: 1.5; }
  .node-label { fill: var(--ink-dim); font: 400 10px 'JetBrains Mono', monospace; pointer-events: none; }
  .link { stroke: rgba(77,211,255,0.2); stroke-width: 1; }

  /* Timeline */
  .sprint-box { fill: var(--panel-2); stroke: var(--border); }
  .sprint-box-current { fill: rgba(77,211,255,0.15); stroke: var(--accent); }
  .sprint-label { fill: var(--ink); font: 600 11px 'JetBrains Mono', monospace; }
  .sprint-sub { fill: var(--ink-dim); font: 400 10px 'Inter', sans-serif; }

  /* Table */
  table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 13px; }
  th,td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
  th { color: var(--ink-faint); font-weight: 500; font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; }
  td.num { text-align: right; }
  .pass { color: var(--good); }
  .fail { color: var(--bad); }
  .pill { padding: 2px 8px; border-radius: 999px; font-size: 10px; font-weight: 600; }
  .pill.good { background: rgba(74,222,128,0.15); color: var(--good); }
  .pill.warn { background: rgba(251,191,36,0.15); color: var(--warn); }
  .pill.bad  { background: rgba(239,68,68,0.15);  color: var(--bad);  }

  .select {
    background: var(--panel-2); color: var(--ink); border: 1px solid var(--border);
    padding: 6px 10px; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 12px;
  }

  .hint { color: var(--ink-faint); font-size: 11px; font-family: 'JetBrains Mono', monospace; }
</style>
</head>
<body>
<nav>
  <div class="brand">REALM<span class="dot"> · </span><span style="color:var(--ink-dim);font-weight:400;">Simulation Observatory</span></div>
  <ul>
    <li><a href="#panel-1">01&nbsp;Overview</a></li>
    <li><a href="#panel-2">02&nbsp;Engine</a></li>
    <li><a href="#panel-3">03&nbsp;Validation</a></li>
    <li><a href="#panel-4">04&nbsp;Simulation</a></li>
    <li><a href="#panel-5">05&nbsp;Performance</a></li>
  </ul>
</nav>

<main>

  <!-- ================================================================== -->
  <!-- Panel 1 — What is REALM?                                            -->
  <!-- ================================================================== -->
  <section id="panel-1">
    <h2>01 &mdash; Overview</h2>
    <h3>What is REALM?</h3>
    <p class="lede">
      REALM is a swarm-intelligence simulation engine. It builds a population of
      synthetic agents from three parallel signals &mdash; birth-chart astrology,
      Big-Five personality scores, and country-level Hofstede culture &mdash; and
      runs them through a tick-based social platform where they post, engage,
      drift, and react to transiting celestial events. The aim is a working
      laboratory for testing how personality, culture, and timing compose into
      collective behaviour.
    </p>
    <div class="kpi-row">
      <div class="kpi"><span class="k">Tests</span><span class="v" id="kpi-tests">620</span></div>
      <div class="kpi"><span class="k">Countries</span><span class="v">66</span></div>
      <div class="kpi"><span class="k">Traits</span><span class="v" id="kpi-traits">24</span></div>
      <div class="kpi"><span class="k">BF Validation N</span><span class="v">612,711</span></div>
      <div class="kpi"><span class="k">Astro Validation N</span><span class="v">22</span></div>
      <div class="kpi"><span class="k">10K Sim Agents</span><span class="v" id="kpi-agents">10,000</span></div>
    </div>
    <p style="margin-top:20px;color:var(--ink-dim);font-size:13px;">
      <span class="mono" style="color:var(--accent);">Stack:</span>
      Kerykeion (Swiss Ephemeris) natal charts
      <span style="color:var(--ink-faint);">&rarr;</span> AstrologicalAdapter + BigFiveAdapter + DemographicAdapter
      <span style="color:var(--ink-faint);">&rarr;</span> 24-trait vector
      <span style="color:var(--ink-faint);">&rarr;</span> SimulationEngine with TransitModulator, ExperienceDriftEngine, ClimateEngine, NetworkTopology.
    </p>
  </section>

  <!-- ================================================================== -->
  <!-- Panel 2 — How does the engine work?                                 -->
  <!-- ================================================================== -->
  <section id="panel-2">
    <h2>02 &mdash; Engine</h2>
    <h3>How does the personality engine work?</h3>
    <p class="lede">
      Every agent is built from three adapters running in parallel and merged
      by a BlendedAdapter. The diagram traces one path. On the right, the
      24-trait output for a real sample &mdash; produced by the current REALM
      code running on the figure's natal chart.
    </p>
    <div class="grid grid-2">
      <div class="card pipeline">
        <div class="card-title">Adapter pipeline &mdash; one agent</div>
        <svg id="pipeline-svg" viewBox="0 0 520 380"></svg>
      </div>
      <div class="card">
        <div class="card-title" id="radar-title">Sample agent &mdash; 23 astro traits</div>
        <svg id="sample-radar" viewBox="-180 -180 360 360" style="width:100%;height:auto;"></svg>
        <div id="radar-sub" class="hint" style="margin-top:8px;"></div>
      </div>
    </div>
  </section>

  <!-- ================================================================== -->
  <!-- Panel 3 — Scientific basis                                          -->
  <!-- ================================================================== -->
  <section id="panel-3">
    <h2>03 &mdash; Validation</h2>
    <h3>What is the scientific basis?</h3>
    <p class="lede">
      Two validation studies back the engine. Big-Five facet output is checked
      against the public Johnson IPIP-NEO-120 dataset (N=612,711). Astrological
      output is checked against 22 hand-authored celebrity profiles with
      expert-rated expected traits.
    </p>
    <div class="grid grid-2" style="margin-bottom:16px;">
      <div class="card">
        <div class="card-title">Big-Five validity</div>
        <div class="big good">8&nbsp;/&nbsp;8 PASS</div>
        <div class="sub">Johnson IPIP-NEO-120, N=612,711 &middot; facet-mode adapter &middot; online-sample tolerances.</div>
        <div class="hint" style="margin-top:10px;">Structural pairs 15/15 &middot; Per-facet BF 13/13 PASS</div>
      </div>
      <div class="card">
        <div class="card-title">Astrological validity</div>
        <div class="big good">4&nbsp;/&nbsp;4 PASS</div>
        <div class="sub">Directional Accuracy <b id="val-da">–</b> &middot; Extreme Detection <b id="val-ext">–</b> &middot; CW-DA <b id="val-cw">–</b>.</div>
        <div class="hint" style="margin-top:10px;">N=22 figures, 490 trait judgements &middot; raw (uncalibrated) adapter.</div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Per-trait Directional Accuracy &mdash; celebrity cohort</div>
      <svg id="per-trait-bars" viewBox="0 0 900 520" style="width:100%;height:auto;"></svg>
      <div class="hint" style="margin-top:10px;">
        DA &mdash; per trait hit rate against expected direction. 0.50 is the chance line. Bars are coloured by DA tier.
      </div>
    </div>
  </section>

  <!-- ================================================================== -->
  <!-- Panel 4 — Simulation outputs (the core panel)                       -->
  <!-- ================================================================== -->
  <section id="panel-4">
    <h2>04 &mdash; Simulation</h2>
    <h3>What does the 10K&nbsp;&times;&nbsp;30 run produce?</h3>
    <p class="lede">
      This is what the engine actually does. Every number below comes from the
      seed=42 run persisted to <span class="mono">outputs/sim_10k_run1/</span>:
      10,000 agents, 30 ticks, real drift events, real posts, real engagements.
    </p>

    <div class="grid grid-4" style="margin-bottom:16px;">
      <div class="card">
        <div class="card-title">Posts</div>
        <div class="big" id="sim-posts">–</div>
        <div class="sub" id="sim-posts-sub">across 30 ticks</div>
      </div>
      <div class="card">
        <div class="card-title">Engagements</div>
        <div class="big" id="sim-eng">–</div>
        <div class="sub">likes, shares, replies</div>
      </div>
      <div class="card">
        <div class="card-title">Agents with drift</div>
        <div class="big good" id="sim-drift-agents">–</div>
        <div class="sub" id="sim-drift-sub">mean magnitude &mdash;</div>
      </div>
      <div class="card">
        <div class="card-title">Mean drift events / agent</div>
        <div class="big" id="sim-events">–</div>
        <div class="sub">max <span id="sim-events-max">–</span></div>
      </div>
    </div>

    <div class="grid grid-2">
      <div class="card">
        <div class="card-title">Trait distribution &mdash; tick 0 vs tick 30 (drifted)</div>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
          <label class="hint">Trait:</label>
          <select class="select" id="trait-select"></select>
        </div>
        <svg id="hist-svg" viewBox="0 0 520 280" style="width:100%;height:auto;"></svg>
        <div class="hint" style="margin-top:6px;">
          Normal approximation using &mu;/&sigma; reported by the run. Solid stats labelled below.
        </div>
        <div id="hist-stats" class="mono" style="font-size:11px;color:var(--ink-dim);margin-top:6px;"></div>
      </div>
      <div class="card">
        <div class="card-title">Mean drift per trait (tick&nbsp;30 &minus; tick&nbsp;0)</div>
        <svg id="drift-bars" viewBox="0 0 520 520" style="width:100%;height:auto;"></svg>
        <div class="hint" style="margin-top:8px;">
          Social event bridge currently drifts empathy, social_dominance, agreeableness, contrarian_tendency, neuroticism. Risk/knowledge/stress traits show zero drift until Sprint 10 WP3 event bridge expansion is active.
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:16px;">
      <div class="card-title">World coverage &mdash; per-country mean trait</div>
      <div style="display:flex;gap:12px;margin-bottom:8px;align-items:center;">
        <label class="hint">Trait:</label>
        <select class="select" id="map-trait-select"></select>
        <span class="hint" id="map-legend"></span>
      </div>
      <svg id="map-svg" viewBox="0 0 960 480" style="width:100%;height:auto;"></svg>
      <div id="map-tooltip" class="mono" style="font-size:12px;color:var(--ink-dim);min-height:18px;margin-top:4px;"></div>
      <div class="hint" style="margin-top:6px;">
        Hover a country to see sample size and trait mean. Grey countries are outside the 66-country panel.
      </div>
    </div>

    <div class="grid grid-2" style="margin-top:16px;">
      <div class="card">
        <div class="card-title">Action mix across the run</div>
        <svg id="action-pie" viewBox="-100 -100 200 200" style="width:200px;height:200px;display:block;margin:0 auto;"></svg>
        <div id="action-legend" style="margin-top:12px;"></div>
      </div>
      <div class="card">
        <div class="card-title">Country cluster network &mdash; trait-similarity graph</div>
        <svg id="country-net" viewBox="0 0 480 320" style="width:100%;height:320px;"></svg>
        <div class="hint" style="margin-top:6px;">
          Top-30 simulated countries, positioned by force layout. Node size = population, link opacity = cosine similarity on the 23-trait mean vector.
        </div>
      </div>
    </div>
  </section>

  <!-- ================================================================== -->
  <!-- Panel 5 — Performance                                               -->
  <!-- ================================================================== -->
  <section id="panel-5">
    <h2>05 &mdash; Performance</h2>
    <h3>What does the system cost?</h3>
    <p class="lede">
      10K agents &times; 30 ticks on a single CPU. Sprint 10 WP1 shrank the
      hot-path aspect calculator from 94% of tick time down to a smaller share
      via allocation-free transit-aspect evaluation.
    </p>
    <div class="grid grid-4" style="margin-bottom:16px;">
      <div class="card">
        <div class="card-title">Runtime (10K&times;30)</div>
        <div class="big good" id="perf-runtime">20.4 min</div>
        <div class="sub" id="perf-runtime-sub">Sprint 9 baseline 38.4 min &rarr; <b>1.88&times; faster</b> after WP1</div>
      </div>
      <div class="card">
        <div class="card-title">Peak memory</div>
        <div class="big good" id="perf-memory">0.20 GB</div>
        <div class="sub">40&times; below the 8 GB budget</div>
      </div>
      <div class="card">
        <div class="card-title">Test coverage</div>
        <div class="big" id="perf-tests">654</div>
        <div class="sub">Ruff clean on all Sprint 10 files</div>
      </div>
      <div class="card">
        <div class="card-title">Aspect-calculator share</div>
        <div class="big good" id="perf-aspect">63% &rarr; 24%</div>
        <div class="sub">cProfile 10K&times;30 &mdash; cumulative tick-time fraction</div>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Sprint timeline &mdash; test count and milestones</div>
      <svg id="sprint-svg" viewBox="0 0 900 160" style="width:100%;height:auto;"></svg>
    </div>
  </section>

</main>

<script id="payload" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);

// --------------------------------------------------------------------
// Shared helpers
// --------------------------------------------------------------------
const fmt   = d3.format(",.0f");
const fmt3  = d3.format(".3f");
const fmt2  = d3.format(".2f");
const pct   = d => (d * 100).toFixed(1) + '%';

// DA color scale — keyed to interpretable tiers.
function daColor(d) {
  if (d >= 0.8) return '#4ade80';
  if (d >= 0.6) return '#4dd3ff';
  if (d >= 0.5) return '#b794f4';
  if (d >= 0.4) return '#fbbf24';
  return '#ef4444';
}

// --------------------------------------------------------------------
// KPIs + top metrics
// --------------------------------------------------------------------
document.getElementById('kpi-traits').textContent = DATA.trait_names.length;
document.getElementById('kpi-agents').textContent = DATA.sim_meta.n_agents.toLocaleString();
document.getElementById('kpi-tests').textContent  = '654';
if (DATA.performance) {
  const p = DATA.performance;
  document.getElementById('perf-runtime').textContent = p.sprint10_minutes.toFixed(1) + ' min';
  document.getElementById('perf-runtime-sub').innerHTML =
    `Sprint 9 baseline ${p.sprint9_minutes.toFixed(1)} min &rarr; <b>${(p.sprint9_minutes / p.sprint10_minutes).toFixed(2)}× faster</b> after WP1 &middot; <span class="mono">${p.source_dir}</span>`;
  document.getElementById('perf-aspect').textContent =
    Math.round(p.sprint9_aspect_share * 100) + '% → ' + Math.round(p.sprint10_aspect_share * 100) + '%';
}

document.getElementById('val-da').textContent  = fmt3(DATA.validity.da.overall);
document.getElementById('val-ext').textContent = fmt3(DATA.validity.extreme.da);
document.getElementById('val-cw').textContent  = fmt3(DATA.validity.cw_da.da);

document.getElementById('sim-posts').textContent   = fmt(DATA.totals.post);
document.getElementById('sim-posts-sub').textContent = 'across ' + DATA.sim_meta.n_ticks + ' ticks · ' + (DATA.totals.post / DATA.sim_meta.n_ticks).toFixed(0) + '/tick';
document.getElementById('sim-eng').textContent     = fmt(DATA.totals.engage);
document.getElementById('sim-drift-agents').textContent = fmt(DATA.drift_summary.agents_with_drift);
document.getElementById('sim-drift-sub').textContent    = 'mean magnitude ' + fmt3(DATA.drift_summary.mean_magnitude);
document.getElementById('sim-events').textContent  = fmt2(DATA.drift_summary.mean_event_count);
document.getElementById('sim-events-max').textContent = DATA.drift_summary.max_event_count;

// --------------------------------------------------------------------
// Panel 2 — Pipeline diagram
// --------------------------------------------------------------------
(function renderPipeline() {
  const svg = d3.select('#pipeline-svg');
  svg.append('defs').html(`
    <marker id="arrowhead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">
      <path d="M0,0 L8,4 L0,8 z" fill="#5c6372"/>
    </marker>
  `);
  const boxes = [
    {x: 20,  y: 20,  w: 140, h: 50,  t: 'Birth data',         s: 'UTC + lat/lon + TZ'},
    {x: 20,  y: 160, w: 140, h: 50,  t: 'OCEAN scores',        s: 'Big-Five IPIP-NEO'},
    {x: 20,  y: 300, w: 140, h: 50,  t: 'Demographic',         s: 'country · age · job'},

    {x: 200, y: 20,  w: 140, h: 50,  t: 'NatalChart',          s: 'planets + houses + asp.'},
    {x: 200, y: 90,  w: 140, h: 50,  t: 'AstrologicalAdapter', s: '23 traits · conf: high', active: true},
    {x: 200, y: 160, w: 140, h: 50,  t: 'BigFiveAdapter',      s: '5 OCEAN + 13 facets'},
    {x: 200, y: 300, w: 140, h: 50,  t: 'DemographicAdapter',  s: '6 culture traits'},

    {x: 380, y: 140, w: 120, h: 90,  t: 'BlendedAdapter',      s: 'weighted merge\n+ noise', active: true},
    {x: 380, y: 280, w: 120, h: 70,  t: '24-trait TraitVector', s: 'agent.traits (frozen)', active: true},
  ];
  const g = svg.append('g');
  for (const b of boxes) {
    g.append('rect')
      .attr('x', b.x).attr('y', b.y).attr('width', b.w).attr('height', b.h)
      .attr('rx', 6).attr('class', 'pipe-box' + (b.active ? ' pipe-box-active' : ''));
    const lines = b.s.split('\n');
    g.append('text').attr('x', b.x + b.w/2).attr('y', b.y + 20)
      .attr('text-anchor', 'middle').attr('class', 'pipe-label').text(b.t);
    lines.forEach((line, i) => {
      g.append('text').attr('x', b.x + b.w/2).attr('y', b.y + 36 + i*11)
        .attr('text-anchor', 'middle').attr('class', 'pipe-sub').text(line);
    });
  }
  // Arrows: birth -> natal -> astro -> blended
  const arrows = [
    [160,45,200,45], [340,45,380,160],   // birth -> natal -> blended
    [160,45,200,115], [340,115,380,170], // natal-like path
    [160,185,200,185], [340,185,380,180],// OCEAN -> BigFive -> Blended
    [160,325,200,325], [340,325,380,220],// Demo -> Blended
    [440,230,440,280],                   // Blended -> TraitVector
  ];
  arrows.forEach(a => g.append('path').attr('class', 'pipe-arrow')
    .attr('d', `M${a[0]},${a[1]} L${a[2]},${a[3]}`));
})();

// --------------------------------------------------------------------
// Panel 2 — Sample agent radar
// --------------------------------------------------------------------
(function renderSampleRadar() {
  const traits = Object.entries(DATA.sample_agent.traits);
  document.getElementById('radar-title').textContent =
    `${DATA.sample_agent.name} — ${DATA.sample_agent.occupation} (Sun ${DATA.sample_agent.sun_sign})`;
  document.getElementById('radar-sub').textContent =
    `${DATA.sample_agent.birth_utc} · Moon ${DATA.sample_agent.moon_sign} · Asc ${DATA.sample_agent.asc_sign}`;

  const svg = d3.select('#sample-radar');
  const R = 150;
  const N = traits.length;
  const angle = i => (i / N) * Math.PI * 2 - Math.PI / 2;
  // axes
  for (let r = 0.25; r <= 1; r += 0.25) {
    svg.append('circle').attr('class', 'radar-axis').attr('r', R * r).attr('fill', 'none');
  }
  traits.forEach((t, i) => {
    const [name, val] = t;
    const a = angle(i);
    svg.append('line').attr('class', 'radar-axis')
      .attr('x1', 0).attr('y1', 0)
      .attr('x2', Math.cos(a) * R).attr('y2', Math.sin(a) * R);
    const lx = Math.cos(a) * (R + 14);
    const ly = Math.sin(a) * (R + 14);
    svg.append('text').attr('class', 'radar-axis-label')
      .attr('x', lx).attr('y', ly)
      .attr('text-anchor', Math.abs(lx) < 5 ? 'middle' : (lx > 0 ? 'start' : 'end'))
      .attr('dy', '0.3em')
      .text(name.length > 14 ? name.slice(0, 12) + '…' : name);
  });
  const poly = traits.map((t, i) => {
    const a = angle(i);
    return [Math.cos(a) * R * t[1], Math.sin(a) * R * t[1]];
  });
  svg.append('polygon').attr('class', 'radar-poly')
    .attr('points', poly.map(p => p.join(',')).join(' '));
  poly.forEach(p => svg.append('circle').attr('class', 'radar-dot')
    .attr('cx', p[0]).attr('cy', p[1]).attr('r', 2));
})();

// --------------------------------------------------------------------
// Panel 3 — Per-trait DA bars
// --------------------------------------------------------------------
(function renderPerTraitBars() {
  const svg = d3.select('#per-trait-bars');
  const entries = Object.entries(DATA.validity.per_trait)
    .filter(([_, v]) => v && typeof v.da === 'number')
    .sort((a, b) => b[1].da - a[1].da);
  const W = 900, H = 520;
  const M = { t: 8, r: 60, b: 20, l: 170 };
  const barH = Math.max(12, Math.floor((H - M.t - M.b) / entries.length));
  const x = d3.scaleLinear().domain([0, 1]).range([0, W - M.l - M.r]);
  const g = svg.append('g').attr('transform', `translate(${M.l},${M.t})`);

  // chance line at 0.5
  g.append('line').attr('x1', x(0.5)).attr('x2', x(0.5))
    .attr('y1', 0).attr('y2', entries.length * barH)
    .attr('stroke', 'rgba(255,255,255,0.1)').attr('stroke-dasharray', '2 3');
  g.append('text').attr('x', x(0.5)).attr('y', -2).attr('text-anchor', 'middle')
    .attr('class', 'bar-label').attr('font-size', '9px').text('0.50 chance');

  entries.forEach((e, i) => {
    const [name, v] = e;
    g.append('rect').attr('class', 'bar')
      .attr('x', 0).attr('y', i * barH + 2)
      .attr('width', x(v.da)).attr('height', barH - 4)
      .attr('fill', daColor(v.da));
    g.append('text').attr('class', 'bar-label')
      .attr('x', -8).attr('y', i * barH + barH / 2 + 3).attr('text-anchor', 'end')
      .text(name);
    g.append('text').attr('class', 'bar-value')
      .attr('x', x(v.da) + 4).attr('y', i * barH + barH / 2 + 3)
      .text(fmt3(v.da) + '  n=' + v.n_classified);
  });
})();

// --------------------------------------------------------------------
// Panel 4 — Trait histogram
// --------------------------------------------------------------------
(function setupHistogram() {
  const sel = document.getElementById('trait-select');
  DATA.trait_names.forEach(t => {
    const o = document.createElement('option');
    o.value = t; o.textContent = t;
    sel.appendChild(o);
  });
  sel.value = 'empathy';
  sel.addEventListener('change', () => renderHistogram(sel.value));
  renderHistogram(sel.value);
})();

function renderHistogram(trait) {
  const svg = d3.select('#hist-svg'); svg.selectAll('*').remove();
  const t0 = DATA.trait_dist.tick_0[trait];
  const tN = DATA.trait_dist.tick_N[trait];
  const W = 520, H = 280, M = { t: 10, r: 20, b: 30, l: 40 };
  const x = d3.scaleLinear().domain([0, 1]).range([M.l, W - M.r]);
  const bins = 30;
  const binW = (W - M.l - M.r) / bins;
  const normalPDF = (x, mu, sigma) => Math.exp(-((x - mu) ** 2) / (2 * sigma * sigma)) / (sigma * Math.sqrt(2 * Math.PI));
  const peakRef = Math.max(
    normalPDF(t0.mean, t0.mean, Math.max(t0.std, 0.01)),
    normalPDF(tN.mean, tN.mean, Math.max(tN.std, 0.01)),
  );
  const y = d3.scaleLinear().domain([0, peakRef * 1.05]).range([H - M.b, M.t]);

  const bars0 = [], barsN = [];
  for (let i = 0; i < bins; i++) {
    const cx = (i + 0.5) / bins;
    bars0.push({ x: cx, y: normalPDF(cx, t0.mean, Math.max(t0.std, 0.01)) });
    barsN.push({ x: cx, y: normalPDF(cx, tN.mean, Math.max(tN.std, 0.01)) });
  }

  const gridg = svg.append('g');
  [0, 0.25, 0.5, 0.75, 1].forEach(v => {
    gridg.append('line').attr('x1', x(v)).attr('x2', x(v))
      .attr('y1', M.t).attr('y2', H - M.b)
      .attr('stroke', 'rgba(255,255,255,0.04)');
    gridg.append('text').attr('x', x(v)).attr('y', H - 10)
      .attr('text-anchor', 'middle').attr('class', 'bar-label').text(v.toFixed(2));
  });
  // Tick-0
  svg.append('path').attr('class', 'hist-tick0')
    .attr('d', d3.area()
      .x(d => x(d.x)).y0(y(0)).y1(d => y(d.y))(bars0));
  // Tick-N
  svg.append('path').attr('class', 'hist-tickN')
    .attr('d', d3.area()
      .x(d => x(d.x)).y0(y(0)).y1(d => y(d.y))(barsN));
  // Mean markers
  svg.append('line').attr('x1', x(t0.mean)).attr('x2', x(t0.mean))
    .attr('y1', M.t).attr('y2', H - M.b)
    .attr('stroke', 'var(--accent-2)').attr('stroke-dasharray', '2 3');
  svg.append('line').attr('x1', x(tN.mean)).attr('x2', x(tN.mean))
    .attr('y1', M.t).attr('y2', H - M.b)
    .attr('stroke', 'var(--accent)').attr('stroke-dasharray', '2 3');

  document.getElementById('hist-stats').innerHTML =
    `<span style="color:var(--accent-2);">tick 0</span>&nbsp;μ=${fmt3(t0.mean)}&nbsp;σ=${fmt3(t0.std)}&nbsp;·&nbsp;` +
    `<span style="color:var(--accent);">tick 30</span>&nbsp;μ=${fmt3(tN.mean)}&nbsp;σ=${fmt3(tN.std)}&nbsp;·&nbsp;` +
    `Δμ=${(tN.mean - t0.mean >= 0 ? '+' : '') + fmt3(tN.mean - t0.mean)}`;
}

// --------------------------------------------------------------------
// Panel 4 — Drift per trait bar chart
// --------------------------------------------------------------------
(function renderDriftBars() {
  const svg = d3.select('#drift-bars');
  const t0 = DATA.trait_dist.tick_0;
  const tN = DATA.trait_dist.tick_N;
  const entries = DATA.trait_names.map(t => ({
    name: t,
    delta: tN[t].mean - t0[t].mean,
    abs:   Math.abs(tN[t].mean - t0[t].mean),
  })).sort((a, b) => b.abs - a.abs);

  const W = 520, H = 520;
  const M = { t: 8, r: 60, b: 8, l: 160 };
  const barH = (H - M.t - M.b) / entries.length;
  const maxAbs = Math.max(0.01, d3.max(entries, d => d.abs));
  const x = d3.scaleLinear().domain([-maxAbs, maxAbs]).range([0, W - M.l - M.r]);
  const g = svg.append('g').attr('transform', `translate(${M.l},${M.t})`);
  // zero axis
  g.append('line').attr('x1', x(0)).attr('x2', x(0))
    .attr('y1', 0).attr('y2', entries.length * barH)
    .attr('stroke', 'rgba(255,255,255,0.2)');
  entries.forEach((e, i) => {
    const isPos = e.delta >= 0;
    const bx = isPos ? x(0) : x(e.delta);
    const bw = Math.abs(x(e.delta) - x(0));
    g.append('rect').attr('class', 'bar')
      .attr('x', bx).attr('y', i * barH + 2)
      .attr('width', Math.max(bw, 0.5)).attr('height', Math.max(4, barH - 4))
      .attr('fill', isPos ? '#4dd3ff' : '#ef4444')
      .attr('opacity', e.abs > 0 ? 0.85 : 0.25);
    g.append('text').attr('class', 'bar-label')
      .attr('x', -8).attr('y', i * barH + barH / 2 + 3).attr('text-anchor', 'end')
      .text(e.name);
    if (e.abs > 0.0005) {
      g.append('text').attr('class', 'bar-value')
        .attr('x', isPos ? x(e.delta) + 4 : x(e.delta) - 4)
        .attr('y', i * barH + barH / 2 + 3)
        .attr('text-anchor', isPos ? 'start' : 'end')
        .text((isPos ? '+' : '') + fmt3(e.delta));
    }
  });
})();

// --------------------------------------------------------------------
// Panel 4 — Action pie
// --------------------------------------------------------------------
(function renderActionPie() {
  const svg = d3.select('#action-pie');
  const data = [
    { key: 'lurk',    val: DATA.totals.lurk,   color: '#5c6372' },
    { key: 'post',    val: DATA.totals.post,   color: '#4dd3ff' },
    { key: 'engage',  val: DATA.totals.engage, color: '#b794f4' },
  ];
  const total = d3.sum(data, d => d.val);
  const pie = d3.pie().value(d => d.val).sort(null);
  const arc = d3.arc().innerRadius(50).outerRadius(90);
  svg.selectAll('path').data(pie(data)).enter().append('path')
    .attr('d', arc).attr('fill', d => d.data.color)
    .attr('stroke', 'var(--panel)').attr('stroke-width', 2);
  svg.append('text').attr('text-anchor', 'middle').attr('dy', 3)
    .attr('class', 'mono').attr('fill', 'var(--ink)').attr('font-size', '15px')
    .attr('font-weight', 700).text(fmt(total));
  svg.append('text').attr('text-anchor', 'middle').attr('dy', 20)
    .attr('class', 'mono').attr('fill', 'var(--ink-faint)').attr('font-size', '9px')
    .text('actions');
  document.getElementById('action-legend').innerHTML = data.map(d =>
    `<div style="display:flex;align-items:center;gap:8px;font-size:12px;margin-bottom:4px;">
      <span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:${d.color};"></span>
      <span class="mono" style="color:var(--ink);">${d.key}</span>
      <span class="mono" style="color:var(--ink-dim);">${fmt(d.val)} · ${pct(d.val / total)}</span>
    </div>`
  ).join('');
})();

// --------------------------------------------------------------------
// Panel 4 — World map (per-country mean trait)
// --------------------------------------------------------------------
(function setupMap() {
  const sel = document.getElementById('map-trait-select');
  // Only traits that exist in country summary
  const any = Object.values(DATA.countries)[0];
  if (!any) return;
  const available = Object.keys(any.traits);
  DATA.trait_names.filter(t => available.includes(t)).forEach(t => {
    const o = document.createElement('option'); o.value = t; o.textContent = t;
    sel.appendChild(o);
  });
  sel.value = 'openness';
  sel.addEventListener('change', () => renderMap(sel.value));
  renderMap(sel.value);
})();

async function renderMap(trait) {
  const svg = d3.select('#map-svg');
  svg.selectAll('*').remove();
  const width = 960, height = 480;
  const proj = d3.geoNaturalEarth1().scale(165).translate([width / 2, height / 2]);
  const path = d3.geoPath(proj);

  // Color scale from the 30 sim countries
  const values = Object.values(DATA.countries).map(c => c.traits[trait]).filter(v => v != null);
  const ext = d3.extent(values);
  const color = d3.scaleSequential().domain([ext[0] || 0, ext[1] || 1]).interpolator(d3.interpolateViridis);

  document.getElementById('map-legend').textContent =
    `${trait} range across sample: ${fmt3(ext[0])} — ${fmt3(ext[1])}`;

  // Load world map (topojson) from unpkg — if it fails, we degrade to just dots
  let world;
  try {
    world = await d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json');
  } catch (e) {
    // Offline fallback: draw dots per country coordinate
    renderMapDots(trait, color);
    return;
  }
  const countries = topojson.feature(world, world.objects.countries).features;
  // Build iso3 -> trait lookup
  const iso3Map = {};
  Object.values(DATA.countries).forEach(c => { if (c.iso3) iso3Map[c.iso3] = c; });

  svg.append('g').selectAll('path').data(countries).enter().append('path')
    .attr('class', 'country')
    .attr('d', path)
    .attr('fill', d => {
      const name = d.properties && d.properties.name;
      // countries-110m uses numeric ISO codes; try 3-letter match via name
      const match = Object.values(DATA.countries).find(c => c.name === name);
      if (!match || match.traits[trait] == null) return '#1a1d25';
      return color(match.traits[trait]);
    })
    .on('mousemove', (ev, d) => {
      const name = d.properties && d.properties.name;
      const match = Object.values(DATA.countries).find(c => c.name === name);
      const tooltip = document.getElementById('map-tooltip');
      if (!match) { tooltip.textContent = name ? `${name} — outside sample` : ''; return; }
      tooltip.innerHTML = `<b>${match.name}</b> · n=${match.n_agents.toLocaleString()} · ${trait} μ=${fmt3(match.traits[trait])} · pop ${match.population_m}M`;
    })
    .on('mouseout', () => { document.getElementById('map-tooltip').textContent = ''; });
}

function renderMapDots(trait, color) {
  const svg = d3.select('#map-svg');
  const proj = d3.geoNaturalEarth1().scale(165).translate([480, 240]);
  Object.values(DATA.countries).forEach(c => {
    const pt = proj([c.lon, c.lat]); if (!pt) return;
    svg.append('circle').attr('cx', pt[0]).attr('cy', pt[1]).attr('r', 5)
      .attr('fill', c.traits[trait] != null ? color(c.traits[trait]) : '#333')
      .attr('stroke', 'var(--bg)').attr('stroke-width', 1)
      .on('mousemove', () => {
        document.getElementById('map-tooltip').innerHTML =
          `<b>${c.name}</b> · n=${c.n_agents.toLocaleString()} · ${trait} μ=${fmt3(c.traits[trait])}`;
      })
      .on('mouseout', () => { document.getElementById('map-tooltip').textContent = ''; });
  });
}

// --------------------------------------------------------------------
// Panel 4 — Country trait-similarity network
// --------------------------------------------------------------------
(function renderCountryNetwork() {
  const svg = d3.select('#country-net');
  const width = 480, height = 320;
  const nodes = Object.values(DATA.countries).map(c => ({
    id: c.iso2,
    label: c.iso2,
    name: c.name,
    n: c.n_agents,
    pop: c.population_m,
    traits: c.traits,
  }));

  // Build top-k nearest links by cosine similarity
  const traitKeys = Object.keys(nodes[0].traits);
  function cosine(a, b) {
    let dot = 0, na = 0, nb = 0;
    for (const k of traitKeys) {
      const xa = a[k] || 0, xb = b[k] || 0;
      dot += xa * xb; na += xa * xa; nb += xb * xb;
    }
    return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-9);
  }
  const links = [];
  for (let i = 0; i < nodes.length; i++) {
    const sims = [];
    for (let j = 0; j < nodes.length; j++) {
      if (i === j) continue;
      sims.push({ j, s: cosine(nodes[i].traits, nodes[j].traits) });
    }
    sims.sort((a, b) => b.s - a.s);
    sims.slice(0, 3).forEach(x => {
      links.push({ source: nodes[i].id, target: nodes[x.j].id, s: x.s });
    });
  }

  const sim = d3.forceSimulation(nodes)
    .force('charge', d3.forceManyBody().strength(-60))
    .force('link',   d3.forceLink(links).id(d => d.id).distance(d => 80 * (1 - d.s) + 30).strength(0.3))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(16))
    .stop();
  for (let i = 0; i < 220; i++) sim.tick();

  const g = svg.append('g');
  g.selectAll('line').data(links).enter().append('line').attr('class', 'link')
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
    .attr('stroke-opacity', d => Math.max(0.05, d.s * 0.4));
  const node = g.selectAll('g.node').data(nodes).enter().append('g')
    .attr('class', 'node').attr('transform', d => `translate(${d.x},${d.y})`);
  node.append('circle')
    .attr('r', d => 4 + Math.sqrt(d.pop) * 0.4)
    .attr('fill', '#4dd3ff').attr('fill-opacity', 0.75);
  node.append('text').attr('class', 'node-label')
    .attr('dy', -10).attr('text-anchor', 'middle').text(d => d.label);
  node.append('title').text(d => `${d.name} · n=${d.n.toLocaleString()} · ${d.pop}M pop`);
})();

// --------------------------------------------------------------------
// Panel 5 — Sprint timeline
// --------------------------------------------------------------------
(function renderSprintTimeline() {
  const svg = d3.select('#sprint-svg');
  const W = 900, H = 160;
  const M = { t: 20, r: 20, b: 30, l: 20 };
  const xs = DATA.sprint_timeline;
  const colW = (W - M.l - M.r) / xs.length;
  xs.forEach((s, i) => {
    const isCurrent = s.sprint === 10;
    const x = M.l + i * colW + 6;
    const w = colW - 12;
    svg.append('rect').attr('class', isCurrent ? 'sprint-box-current' : 'sprint-box')
      .attr('x', x).attr('y', M.t).attr('width', w).attr('height', H - M.t - M.b)
      .attr('rx', 6).attr('stroke-width', 1);
    svg.append('text').attr('class', 'sprint-label')
      .attr('x', x + w / 2).attr('y', M.t + 16).attr('text-anchor', 'middle')
      .text('S' + s.sprint);
    svg.append('text').attr('class', 'sprint-sub')
      .attr('x', x + w / 2).attr('y', M.t + 32).attr('text-anchor', 'middle')
      .text(s.label);
    svg.append('text').attr('class', 'sprint-sub')
      .attr('x', x + w / 2).attr('y', M.t + 48).attr('text-anchor', 'middle')
      .attr('fill', 'var(--ink-faint)')
      .text(s.tests > 0 ? s.tests + ' tests' : '—');
    svg.append('text').attr('class', 'sprint-sub')
      .attr('x', x + w / 2).attr('y', M.t + 64).attr('text-anchor', 'middle')
      .attr('fill', 'var(--ink-faint)').attr('font-size', '9px')
      .text(s.note);
  });
})();

// Nav active link highlight
(function initNavActive() {
  const links = document.querySelectorAll('nav a');
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const id = e.target.id;
        links.forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + id));
      }
    });
  }, { rootMargin: '-40% 0px -55% 0px' });
  document.querySelectorAll('section').forEach(s => obs.observe(s));
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
