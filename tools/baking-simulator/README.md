# Baking Simulator — design and science notebook

**Status:** concept / model specification, no solver implemented yet.

## Purpose

An interactive, browser-based tool for **experimenting with physical baking outcomes**, not merely recalculating recipes or generating arbitrary quality scores. Inputs include ingredient quantities, mixing/proofing preparation, dough geometry, baking time, oven temperature and environmental conditions. Outputs should follow a **coupled material model** and clearly disclose assumptions and uncertainty.

The tool belongs within Cooking by the Book as **one tool among many independent cooking experiments**. Do not architect the entire repository around it.

## Design principles

1. **Physical basis first.** Heat flow, moisture transport, evaporation, reactions and deformation should follow documented governing equations or carefully identified approximations. Do not silently turn slider values into subjective scores.
2. **State is not a single label.** Every spatial element may contain solid, liquid and gas simultaneously, together with local temperature, moisture, porosity and reaction progress.
3. **Coupled processes.** Composition affects thermophysical properties; temperature and moisture affect chemical transitions; transitions affect transport and mechanics.
4. **Start narrow, extend modularly.** Bread is the first material system, not a universal bread/cake/cookie model with invented coefficients.
5. **Provenance and calibration.** Record the exact reference behind equations and parameter values. Tag outputs as first-principles, literature-fit, experimentally calibrated, or illustrative.
6. **Preserve conservation.** Test mass and energy balances. Numerical stability and dimensional consistency come before presentation polish.
7. **Interpret predictions cautiously.** Simulations cannot alone establish microbiological safety, doneness, or dietary suitability.

## Proposed UI

Inputs:
- Flour mass/type (start with simple wheat assumptions), water/baker's hydration %, salt %, yeast %, optional fat/sugar %
- Initial dough temperature, proofing temperature/time (later)
- Dough shape **and dimensions** (mass alone is insufficient for thermal geometry)
- Oven setpoint, baking time, fan/heat transfer setting, optional steam/ambient humidity
- Material/property presets with advanced parameters visible on demand

Outputs, by confidence level:
- Time-series temperature and moisture at surface, mid-depth, and centre
- Cross-section animation / maps and movable time scrubber
- Estimated mass loss / evaporation and onset of crust drying
- Model-estimated starch gelatinization, browning and expansion only as corresponding submodels are implemented
- Overlay of two simulations and a measurement upload/CSV export for real trials
- Assumption and uncertainty panel; no unvalidated texture/flavour prediction score

## Mathematical architecture

**V0.1 — heat solver with geometry and boundary conditions**
- 1D spatial mesh, initially slab / radial bread models; explicit geometry and discretization.
- Conserve energy: rho * c_p * dT/dt = div(k * grad(T)) with conduction and effective oven boundary transfer (convection + radiation).
- Allow temperature-dependent thermophysical properties when source data exists.
- Verify convergence with time-step/mesh refinement; compare to known analytical cases.
- No claimed crust texture / doneness predictions in this version.

**V0.2 — moisture + evaporation**
- Add local liquid water, vapor fraction, evaporation/condensation and latent heat terms.
- Boundary water loss, gas exchange and effective moisture diffusion.
- Track food mass before/after and crust/crumb moisture differences.
- Validate against measured core temperature and mass loss from actual baking.

**V0.3 — microstructural chemistry**
- Starch gelatinization as temperature-, moisture- and time-dependent kinetic extent.
- Protein setting and water binding; surface Maillard/browning proxy with literature-supported calibration.
- Identify which chemistry is proven versus assumed. Chemistry must modify material properties where appropriate.

**V0.4 — proofing, bubbles, expansion**
- CO2 generation and gas retention; porosity, permeability and viscoelastic responses.
- Add moving mesh or an effective-volume approximation, separately validated.
- Avoid asserting deterministic crumb-bubble geometry without experimental support.

**Later — specialized ingredient/material plugins**
- Egg/dairy protein systems, sugar dissolution/crystallization, fat polymorphism, starches, emulsions, hydrogel/oleogel systems, cakes/cookies and food-specific geometries.
- New model families need their own literature-based parameters and validation; they are not just more recipe sliders.

## Technology

- Browser interface: HTML/CSS/JavaScript (or lightweight web components) for sliders, charts and maps.
- Scientific engine: Python + NumPy/SciPy using [Pyodide](https://pyodide.org/en/stable/) in a **Web Worker** for nonblocking calculation and static GitHub Pages deployment.
- The engine's input/output interface is JSON so it can also run under normal Python for batch validation and tests.
- Avoid introducing a backend until computation, data-management or collaboration requirements justify it.

## Reference starting points

- Zhang & Datta (2006), *Mathematical modeling of bread baking process*. DOI: [10.1016/j.jfoodeng.2005.03.058](https://doi.org/10.1016/j.jfoodeng.2005.03.058).
- Purlis & Salvadori (2009), *Bread baking as a moving boundary problem*, Parts 1 and 2: [10.1016/j.jfoodeng.2008.09.037](https://doi.org/10.1016/j.jfoodeng.2008.09.037), [10.1016/j.jfoodeng.2008.09.038](https://doi.org/10.1016/j.jfoodeng.2008.09.038).
- Purlis (2011), *Bread baking: Technological considerations based on process modelling and simulation*. [10.1016/j.jfoodeng.2010.10.003](https://doi.org/10.1016/j.jfoodeng.2010.10.003).
- *Study on Moisture Phase Changes in Bread Baking Using a Coupling Model* (2025): [PMC12071401](https://pmc.ncbi.nlm.nih.gov/articles/PMC12071401/).
- [Pyodide](https://pyodide.org/en/stable/) documentation.

## First implementation test

Change only **oven temperature, time and loaf thickness** while holding composition and initial temperature fixed. Confirm that changing thickness alters centre heating, that mesh refinement converges, and that setting the oven to the same temperature as the sample produces no spurious heating. Then compare to a measured loaf time/temperature trace.

**Next action when ready:** implement the V0.1 heat solver and a live browser UI, clearly labelled *heat-transfer demonstrator* rather than baking-quality predictor.
