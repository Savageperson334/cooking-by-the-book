# BakeLab — experimental browser baking simulator

**Running prototype v0.5** in the [Cooking by the Book](../../README.md) experiment toolkit.

[Open browser app](index.html) · [Scientific methods and limitations](MODEL.md) · [Python engine](engine.py) · [20-ingredient catalogue](ingredients.json)

## Mobile-first workspace (v0.5)

On a phone, four tabs—**Ingredients**, **Process**, **Results**, and **Compare**—sit above the **always-visible bake preview**. The preview remains pinned below the tab bar while you scroll long ingredient lists or process controls. Switching tabs does not reset the simulated scenario, playback, or A/B snapshots.

- **Ingredients:** choose recipe presets, adjust ingredients with sliders or precise gram inputs, see total mass, reset formula.
- **Process:** control proofing, time, temperature, thickness, oven conditions and fan.
- **Results:** inspect numerical predictions, charts, the heat cross-section, composition and model-limit warnings.
- **Compare:** save A/B predictions and export JSON/CSV.

The **Run prediction** button is attached to the preview so it is reachable from any tab; changing sliders also triggers recalculation. Play/pause and the simulation timeline remain next to the pan. On desktop, the preview stays beside the currently selected tab. This is a UI-only release; the physics solver and its validation limits are unchanged.

## What works today

- Responsive, dark-themed HTML interface with **20 ingredients**, individually adjustable in grams using sliders or precise numeric inputs.
- Bread, enriched dough, cake-like batter and intentionally absurd high-water, all-dry, high-salt, oil-rich, pure-water, pure-oil and sugar-syrup presets.
- Sliders for **oven temperature, baking time, thickness, initial temperature, normalized steam level and fan, plus **proof duration and proof temperature**.
- **Real time-dependent Python calculations**, not static recipe lookup. Python is loaded through **Pyodide** in a browser Web Worker.
- A 1D **implicit finite-volume heat-flow solver** with approximate moisture diffusion, vapour loss and latent cooling; composition-dependent heat capacity/conductivity.
- Centre, mid-depth and surface temperature curves; moisture and mass-loss curves; **new CO₂ generation and effective rise estimates**; provisional chemical-transformation indices; timestamp scrubber through temperature cross-sections.
- An animated **Bake viewport**: a stylized oven/pan scene that changes with the simulated state (rise, browning, surface moisture, collapse tendency and warnings) while still exposing absurd or out-of-domain formulations.
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

## Bake viewport v0.4

The oven/pan scene is an SVG **2.5D angled illustration** whose state is recomputed from the Python time series. Use **Replay bake**, **Pause**, 0.5–4× playback, the scene timeline, or the temperature cross-section timeline; both are synchronized. This is not a rendered 3D physics simulation.

The illustration uses the current model's rise/thickness proxy, surface temperature, moisture loss, browning and composition to choose textures/colours and distinguish liquid, dry powder, high salt/sugar and nearly pure oil. For unrealistic compositions the viewport explicitly says *unsupported*: it never assumes that every ingredient mixture turns into a loaf. Granules, cracking, bubbling, steaming and the shape of the pan fill are **qualitative interpretations**, not measured or predicted internal microstructure.

The remaining numerical solver is unchanged from v0.2. Rigorous visual prediction needs measured rheology, phase separation, a 3D geometry and a surface-colour calibration dataset.
