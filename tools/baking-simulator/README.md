# BakeLab — experimental browser baking simulator

**Running prototype v0.2** in the [Cooking by the Book](../../README.md) experiment toolkit.

[Open browser app](index.html) · [Scientific methods and limitations](MODEL.md) · [Python engine](engine.py) · [20-ingredient catalogue](ingredients.json)

## What works today

- Responsive, dark-themed HTML interface with **20 ingredients**, individually adjustable in grams using sliders or precise numeric inputs.
- Bread, enriched dough, cake-like batter and intentionally absurd high-water, all-dry, high-salt and oil-rich presets.
- Sliders for **oven temperature, baking time, thickness, initial temperature, normalized steam level and fan, plus **proof duration and proof temperature**.
- **Real time-dependent Python calculations**, not static recipe lookup. Python is loaded through **Pyodide** in a browser Web Worker.
- A 1D **implicit finite-volume heat-flow solver** with approximate moisture diffusion, vapour loss and latent cooling; composition-dependent heat capacity/conductivity.
- Centre, mid-depth and surface temperature curves; moisture and mass-loss curves; **new CO₂ generation and effective rise estimates**; provisional chemical-transformation indices; timestamp scrubber through temperature cross-sections.
- Save and compare two scenarios (A/B) with fine-grained numerical differences. Export current run to JSON or time-series CSV.
- Warnings for out-of-range materials/geometry. Non-finite or negative ingredient values are rejected rather than silently accepted.

**Important:** this is a functional, exploratory *physics model*—not an empirically calibrated prediction of actual loaf rise, internal crumb structure, nutritional chemistry, flavour, or safe doneness. Yeast and baking powder now produce **modelled** CO₂, with a configurable proof stage, an empirical gas-retention factor, and a bounded rise proxy that changes the heat-transfer thickness. These kinetics and dimensional results are **not experimentally calibrated**. Baking soda without a specified acid reaction does not release modeled gas. All assumptions are in [MODEL.md](MODEL.md).

## Run locally

At the repository root:

```bash
python -m http.server 8000
```

Navigate to `http://localhost:8000/tools/baking-simulator/`. A normal HTTP server is needed because browser workers cannot load Python and JSON from a local `file://` URL. Internet access is needed initially to fetch the pinned Pyodide runtime from its CDN; calculations happen locally after loading.

Alternatively, host the repository as a static GitHub Pages site and visit `/tools/baking-simulator/` at the site URL.

## Run model without a browser

```bash
cd tools/baking-simulator
python -m unittest discover -s tests -v
```

The engine exports `simulate({"catalog": ingredients, "amounts": {"bread_flour":500, "water":340}, "settings": {"oven_c":220, "minutes":35, "thickness_mm":80}})`. It has **no scientific-package dependencies**. The ingredient catalogue is also used by the HTML app.

## Roadmap

1. Calibrate basic heat/moisture predictions with real baking trials and known geometries.
2. Introduce oven schedules and multi-zone geometries (pan / top / base, cylinder, sphere).
3. Calibrate the new gas-production, gas-retention and effective-thickness submodel against measured proofing and oven-rise traces; then introduce real viscoelastic material response.
4. Water activity, sugar dissolution, starch transformations and fat phase changes using better ingredient data.
5. Add cake, cookie, pastry, egg/dairy and plant-based gel **model families**, each with independent calibration.
6. Better optimizer / uncertainty bands and upload of actual thermometer and weight observations.

The project should remain a general *food experiments* toolkit, not define the scope of Cooking by the Book.

## New in v0.2

- Temperature- and time-dependent yeast CO₂ production during **proofing and initial baking**, affected by sugar, salt, and moisture proxies.
- Illustrative baking-powder gas release, limited by a fixed assumed CO₂ yield; **no baking-soda/acid reaction is claimed**.
- Gas retention and leakage approximation, plus thermal gas expansion and a bounded effective-volume estimate.
- The estimated volume changes sample **thickness in the fixed-footprint heat model**, so a larger simulated rise also changes the heating trajectory.
- Charts, A/B comparisons, and CSV exports now expose the gas and expansion signals.
- Current stable Pyodide is loaded in a **module web worker**, matching upstream documentation.
- 26 automated Python tests, including continuous parameter sensitivity and extreme mixtures.

**Interpretation:** These are directional/diagnostic model outputs for hypotheses. Rise percentages are not validated predictions of real loaf size. CO₂ venting is excluded from the water-only mass-loss balance, and a chemical-leavening proxy omits detailed acid chemistry. A truly physical baking model will need measured viscoelasticity, bubble transport, and calibration.
