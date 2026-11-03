# BakeLab — experimental browser baking simulator

**Running prototype v0.12.0** in the [Cooking by the Book](../../README.md) experiment toolkit.

[Open browser app](index.html) · [Scientific methods and limitations](MODEL.md) · [Python engine](engine.py) · [20-ingredient catalogue](ingredients.json)

## Mobile-first workspace (v0.9)

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

## Engineering review — priorities after Claude's boiling fix (v0.9.2)

Claude's [PR #1](https://github.com/Savageperson334/cooking-by-the-book/pull/1) fixed a concrete inconsistency: the 1D dough solver previously allowed liquid-bearing interior cells to become much hotter than water's approximate atmospheric boiling point. The new wet-cell boiling/evaporation cap improves physical consistency and extreme-oven mass loss. It does **not** yet make the loaf's heating curve quantitatively reliable: inward vapour migration and condensation (sometimes called an internal steam or heat-pipe effect) remain absent, and the centre can consequently warm far too slowly. Passing Python tests checks the implementation's contracts, **not** agreement with measured food temperatures.

Suggested investigation order (project notes, not rigid agent instructions):

1. **Resolve coupled heat/moisture transport first.** Examine vapour generation, migration, condensation and venting in a porous dough without double-counting water or latent energy. Test mass and energy balances; preserve the boiling constraint for wet regions. Compare the old conduction-only and proposed coupled model against representative centre/surface temperature traces.
2. **Establish experimental reference cases and calibration.** Start with simple, well-defined pan geometry, initial mass, thickness, ambient pressure and temperature, oven setpoint and measured centre/surface temperatures and mass loss versus time. Keep at least some trials unseen during parameter fitting, and report discrepancies and uncertainty rather than simply tuning until a visually convincing loaf appears.
3. **Couple upper-end reactions only when inputs justify it.** Current organic loss, triglyceride scission, char and ash calculations are screening post-processors: they do not feed reaction enthalpy, loss of material, evolving properties, oxygen availability or gas movement back into heat transfer. At 600°C they are useful for stress testing and qualitative ordering, **not** validated burn, smoke, ignition or residue predictions. Keep mechanical fissures separate from chemical chain scission.
4. **Advance deformation and the viewport after the thermal foundation.** A physical fracture model ultimately needs moisture-dependent material strength, shrinkage and stress/strain, adhesion and geometry. Until then, the animated pan should clearly label heuristic crust cracks, shrinkage, oil layers, colour and charring as illustrative.
5. **Add an actual browser integration test.** The repo's existing CI runs Python tests and static UI-contract checks; it does not prove a real Pyodide startup on a user's phone. Test a served build against the pinned runtime, a successful prediction, controls and common mobile widths, with a graceful offline/CDN failure.

Useful near-term acceptance evidence: a reproducible wet-cell energy/mass budget; measured-versus-predicted centre and surface traces for at least one known loaf and pan; regression cases for pure water, banana/oat slurry, bread and oil at normal and extreme temperatures; and a plainly stated confidence boundary for each prediction. Don't treat a green CI run or a more realistic-looking animation as scientific validation.

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
- 26 automated Python tests at the time (the suite has since grown; run it for the current count), including continuous parameter sensitivity and extreme mixtures.

**Interpretation:** These are directional/diagnostic model outputs for hypotheses. Rise percentages are not validated predictions of real loaf size. CO₂ venting is excluded from the water-only mass-loss balance, and a chemical-leavening proxy omits detailed acid chemistry. A truly physical baking model will need measured viscoelasticity, bubble transport, and calibration.

## v0.9.2 interface fix — unobstructed bake viewport

Simulation labels and the model warning no longer obscure the SVG food/pan. Oven temperature (°C/°F), effective thickness (mm) and rise proxy (%) appear in a compact readout row below the artwork; the warning is an expandable detail. On narrow phones the thickness badge is omitted from the pinned preview for space. This is a presentation-only correction; the calculated physics has not changed.

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

**Test coverage:** Python unit tests for water depletion, pan depth, heating, mass conservation, milk skin, oil separation, syrup concentration, tiny parameter differences and extreme inputs; plus static checks of the HTML/JS wiring (tabs, controls, worker setup). There are **no automated in-browser tests yet**; browser startup against the real Pyodide CDN still needs live verification on GitHub Pages.

## v0.9: water + banana / rolled oats, longer ranges, and °C/°F

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


## v0.9: verify the upper end (thermal breakdown / cracking)

At a 600 °C oven setting, **the original dry-solids balance was wrong if read as surviving food**: it kept all dry matter while only evaporating water. A separate, explicitly *uncalibrated* post-processing diagnostic now accumulates thermal exposure of sugar, starch, protein, fibre and fat using each frame's modeled material temperature and moisture. It partitions carbon-containing material into **remaining organics, devolatilized material, char, air-accessible char oxidation, and inorganic/mineral ash**. A **qualitative crack-risk index** responds to drying and thermal gradients but does **not** supply a single crack temperature or actual mechanical fracture prediction.

Important: the original energy/water equations are unchanged. The revised output is a **screening estimate shown separately** from original `end_mass_g`, which still includes all dry matter. Browser charts, pan viewport, and exports expose the estimate so high-heat experiments don't appear to leave intact sugar, oil or banana forever.

New process control: **Air access (relative)**, 0–100% in this model. This is a sensitivity proxy for char oxidation, **not oxygen percent, ventilation measurement or ignition probability**. 600 °C simulations must not be treated as food safety or fire guidance.

Reference discussion: [thermal model](MODEL.md).


## v0.9.1 — Two kinds of cracking, not one

**Physical cracks / fissures:** `physical_fracture.py` estimates an **uncalibrated risk index**, driven by drying shrinkage, moisture/temperature differences, and the presence of a fractureable starch/protein/sugar/fibre structure. It is not a tensile-stress, fracture-toughness or crack-length solver. A model threshold crossing is *not a physical crack point*; real fracture depends on adhesion, thickness, strain rate, geometry, temperature, moisture and strength. Cracks are visually drawn only when the physical screening index is elevated.

**Chemical thermal cracking:** `thermal_breakdown.py` estimates **fractional thermal cleavage of triglycerides**, particularly in oil-rich mixes. It competes with other oil degradation pathways and tracks a transient pool of lighter products, volatile loss and char. It is entirely separate from physical fractures or generic browning. Triglycerides are not pure hydrocarbons; their high-temperature breakdown can yield hydrocarbons **and** oxygenated compounds. No single molecular cracking temperature exists, and no individual molecule or exhaust gas composition is predicted.

The Results tab exposes the two independent curves and gram-based readouts. All chemical coefficients and fracture indices are *illustrative*, not fitted against measurements. See [MODEL.md](MODEL.md) for cited evidence and the limitations of 600°C simulations. Neither subsystem predicts safe use of hot oil, ignition or real flames.

**v0.9.2 integration:** Existing v0.9 public output keys are retained alongside the two new independent subsystems: total organic decomposition and total fat conversion (all routes), chemically cleaved triglycerides (subset), accumulated fracture damage and currently visible fissure risk. The food-temperature/time crossing of a *modelled* 10% fat conversion is a reporting convention, not a universal crack temperature.


### Distinct cracking-point indicators (screening only)

The Results card displays the first simulated *physical fracture-index 20/100 crossing* and the first *1%-of-fat triglyceride-scission crossing*, with corresponding estimated food temperatures in both °C and °F. The physical temperature is a surface estimate, while the fat-scission temperature is a representative computational-cell average. These are uncalibrated, threshold-dependent indicators **not measured failure/cracking temperatures, ignition temperatures, nor safety guidance**. Actual transitions depend on heating history, oxygen, moisture, composition, geometry and kinetics. The physical fracture model has no constitutive modulus or fracture toughness; lipid breakdown does not resolve chemical product distributions.


## v0.9.2 fixes — boiling ceiling for wet dough

- **Wet crumb no longer superheats.** Previously only the surface cell could lose water, so interior cells could reach 150 °C+ (or 500 °C at extreme settings) while still holding ~45% liquid water. Any dough cell that still contains water is now held near **100 °C**: excess heat boils that water off and the vapour is assumed to vent. Interior drying, mass loss and the high-heat breakdown stages now follow from that.
- **Centre heating is still slow.** The model remains conduction-only, without the internal steam "heat pipe" that warms real crumb; the default lean loaf reports a much cooler centre than a real loaf would reach. A warning now says so whenever the centre stays below 90 °C while the surface is above 100 °C.
- The browser worker now shows a readable message if the Pyodide runtime cannot be downloaded, and skips simulation requests that a newer slider change has already superseded.


## v0.9.3 — stale UI asset prevention

The prior pan-overlay fix was present in the deployed source but could remain invisible in a previously opened tab or cached browser assets. The HTML now references release-versioned JavaScript and CSS (`?ui=0.9.3`), and the JavaScript loads a correspondingly versioned Web Worker. This helps ensure that a newly opened page uses the matching interface revision rather than an older cached script. **Already-open tabs do not automatically update**; open [the versioned app URL](https://savageperson334.github.io/cooking-by-the-book/tools/baking-simulator/?ui=0.9.3) or reload once to switch builds. The scene labels and warnings remain outside the SVG, beneath the pan. This is a cache-consistency fix, not a change to the numerical baking model.


## v0.9.4 — browser-visible floating oval correction

The broad tan semicircle above the oven in browser screenshots was not food: the preview rendered a decorative SVG ellipse **and** a separate CSS radial gradient behind the oven frame. Both are now removed. Visual Chromium checks at 940 px and 1440 px reproduced the stray oval and verified it disappears when both layers are removed. The automated suite also asserts the two drawing paths stay removed. This changes presentation only, not the physics model or the pan/food geometry. JavaScript, CSS and worker URLs now include `?ui=0.9.4` to distinguish this release from cached prior files.


## Engine 0.10.0 — steam heat transport, checked against published loaves

The dough solver now includes an **evaporation–condensation ("heat pipe") term**: steam carries heat inward through the wet crumb, and the matching water moves with it. This was the main reason the centre heated far too slowly. The term has one parameter, fitted to one published loaf and then checked, unchanged, against a second published bake:

| | Measured | Before | Now |
|---|---|---|---|
| Round loaf (fit): centre at 97 °C | ~25 min | never (80 °C at 40 min) | 25 min |
| Round loaf: weight loss | 8.9 % | 10.1 % | 7.9 % |
| Thin layer (held out): centre > 93 °C | ~17 min | 23.8 min | 16.5 min |
| Thin layer: water lost | 15.0 g | 21.4 g | 20.7 g |

Crust still forms: outer layers dry and heat past 100 °C. The crumb also gains a little moisture, as in real loaves. Water loss on the thin glass-mould bake remains too high (see the [reference bakes](../../research/reference-bakes.md) note). The interface build (`?ui=0.9.4`) is unchanged; only the Python engine and its version tag changed.


## v0.11.0 — shapes and pans

The **Process** tab now has two new choices:

- **Shape:** flat slab, long cylinder (baguette) or ball (roll / boule). For the round shapes the depth slider is the diameter.
- **Pan / support** (slab only):
  - none, which is the old behaviour with both faces open
  - wire rack + baking paper
  - light aluminium sheet
  - dark steel pan
  - glass dish
  - preheated cast iron
  - preheated baking stone
  - preheated baking steel

A solid pan is solved as its own temperature. It heats from the oven according to its material and colour, then passes heat into the dough's bottom, which no longer loses water there. The Results tab then shows the bottom, pan and coldest-point temperatures and a separate bottom browning index. The cross-section runs bottom → top.

The pans rank as bakers would expect: preheated steel and stone heat the bottom fastest, then dark steel, then glass, with shiny aluminium slowest. Re-entering the two [reference bakes](../../research/reference-bakes.md) with their real supports refitted the steam term on the round loaf (rack). The held-out glass-dish bake's water loss now matches: 14.5 g against 15.0 g measured, where it was 20.7 g.

Python files and `ingredients.json` are now fetched with the same `?ui=` release tag as the page, so a new release never runs a cached older engine.


## v0.12.0 — altitude, drying, published browning rates and a friendlier app

**Physics**
- **Altitude** (Process tab, −500 to 5,000 m). Lower air pressure lowers the boiling point (95 °C at 1,500 m), caps crumb and liquids there, and lets gas expand more.
- **Drying** uses a measured bread-crust water-activity curve (Hamdami et al. 2006). The crust dries more slowly as it gets drier, as in real baking.
- **Browning** uses published bread-crust kinetics (Zanoni et al. 1995). It only starts above ~120 °C and below water activity ~0.6 (Purlis & Salvadori 2009), and it is driven by the crust's skin temperature, not the average of the outer 1–2 mm. Inside 180–220 °C, the whole-loaf colour change ΔE of Purlis & Salvadori (2007) is also shown.

**App**
- **New presets that also set the bake:** baguette (cylinder, steamed oven), soft dinner roll (ball), flatbread on a baking steel, focaccia in a dark pan, and the round loaf on a rack from the published test bake.
- **Baker's percentages** under the formula: hydration, salt, yeast, sugar and fat relative to flour.
- **Bake milestones** card on Results:
  - when the coldest point gets within 4 °C of boiling
  - when the crust starts to brown
  - final top and bottom browning, crust skin temperature and water loss
  - an illustrative crust-colour swatch
- **Preview drawing** follows the shape and support: a baguette on the rack, a bun-shaped roll, and a flat loaf on a stone, steel, sheet or paper. Only a deep pan is drawn as a pan.
- **Temperature chart** adds crust-skin and bottom lines.
- **Preview warning** shows only the run's most important problem. The general caveats stay under Results → Model boundaries.

