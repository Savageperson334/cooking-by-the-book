# BakeLab 0.1 — Model specification and evidence

**Status:** Working numerical prototype. Physics-inspired *screening model*, not a validated food-quality or food-safety prediction system.

## Scope

- **20 controllable ingredients**, with an approximate water/protein/fat/starch/sugar/fibre/mineral composition table (`ingredients.json`). Ingredient fractions are approximate class-level starting points, **not verified batch-specific USDA measurements**. Real flours, eggs, honey etc. vary.
- **Adjustable:** oven setpoint −20–400 °C, heating time 0–300 minutes, 1D slab thickness 2–250 mm, starting temperature −20–100 °C, normalized oven water-vapour level 0–100%, still/forced air, ingredient amounts 0–100,000 g (large extremes outside confidence domain).
- **Time series:** surface, mid-depth and centre temperature; bulk mass lost to evaporation; center/surface water fractions; proxy indices for starch gelatinization, protein setting and surface browning.
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

**Important limits:** no internal steam-driven convective transport, no changing sample thickness, no oven preheating model, no thermal contraction/expansion, no vapor condensation within pores, no moisture-dependent spatial deformation, no actual sphere/cylinder geometry. Batch *mass* scales the output quantity and implied surface area at a fixed thickness; it does not by itself alter the 1D heat trajectory. A loaf's real shape, uncovered surfaces and pan contact matter greatly.

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

Model does not yet simulate leavening gas formation, proofing, yeast metabolism, baking powder CO₂, dough elasticity, bubble collapse, crumb morphology, fat polymorphism or enzymatic hydrolysis. A slider for yeast or baking powder influences mixture composition/thermal properties, **not yet a realistic rise estimate**. Baking soda affects the provisional browning index, but acid–base reaction and CO₂ production are not modeled. The first scientific extension should be calibrated fermentation and gas-retention kinetics, not a cosmetic “fluffiness score.”

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
