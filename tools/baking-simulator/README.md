# BakeLab — experimental browser baking simulator

**Running prototype v0.9** in the [Cooking by the Book](../../README.md) experiment toolkit.

[Open browser app](index.html) · [Scientific methods and limitations](MODEL.md) · [Python engine](engine.py) · [20-ingredient catalogue](ingredients.json)

## Mobile-first workspace (v0.8)

On a phone, four tabs—**Ingredients**, **Process**, **Results**, and **Compare**—sit above the **always-visible bake preview**. The preview remains pinned below the tab bar while you scroll long ingredient lists or process controls. Switching tabs does not reset the simulated scenario, playback, or A/B snapshots.

- **Ingredients:** choose recipe presets, adjust ingredients with sliders or precise gram inputs, see total mass, reset formula.
- **Process:** control proofing, time, temperature, thickness, oven conditions and fan.
- **Results:** inspect numerical predictions, charts, the heat cross-section, composition and model-limit warnings.
- **Compare:** save A/B predictions and export JSON/CSV.

The **Run prediction** button is attached to the preview so it is reachable from any tab; changing sliders also triggers recalculation. Play/pause and the simulation timeline remain next to the pan. On desktop, the preview stays beside the currently selected tab. v0.7 adds an explicit mobile right-edge **scroll gutter** (safe place to drag past ingredient sliders) and visible **g** units on ingredient number inputs. It also adds a dedicated open-pan liquid solver, so the physics branch *does* change for fluid-only formulations; dough uses its prior model.

## What works today

- Responsive, dark-themed HTML interface with **20 ingredients**, individually adjustable in grams using sliders or precise numeric inputs.
- Bread, enriched dough, cake-like batter and intentionally absurd high-water, all-dry, high-salt, oil-rich, pure-water, pure-oil and sugar-syrup presets.
- Sliders for **oven temperature, baking time, thickness, initial temperature, normalized steam level and fan, plus **proof duration and proof temperature**.
- **Real time-dependent Python calculations**, not static recipe lookup. Python is loaded through **Pyodide** in a browser Web Worker.
- A 1D **implicit finite-volume dough solver**, and a separate **well-mixed open-pan liquid energy/evaporation solver** for water, milk, syrup, oil and mixtures. Model details in [MODEL.md](MODEL.md).
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


## v0.7: open-pan liquids and material-aware visuals

**What's new:** pure water (blue transparent pool); milk and milk/water mixtures (creamy liquid and illustrative hot surface film); sugar syrup (concentration-dependent thickness/colour cues); olive oil and water (upper oil-layer cue); pure olive oil (does not evaporate as water). There are extra fluid presets for **only milk**, **milk + water** and **oil + water**. The sample-depth slider is interpreted as the **starting depth** for a liquid pan.

A fluid-only recipe now uses [`liquids.py`](liquids.py), a compact energy/evaporation model. Its **remaining water mass**, **total remaining mass**, **apparent volume** and **depth** update during the run and are exported to JSON/CSV. Change the chart selector to **Remaining pool depth (mm)** or **Liquid sugar concentration (%)**, and scrub the preview to see it recede. The depth readout appears below the visual pan and in the **Results** tab.

- This is **not CFD**. There is no splashing, turbulent boil, vortex flow, surface tension or validated film/rheology solver. The angled pan is an SVG illustration of the computed volume/depth and some uncalibrated visual cues.
- Dissolved sugar is treated using a non-ideal but rudimentary boiling-elevation approximation; crystal growth is not simulated. The displayed sugar fraction is **not measured Brix**.
- Milk skin is a visual indicator of plausible hot interface film formation, not an actual protein-network simulation.
- Added free oil may appear as a floating layer; its apparent separation time is assumed, not solved from droplet size, viscosity or mixing history.
- All pure-water simulations prevent liquid water being superheated far above its normal boiling temperature at atmospheric pressure. A completely empty pan reports a numeric oven-temperature sentinel, which **does not mean there is still material in the pan**.
- Mobile right-side **SCROLL ↓** rail lets you slide your thumb to scroll the long controls without changing ingredient amounts.

**Test coverage:** Python unit tests for water depletion, pan depth, heating, mass conservation, milk skin, oil separation, syrup concentration, tiny parameter differences and extreme inputs; plus browser-smoke tests against mocked solver responses across phone, tablet and desktop sizes. Browser startup against the real Pyodide CDN still needs live verification on GitHub Pages.

## v0.8: water + banana / rolled oats, longer ranges, and °C/°F

**Two new demo presets:** *Banana + water → scorched solids* (500 g water + 250 g mashed banana) and *Rolled oats + water → toasted residue* (600 g water + 200 g oats). These deliberately switch the **Process** tab to a 260°C oven, 240-minute run and 15-mm starting depth to reveal drying/browning stages. Ordinary presets still retain your existing process settings. You can scrub the preview from the beginning to the end to inspect slurry → paste → residue; the pan height follows the computed remaining mass rather than being kept full.

The new **suspension branch** in [`liquids.py`](liquids.py) is a well-mixed heat/water evaporation model augmented by *qualitative* moisture-driven state, oat hydration, and residue-browning indices. It is not a physically resolved pulp, porridge, or surface chemistry simulation. When enough liquid is lost, banana/oat/milk solids remain in the pan instead of evaporating along with the water. Pure water leaves an empty pan and must **not** brown. A concentrated milk or banana residue can darken after water evaporation, using a time-temperature-moisture-gated *screening index*. Don't interpret that number as experimentally predicted charring.

**Temperature units:** the Process tab displays both Celsius and Fahrenheit for each temperature field and offers a switch to make sliders operate in °C or °F. The Python solver's inputs and exported JSON are **always in °C**. Results show °C and °F; the temperature chart's vertical axis switches units. The app supports oven setpoints up to **600°C / 1112°F** and bake duration up to **1440 min / 24 h** for numerical stress-testing, **not** advice to use actual equipment at those extremes. Long, thin dough simulations may use coarsened time steps, with a warning.

**New charts and data:** oats hydration proxy, residue browning proxy, remaining-water and total-solid fractions, and CSV export fields. The dual-phase and milk/syrup functionality from v0.7 remains.

### Scientific cautions

- Volume uses additive component densities; real slurries, starch gels and sticky fruit reductions are neither ideal mixtures nor well-mixed during evaporation.
- The current solid residue temperature may approach the oven setpoint much faster than a real browned surface once there is little water left; the model is **not** a validated burn time, fire-risk, sensory, colour or food-safety prediction.
- Oat hydration is an uncalibrated heat-and-time surrogate. Individual oat particles, swelling kinetics, starch granule gelatinization and surface crust mechanics are not yet solved.
- The qualitative darkening curve is monotone and lacks oxidation kinetics, moisture-dependent nutrient chemistry, pyrolysis, ash formation, or real colourimetry.

For source literature and modelling gaps, see [MODEL.md](MODEL.md). Tests include extreme-duration/oven runs, pure water no-browning, banana and oat dry-down and small perturbations.

## v0.9: inspect the upper temperature end

The simulator now provides an **explicitly uncalibrated** high-temperature survival diagnostic. Rather than leaving every gram of solids in place forever after evaporation, it post-processes local temperature and moisture histories with composition-specific first-order surrogate rates for organic breakdown, volatile escape, transient char formation, and assumed ambient-air char oxidation. Mineral salts/ash remain as a separate conserved pool. As a qualitative check, a salt-dominant residue behaves differently from sugar, oats, banana and oil at 600°C. Crucially these surrogate rates are not a quantitative model of real pyrolysis, combustion or food safety.

New Results readouts and plots: estimated remaining total mass, intact organics, char, mineral/ash, thermal stage, and a **drying crack-risk index**. This index does not identify a true mechanical failure threshold; shrinkage stress, rheology and adhesion are still missing. The Process tab has an **Air access for char oxidation** control; it scales an illustrative oxidation rate only. It cannot predict ignition, smoke, fire or safe use in oxygen-limited conditions.

The pre-existing heat/moisture mass-loss values remain **water-only baseline outputs**, because the thermal-breakdown diagnostic is not yet fed back into heat transfer, sample geometry or evaporation. Read the independent `estimated_*` values as a stress-test overlay. At extreme temperatures the breakdown curves may be directionally plausible but cannot be trusted quantitatively.

Further reading: [ASABE 2018, Thermal Decomposition of Carbohydrates, Lipids, and Proteins](https://doi.org/10.13031/trans.12494); [Rigaku, edible oil thermal decomposition](https://rigaku.com/products/thermal-analysis/sta/application-notes/b-ta1058-decomposition-behavior-edible-oils-effects-oxidative-degradation); [NIST, sodium chloride melting point](https://srd.nist.gov/NSRDS/NSRDS-NBS61-II.pdf); [banana drying and crack stress](https://doi.org/10.1080/07373937.2023.2280912).

## Two kinds of cracking — high-temperature screening (v0.9)

**Physical fracture:** a normalized, *uncalibrated* drying-stress screening index combines surface/interior moisture mismatch, accumulated surface shrinkage, thermal gradients, gas expansion and composition-dependent cohesion. It records cumulative damage and an estimated **visible fissure** extent, then hides those fissures when little structure remains. Neither a true tensile-strength measurement nor a validated mechanical crack temperature; cooling/checking after baking is omitted.

**Chemical cracking/decomposition:** integrates illustrative time/temperature dependent loss of sugar, starch, protein, fiber and **fat (triglycerides)** into volatile material and possible char. Accessible char can further diminish through an oxidation proxy. The Results panel shows fat conversion and the first point at which **10% of the initial fat** has converted, with the modeled food temperature at that point; these are **not universal cracking, flash or ignition points**. No flames, combustion heat release, smoke chemistry or oxygen transport is simulated. The original water-only energy solutions are unchanged. The chemistry mass accounting is post-processing; no reaction enthalpy feedback is claimed.

At 600°C, reported oven temperature is not food temperature. Temperatures for liquid water remain near boiling while water is present; the matrix may become hotter after drying. All results in this extreme regime are qualitative research stress-tests, not safety guidance.
