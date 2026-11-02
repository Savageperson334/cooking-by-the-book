# BakeLab 0.2 — Model specification and evidence

**Status:** Working numerical prototype. Physics-inspired *screening model*, not a validated food-quality or food-safety prediction system.

## Scope

- **20 controllable ingredients**, with an approximate water/protein/fat/starch/sugar/fibre/mineral composition table (`ingredients.json`). Ingredient fractions are approximate class-level starting points, **not verified batch-specific USDA measurements**. Real flours, eggs, honey etc. vary.
- **Adjustable:** oven setpoint −20–400 °C, heating time 0–300 minutes, 1D slab thickness 2–250 mm, starting temperature −20–100 °C, normalized oven water-vapour level 0–100%, still/forced air, ingredient amounts 0–100,000 g (large extremes outside confidence domain).
- **Time series:** surface, mid-depth and centre temperature; modelled gas generation, retention and effective slab expansion; bulk mass lost to evaporation; center/surface water fractions; proxy indices for starch gelatinization, protein setting and surface browning.
- **Spatial profiles:** time-resolved temperature and water fraction in an implicit finite-volume half-slab model; centre is insulated by symmetry, outside receives radiation + convection.
- **Composition:** mass-weighted heat capacity and component volume-weighted conductivity estimates based on Choi–Okos property equations as summarized in ASHRAE. Water heat capacity uses a constant approximation; calculations clamp component-property temperature to 0–180 °C, explicitly extrapolated otherwise.

## Heat-transfer calculation

For each cell of thickness Δx, with mass/area mᵢ and specific heat cᵢ:

```text
(mᵢ cᵢ / Δt) · (Tᵢ,new − Tᵢ,old) =
  Gᵢ · (Tᵢ₋₁,new − Tᵢ,new)
+ Gᵢ₊₁ · (Tᵢ₊₁,new − Tᵢ,new)
+ (surface-only) h_eff · (T_oven − T_surface,new)
− (surface-only) L_v · (evaporated mass/area)/Δt
```

Interface conductance `G = harmonic_mean(k_left, k_right)/Δx`. Radiation is linearized using `ε σ (T_o²+T_s²)(T_o+T_s)` and added to an adjustable forced-air / still-air convection coefficient. The implicit tridiagonal system is solved by Thomas elimination, avoiding explicit boundary instability at thin thicknesses.

**Important limits:** no internal steam-driven convective transport, the *only* geometry change is effective thickness from a pan-constrained gas proxy (not actual free-loaf deformation), no oven preheating model, no thermal contraction/expansion, no vapor condensation within pores, no moisture-dependent spatial deformation, no actual sphere/cylinder geometry. Batch *mass* scales the output quantity and implied surface area at a fixed thickness; it does not by itself alter the 1D heat trajectory. A loaf's real shape, uncovered surfaces and pan contact matter greatly.

## Moisture model

Interior water redistribution uses an effective diffusion term (order of magnitude `10⁻⁹–10⁻⁸ m²/s`, provisional), with conservative equal-and-opposite fluxes across adjacent cells. Surface moisture loss uses a provisional vapour-pressure driving force:

```text
ṁ_evap = C · max(0, a_w · p_sat(T_surface) − p_water,oven) · exposed-water-factor
```

where `C` is a lumped mass-transfer coefficient, water vapor pressure is capped near 1 atmosphere, and surface evaporation is capped by local water availability and a heat budget. Water activity is approximated by a simple dissolved-sugar/salt mole fraction; flour-bound water and sugar solubility are not resolved. The oven **steam % control is NOT relative humidity at oven temperature**; it is water vapour partial pressure relative to saturated water at 100 °C.

The solver conserves *its own* water mass (remaining + escaped), and latent heat is debited, but this is not a full multiphase bakery simulation. In extreme cases with effectively no material remaining, any subsequent grid temperature is meaningless and a warning is shown.

## Chemistry / morphology

Three indices are presented as **relative laboratory hypotheses**, not predictions of cooked texture or actual measured colour:

- Starch gelatinization proxy: water-gated sigmoidal temperature activation with first-order completion, only if flour is present.
- Protein thermal-setting proxy: sigmoidal temperature activation with first-order completion.
- Surface browning index: temperature-sensitive kinetic surrogate, modulated by local dryness, protein and sugar concentrations and a rough soda alkalinity effect.

The model now includes **illustrative yeast CO₂ and baking-powder CO₂ source terms**, an empirical bubble-retention factor and an effective-volume index that changes the thermal slab thickness. It does **not** simulate validated yeast metabolism, fluid elasticity, actual bubble pressure, bubble collapse, free-loaf deformation, crumb morphology, fat polymorphism or enzymatic hydrolysis. Baking soda affects the provisional browning index but its reaction with acid and CO₂ production are not modeled. These new submodels are exploratory: changing the yeast slider changes a calculated gas estimate, **not yet a validated rise prediction**.

## Model-source boundaries

### Literature that supports the *physical model family*

1. Zhang, J. & Datta, A.K. (2006). **Mathematical modeling of bread baking process.** *Journal of Food Engineering* 75, 78–89. [doi:10.1016/j.jfoodeng.2005.03.058](https://doi.org/10.1016/j.jfoodeng.2005.03.058). Coupled heat/moisture/deformation; our model is much simpler.
2. Purlis, E. & Salvadori, V.O. (2009). **Bread baking as a moving boundary problem.** Parts [1](https://doi.org/10.1016/j.jfoodeng.2008.09.037) and [2](https://doi.org/10.1016/j.jfoodeng.2008.09.038). Includes moving evaporation fronts and model validation; these effects are **not implemented here**.
3. Purlis, E. (2011). **Bread baking: Technological considerations based on process modelling and simulation.** *Journal of Food Engineering* 103, 92–102. [doi:10.1016/j.jfoodeng.2010.10.003](https://doi.org/10.1016/j.jfoodeng.2010.10.003). Coupled transport, starch and browning kinetics; our kinetic coefficients are not derived from its validated fits.
4. ASHRAE *Handbook—Refrigeration*, **Thermal Properties of Foods**, summary of Choi & Okos (1986). [Thermal-property equations](https://handbook.ashrae.org/Handbooks/R18/SI/r18_ch19/r18_ch19_si.aspx). This directly informs component heat capacities and conductivity approximations.
5. [USDA FoodData Central](https://fdc.nal.usda.gov/download-datasets/) is a recommended future source for provenance-tracked ingredient compositions; catalogue entries are currently rough archetypes.

### Reusable tools investigated

- [Pyodide](https://pyodide.org/en/stable/usage/quickstart.html): actual **CPython** running inside an HTML page via WebAssembly; selected to run the same `engine.py` in-browser and in tests. The main UI stays responsive using a Web Worker.
- NumPy/SciPy: potential future optimized sparse solvers and parameter fitting, but not necessary yet. The initial solver uses the Python standard library for low dependencies and easy testing.
- COMSOL/FEniCS/FiPy: useful references for future multi-physics/moving-mesh modelling, not integrated here; copying a research paper's claims without its parameters would be misleading.

## Validation plan

1. **Numerical verification:** temperature remains finite, mass is conserved, a warmer oven warms the sample faster, thinner samples heat faster, tiny parameter changes yield smooth output. `python -m unittest discover -s tests -v`.
2. **Parameter sensitivity:** run controlled one-variable changes for temperature, baking time, loaf depth, hydration, fat and sugar. Keep snapshots in the HTML comparison view and export the run JSON/CSV.
3. **Real bake calibration:** use a known flour type, constant thickness/geometry, oven thermocouple, centre thermocouple and mass before/after. Record cross-sections if possible. Calibrate effective boundary heat and evaporation parameters before adding claims about accuracy.
4. **Confidence envelopes:** fit and validate on withheld trials, publish experimental RMSEs and interval estimates. Only after this should the UI state numeric prediction accuracy.

## Safety

Results do not determine doneness, safe heating schedules, pathogen destruction or allergen safety. Subzero freezing, pyrolysis/charring and very high sugar/fat phase transitions are outside the solver. Chemical-lab centrifuge samples must never be considered edible.

## v0.2 gas-source and effective-volume extension

### Yeast activity and proofing

A continuous, bounded yeast activity curve peaks near 33°C and decreases above ~49°C. The rate also depends on a **parametric, uncalibrated** suppression by salt and concentrated sugar and a wetness gate. A finite carbohydrate budget limits total gas production; a separate proofing stage evaluates the model at a specified proof temperature and duration.

The numerical CO₂ rate prefactor **0.0045 g CO₂/(g instant yeast·minute)** is a demonstration parameter, **not a measured strain-specific fit or published constant**. Literature supports the *qualitative* roles of yeast amount, temperature, substrate, and gas retention; our quantitative mapping needs direct measurement.

### Baking powder and retention

A provisional baking-powder gas yield of 0.12 g CO₂ per gram baking powder is released at temperature-dependent rates. Brands with different double-acting acid compositions can behave quite differently. Sodium bicarbonate is not separately counted without knowing the acid balance.

The model converts retained gas moles into an estimated volume using the ideal gas equation at atmospheric pressure. It includes an approximate initial entrained-air fraction, smooth wetness/gluten/fat retention heuristics and temperature-dependent leakage. This **omits internal pressure, dissolved CO₂ and viscoelastic resistance** and caps volume at 3.5× the model's reference volume.

### Coupling to heat and limitations

The initial full slab thickness is interpreted **before proof**. The first-stage experimental assumption is a fixed planar footprint (like pan-confined material), so the predicted volume ratio changes slab thickness and therefore cell spacing in the implicit conductive heat solver. Mass and moisture inventories remain conserved **per projected area** for the heat/water transport calculation.

The separate gas submodel **does not subtract vented CO₂ mass** from the displayed product mass: the mass-loss chart represents evaporated water only. In reality fermentation also transforms sugar into ethanol and other by-products. The present model is not a complete mass/energy-conserving reacting multiphase solver. At high rise, weak matrices, very high temperatures, or mostly liquid/oil mixtures, interpret expansion only as a sensitivity signal, not geometry.

### Evidence motivating the model family (not its coefficients)

- Fan, Mitchell & Blanshard (1999), [A model for the oven rise of dough during baking](https://doi.org/10.1016/S0260-8774(99)00070-9): gas generation, vapor partition and setting constrain oven rise.
- [Proving of Bread Dough II: Measurement of Gas Production and Retention](https://doi.org/10.1205/096030803322437974) (2003): measurements support strong dependence on yeast concentration and proof temperature.
- [Description of leavening of bread dough with mathematical modelling](https://doi.org/10.1016/j.jfoodeng.2007.02.014) (2007): stresses distinction between production and retention.
- Zhang, Datta & Mukherjee (2005), [Transport processes and large deformation during baking of bread](https://doi.org/10.1002/aic.10518): full multiphase transport + viscoelastic deformation is a significantly more complex, experimentally validated target.

## Browser compatibility note

Pyodide v314.0.7 requires **module** web workers rather than classic `importScripts()`. Version 0.2 uses an ES module import. JavaScript syntax and Python tests passed, but the full browser startup still requires an interactive network-enabled browser integration test.
