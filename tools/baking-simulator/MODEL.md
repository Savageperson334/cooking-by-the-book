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


## 2.5D scene: scientific boundary (v0.4)

The angled oven viewport draws from computed time-series temperature, water, rise and browning signals, *not* from a 3D heat/flow model. Geometry is a fixed-footprint pan analogy; steam wisps, bubbles, cracks, grain, collapse and shine are deterministic artistic representations informed by composition and the existing uncalibrated rise proxy. This is deliberately **qualitative**, especially for nearly pure liquid, oil, crystals, very dry powders and high-salt mixtures. The numerical prediction does not include oil–water phase separation, sugar glass transitions, protein gel strength or fracture mechanics. Preserve warnings and avoid interpreting this view as evidence of texture or food safety.

References on physically grounded crust modelling: Purlis and Salvadori (2009), *Modelling the browning of bread during baking*, doi:10.1016/j.foodres.2009.03.007, and Chhanwal et al. (2014), temperature- and moisture-based modelling of starch gelatinization and crumb softness, doi:10.1111/jtxs.12097. The viewport is **not an implementation** of their published calibrated models.

## v0.7 — liquid-only open-pan branch (not a fluid dynamics simulation)

The previous 1D bread solver could produce impossible bulk water temperatures above normal boiling while substantial liquid water remained. Rather than masking that with a renderer-only patch, version 0.7 adds an explicitly separate numerical model in [`liquids.py`](liquids.py). The prior dough/batter model is preserved.

**Classification:** relatively pourable, starch-light recipes are assigned *aqueous*, *syrup*, *biphasic (added oil + water)*, or *oil* categories. Starch/protein-rich recipes remain in the bread solver, since setting/gelling invalidates a well-mixed liquid approximation. Classification is approximate; e.g. egg-rich custards require a future model. `liquid_mode` is exposed to the browser.

**Geometry:** Each ingredient's effective water/protein/fat/starch/sugar/fiber/ash masses are converted to additive volumes using approximate component densities. The *initial depth* control and initial volume imply a constant pan footprint area `A=V_initial / depth_initial`. As water leaves the open pan, the approximate volume and height become:

```text
water_g(t) = water_g(0) - cumulative_evaporation_g(t)
volume_mL(t) ≈ Σ(initial_component_g / component_density_g_per_mL)
               − cumulative_evaporation_g(t)/0.997
liquid_depth_mm(t) = initial_depth_mm × volume_mL(t)/initial_volume_mL
```

Those formulae imply **water alone can disappear**, **milk leaves a nonvolatile residue**, and **oil does not vanish merely because it gets hot**. These are additive *apparent* volumes: dissolved sugars can alter density/volume nonlinearly, and shrinking films, foams and pot geometry are omitted. Depth is meaningful for liquid-screening runs; this is not a 3D surface/flow solver.

**Thermal/evaporation balance:** A well-mixed sample exchanges heat with the nominal oven through effective exposed-face and pan-bottom coefficients (including linearized radiation). First-order sensible exchange is integrated with a bounded exponential update, and energy spent evaporating water is subtracted via a reference water latent heat. Free water temperature is bounded by an empirical ambient-pressure sugar/water boiling-point elevation curve; excess sensible energy at boiling consumes water instead. **Pure water is not permitted to reach 190°C while its liquid remains.** After a sample entirely disappears, the numerical temperature tracks the *oven as an empty-pan sentinel*, not a meaningful food temperature. Evaporation coefficients, pot heat transfer, skin resistance, atmospheric pressure, concentration effects, and syrup boiling temperature **have not been calibrated**. Low-pressure, vacuum, foam and vigorous convection are excluded.

**Phase and visual cues** (intentionally **not** fully physical):

- **Added olive oil:** its approximate remaining volume corresponds to a potentially floating layer above water. The time-dependent apparent separation fraction is a qualitative exponential cue and not a Stokes/emulsion model. Fat within milk/egg is not assumed to be free oil.
- **Milk:** an elevated-temperature, exposure-dependent *skin index* shades the surface when milk is present. This is **not** calculated whey protein denaturation, film thickness or wrinkling mechanics; stirring and lid conditions are unspecified.
- **Sugar:** sugar/(sugar+remaining_water) is a mass ratio, not a refractometer reading of °Brix. A provisional concentration-to-thickening cue and heat-tinted syrup colour appear in the viewport. Crystallization, fat/sugar glass transitions, viscosity and caramelization reaction kinetics remain unmodeled.
- **Colours:** weighted ingredient-colour approximations, adjusted for remaining water and the above qualitative cues. They are design illustration, **not** spectral mixture, optical scattering, colorimetry, or predicted final product appearance.

**Measurements to calibrate next:** pan footprint and starting depth, water mass before/after, measured liquid temperature through boiling, time-to-evaporate for 10/30/80 mm depths, oil layer thickness, skin formation versus stirring, and syrup concentration versus measured mass. Conduct individual controlled tests with food-safe dedicated equipment.

**Research relevant to the mechanisms, but not to the model coefficients:**

- [American Chemical Society — Density: Sink and Float for Liquids](https://www.acs.org/middleschoolchemistry/lessonplans/chapter3/lesson5.html) (oil/water stratification).
- [Wrinkling of milk skin is mediated by evaporation](https://pubmed.ncbi.nlm.nih.gov/28085169/) (2017), evidence for evaporative protein/fat interfacial films; **not** a calibrated skin-index source.
- [Molecular Gastronomy: A New Emerging Scientific Discipline](https://pmc.ncbi.nlm.nih.gov/articles/PMC2855180/) (2010), syrup water content/boiling point/viscosity/glass transition. Our numerical syrup exponent and colouring cue are **not** derived as validated fits from that paper.

**Safety:** Steam burns, concentrated syrup, and superheated oil can cause serious injury. This toy simulation does not tell you how long to heat foods safely or whether a pan of oil will smoke or ignite. The extremes are numerical stress cases, not recommended experiments.


## v0.8: suspended plant solids and thermal darkening (research model, uncalibrated)

In v0.7, high-water banana pulp and hydrated oats could enter a liquid branch but were depicted as liquid forever: the existing liquid browning state was primarily a sugar-syrup heuristic. v0.8 distinguishes a **suspension** when banana or oat mass contributes to a sufficiently water-rich, flour-light mixture. It keeps the v0.7 energy/mass calculation but tracks approximate nonvolatile dry ingredients (banana dry matter at 25%, oats at 91.5%, from the 20-ingredient catalogue) as water evaporates.

An **unvalidated bulk-state label** is derived from residual water/dry-matter ratio: *slurry*, *paste*, *dry residue* or *scorched*. The amount of dry matter is not reduced by decomposition or gas loss. A new monotone **thermal browning index** is accumulated using a temperature gate (centred at 129°C), a dryness gate (centred near a water/dry ratio of 0.66) and a substrate weighting for banana, oats, sugar and milk. The exact thresholds and kinetic coefficient were chosen to demonstrate state transitions and should be calibrated against photographed runs or published controlled studies. **This is not a validated Maillard or caramelization kinetic equation.** It does not predict oil smoking, flaming, carbon mass losses or toxic gases. Drying residue may physically char in reality, but simulated mass remains constant after water is gone.

For oats an additional heating-integral-based hydration index controls an estimated bound-water fraction; bound water remains part of total water and can still evaporate. The current solver assumes mixing and does not resolve swelling, suspended-particle sedimentation, surface crust formation, pan material or stirring.

**Relevant primary and technical sources:**

- Baini and Langrish (2009), *Assessment of colour development in dried bananas – measurements and implications for modelling*. [DOI 10.1016/j.jfoodeng.2009.01.012](https://doi.org/10.1016/j.jfoodeng.2009.01.012). Reports banana colour change during drying as a function of temperature and moisture; does **not** validate BakeLab's coefficients.
- Chen et al. (2025), *Insights into the mechanisms and regulatory strategies for aroma profiles and browning phenomena in banana puree processing*. [DOI 10.1016/j.foodchem.2025.143783](https://doi.org/10.1016/j.foodchem.2025.143783). Banana puree browning is real and multiple pathways contribute.
- Food and Agriculture Organization, [small- and medium-scale fruit-juice processing: Banana](https://www.fao.org/4/y2515e/y2515e17.htm). Processing browning and enzymatic inactivation context; not a thermal scorched-residue calibration.
- Guerrero, Alzamora and Gerschenson (1997), *Flow behaviour of processed banana purée*. [DOI 10.1177/108201329700300205](https://doi.org/10.1177/108201329700300205). Demonstrates non-Newtonian pseudoplastic, thixotropic banana purée behaviour absent in the model.

**Instruments needed to validate:** gravimetric evaporation curve, pan surface area, puree moisture content, pan vs sample thermocouples, calibrated photographs/spectrophotometer colour data, and if possible rheometry for banana/oats. Compare small changes in starting water and oven setpoint with repeated runs; do not infer precise browning times from this prototype.


## v0.9 upper-end audit: thermal decomposition, char and cracking

The old dry mass was **not a valid survival estimate** at oven temperatures as high as 600 °C: non-water mass was conserved by construction. The new `thermal_breakdown.py` is a *separate post-processing screening layer*. Each simulation timestamp carries `estimated_intact_organic_g`, `estimated_char_g`, `estimated_ash_g`, `estimated_remaining_mass_g`, `estimated_total_mass_loss_pct` and `crack_risk_index_pct`. The old water-only energy model and its `end_mass_g` remain unchanged; estimated mass can differ substantially. The UI deliberately labels which value is modeled and which is approximate.

The screening kinetic coefficients/thresholds are chosen to reproduce **directional** evidence and satisfy finite mass accounting; they have **not** been fitted to TGA curves for banana pulp, oat flakes, milk or your particular pan. A screen at 600 °C cannot establish an exact time to charring, failure or ignition. Oxygen distribution, gas release, char surface area, particle size, reaction heat, pan conduction, flames, lid/ventilation and aerosol generation are not resolved. Air access is a relative scalar sensitivity parameter, not a statement that 100% oxygen is present. Cracking is a tentative shrinkage+dryness+thermal-gradient risk index, not a calculated stress/strain failure criterion.

Primary/technical sources for physical context, **not coefficient validation**:

- Yang, Collins, Kumar, Bellmer, Bowser (2018), *Bioenergy from Food Wastes: Thermal Decomposition of Carbohydrates, Lipids, and Proteins*, Transactions of the ASABE 61(3):797–805, [DOI 10.13031/trans.12494](https://doi.org/10.13031/trans.12494). Devolatilization of representative food constituents extends toward 600 °C.
- P. Collard and A. Blin (2014), *A review on pyrolysis of biomass constituents: Mechanisms and composition of products obtained from the conversion of cellulose, hemicelluloses and lignin*, Renewable and Sustainable Energy Reviews 38:594–608. Plant fibre decomposition spans broad, overlapping temperature ranges.
- [Oxidative thermal decomposition of vegetable oils, PMC6827052](https://pmc.ncbi.nlm.nih.gov/articles/PMC6827052/), showing mass loss in multiple stages over roughly 200–600 °C in air.
- [Rigaku application note on degraded edible oil thermogravimetry](https://rigaku.com/products/thermal-analysis/sta/application-notes/b-ta1058-decomposition-behavior-edible-oils-effects-oxidative-degradation), showing different oil degradation history and 200–600 °C mass-loss stages.

For quantitative estimates, the future upgrade would require kinetic parameter fits from actual controlled TG/DTG under air *and* inert gas, separate pan/sample temperature data, ash yield characterization and an oxygen-access model. Never use the current simulator to choose ignition temperatures, oil heating safety limits or fire experiments.


## v0.9.1 — Physically cracked crust vs chemically cracked triglycerides

**Drying/physical fracture**: The mechanism is tensile stress caused by nonuniform shrinkage, constrained drying and thermal/moisture gradients, acting against material-specific tensile strength and fracture energy. BakeLab does **not** solve the stress/strain field. `physical_fracture.py` therefore produces only a bounded, composition- and drying-driven index, with two distinct sources: accumulated shrinkage drive and temperature/moisture-gradient drive. The displayed index is **not** the predicted probability of cracks. Its 50-point crossing time is not an experimentally meaningful fracture onset. It may peak then decline when the material has decomposed and no continuous structure remains. Pure water/oil and salt lack the modeled cohesive organic matrix; these are distinct from dry banana/oat or dough networks.

**Chemical thermal cracking**: An edible oil is chiefly triglycerides, **not** a pool of pure hydrocarbons. Thermal cleavage of fatty-acid chains and decomposition of the glycerol/ester moieties can form smaller hydrocarbon **and oxygenated** species. A separate high-temperature screening rate competes with bulk oil degradation. The mass ledger distinguishes initial fat, intact material, cumulatively cleaved triglyceride feedstock, a transient low-molecular material pool, released volatiles and char. The fractional split (62% immediate volatiles / 34% transient lighter fragments / 4% char in the cleavage pathway) is a bookkeeping assumption **not a validated oil product yield**. It must not be confused with GC-speciated gas or a reaction equilibrium. The model's 1% feedstock-conversion time is not a physical cracking threshold.

### Research grounding (NOT fitted coefficients)

- Palanisamy & Gevert (2016), [Study of non-catalytic thermal decomposition of triglyceride at hydroprocessing condition](https://doi.org/10.1016/j.applthermaleng.2016.06.167). Bench experiments 300–410°C: thermolysis above about 300°C and stronger cracking above about 350°C, forming mixed oxygenates and hydrocarbons. **Not an edible-pan onset calibration**.
- [RSC Catalysis Science & Technology review of vegetable oil cracking](https://doi.org/10.1039/C2CY20415K). Thermal cracking commonly studied around 350–500°C or higher; process pressure and products vary. **No one universal cracking point.**
- [Analysis of the failure of cracked biscuits](https://doi.org/10.1016/j.jfoodeng.2016.10.015) (2017). Moisture redistribution and local expansion/contraction generate stresses and fissures when strength limits are exceeded. Does **not** establish BakeLab's fracture index.

**Crucial limitations**: The upper-end module remains **one-way post-processing** of the original heat/water solution. Chemical reactions do not change the energy budget, sample temperature, geometry, oxygen diffusion, gas transport, reaction heats or material properties. At 600°C and long exposures the integrated mass percentages can look precise while being highly uncertain. The displayed risk index is not engineering stress and the molecular cracking estimate is not detailed pyrolysis, combustion, or a validated high-temperature kinetic calculation. No simulated ignition point, burning rate or hazardous-gas exposure should be inferred.
