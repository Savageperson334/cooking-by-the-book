"""Cooking by the Book: experimental 1D, composition-aware baking solver.

A bounded, finite-volume *screening model*, NOT a validated doneness predictor.
Thermal component heat capacities/conductivities use Choi-Okos-style mixing;
water redistribution, vapor escape and chemistry are explicit approximations.
Python stdlib only, to run identically in CPython and Pyodide.
"""
from __future__ import annotations

import json
import math
from typing import Any

VERSION = "0.13.1"
from liquids import liquid_kind, simulate_liquid
from thermal_breakdown import annotate_high_heat
from physical_fracture import annotate_fracture
from geometry import PANS, SHAPES, ROOM_C, build_grid, solid_pan_conductances, exponent as geometry_exponent
COMPONENTS = ("water", "protein", "fat", "starch", "sugar", "fiber", "ash")
SIGMA = 5.670374419e-8  # W / (m² K⁴)
LV = 2.26e6  # J / kg, reference latent heat of water
WATER_CP = 4180.0  # J/(kg K)
EC_DIFFUSIVITY = 4.4e-5  # m2/s effective vapour diffusivity; FITTED to one loaf, see evaporation_condensation_k
BOIL_C = 100.0  # liquid-water ceiling inside wet crumb at ~1 atm (°C)
R_GAS = 8.314462618  # J/(mol K)
CO2_G_MOL = 44.0095
P_ATM = 101325.0


def bounded(x: float, low: float, high: float) -> float:
    return max(low, min(high, x))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-bounded(x, -50.0, 50.0)))


def physical_properties(composition: dict, temperature: float) -> tuple[float, float]:
    """Specific heat [J kg-1 K-1] and conductivity [W m-1 K-1].

    Components weighted by mass for cp; conductivity via volume approximation.
    Choi-Okos (1986) polynomials from ASHRAE Handbook, evaluated in °C.
    Extrapolation is explicitly guarded above 180 °C and below 0 °C.
    """
    t = bounded(temperature, 0.0, 180.0)
    c = composition
    cps = {
        "water": 4180.0,
        "protein": 1000 * (2.0082 + 0.0012089*t - 0.0000013129*t*t),
        "fat": 1000 * (1.9842 + 0.0014733*t - 0.0000048008*t*t),
        "starch": 1000 * (1.5488 + 0.0019625*t - 0.0000059399*t*t),
        "sugar": 1000 * (1.5488 + 0.0019625*t - 0.0000059399*t*t),
        "fiber": 1000 * (1.8459 + 0.0018306*t - 0.0000046509*t*t),
        "ash": 1000 * (1.0926 + 0.0018899*t - 0.0000036817*t*t),
    }
    ks = {
        "water": 0.571 + 0.0015 * bounded(t, 0, 90),
        "protein": 0.17881 + 0.0011958*t - 0.0000027178*t*t,
        "fat": 0.18071 - 0.00027604*t - 0.00000017749*t*t,
        "starch": 0.20141 + 0.0013874*t - 0.0000043312*t*t,
        "sugar": 0.20141 + 0.0013874*t - 0.0000043312*t*t,
        "fiber": 0.18331 + 0.0012497*t - 0.0000031683*t*t,
        "ash": 0.32962 + 0.0014011*t - 0.0000029069*t*t,
    }
    rhos = {"water": 998.0, "protein": 1329.9, "fat": 925.6, "starch": 1599.1,
            "sugar": 1599.1, "fiber": 1311.5, "ash": 2423.8}
    cp = sum(c[k] * cps[k] for k in COMPONENTS)
    volumes = [c[k] / rhos[k] for k in COMPONENTS]
    v = sum(volumes)
    k = sum((volumes[i] / v) * ks[k] for i, k in enumerate(COMPONENTS)) if v else 0.2
    return max(cp, 900.0), bounded(k, 0.08, 0.7)


_RHO = {"water": 998.0, "protein": 1329.9, "fat": 925.6, "starch": 1599.1,
        "sugar": 1599.1, "fiber": 1311.5, "ash": 2423.8}


def property_function(dry_comp: dict):
    """Fast equivalent of physical_properties for a fixed dry composition.

    Returns f(water_fraction, temperature) -> (cp, k), identical to calling
    physical_properties with {water: w, other: (1-w)*dry_comp[other]}.
    """
    solids = [k for k in COMPONENTS if k != "water"]
    dc = [dry_comp[k] for k in solids]
    dv = [dry_comp[k] / _RHO[k] for k in solids]  # dry volume per kg dry solids
    dry_vol = sum(dv)
    def f(w: float, temperature: float) -> tuple[float, float]:
        t = bounded(temperature, 0.0, 180.0)
        tt = t * t
        cps = (1000 * (2.0082 + 0.0012089*t - 0.0000013129*tt),
               1000 * (1.9842 + 0.0014733*t - 0.0000048008*tt),
               1000 * (1.5488 + 0.0019625*t - 0.0000059399*tt),
               1000 * (1.5488 + 0.0019625*t - 0.0000059399*tt),
               1000 * (1.8459 + 0.0018306*t - 0.0000046509*tt),
               1000 * (1.0926 + 0.0018899*t - 0.0000036817*tt))
        ks = (0.17881 + 0.0011958*t - 0.0000027178*tt,
              0.18071 - 0.00027604*t - 0.00000017749*tt,
              0.20141 + 0.0013874*t - 0.0000043312*tt,
              0.20141 + 0.0013874*t - 0.0000043312*tt,
              0.18331 + 0.0012497*t - 0.0000031683*tt,
              0.32962 + 0.0014011*t - 0.0000029069*tt)
        d = 1.0 - w
        cp = w * 4180.0 + d * (dc[0]*cps[0] + dc[1]*cps[1] + dc[2]*cps[2] + dc[3]*cps[3] + dc[4]*cps[4] + dc[5]*cps[5])
        vw = w / 998.0
        v = vw + d * dry_vol
        if v:
            kw = 0.571 + 0.0015 * bounded(t, 0, 90)
            k = (vw * kw + d * (dv[0]*ks[0] + dv[1]*ks[1] + dv[2]*ks[2] + dv[3]*ks[3] + dv[4]*ks[4] + dv[5]*ks[5])) / v
        else:
            k = 0.2
        return max(cp, 900.0), bounded(k, 0.08, 0.7)
    return f


def _vapor_pressure(temp_c: float, boil_c: float = 100.0, pressure_pa: float = 101325.0) -> float:
    """Antoine correlation for water from 1 °C to the boiling point, capped at ambient pressure."""
    t = bounded(temp_c, 1.0, boil_c)
    return min(pressure_pa, 133.322368 * 10 ** (8.07131 - 1730.63 / (233.426 + t)))


def _vapour_density(temp_c: float) -> float:
    """Saturated water-vapour density [kg m-3] (ideal gas, Antoine pressure)."""
    return 0.018015 * _vapor_pressure(temp_c, 150.0, 1e9) / (R_GAS * (temp_c + 273.15))


def pressure_at_altitude(altitude_m: float) -> float:
    """International Standard Atmosphere pressure [Pa] (troposphere)."""
    return 101325.0 * (1.0 - 2.25577e-5 * altitude_m) ** 5.25588


def boiling_point_c(pressure_pa: float) -> float:
    """Water boiling point [°C] from the inverted Antoine equation."""
    return 1730.63 / (8.07131 - math.log10(pressure_pa / 133.322368)) - 233.426


# Bread-crust desorption isotherm (GAB) at 25 °C: Hamdami, Monteau & Le Bail
# (2006) Int. J. Food Sci. Tech. 41:33-44, Table 2. Xm in kg water / kg dry.
GAB_XM, GAB_C, GAB_K = 0.0778, 34.09, 0.81


def crust_water_activity(water_frac: float) -> float:
    """Water activity of a bread matrix at a given wet-basis water fraction.

    Inverts the GAB isotherm X = Xm*C*K*aw / ((1-K*aw)(1-K*aw+C*K*aw)).
    Parameters were measured at 25 °C; at baking temperatures a given
    moisture gives a somewhat higher aw, so this is an approximation.
    """
    w = bounded(water_frac, 0.0, 0.999)
    x = w / (1.0 - w)
    if x <= 0.0:
        return 0.0
    a = x * (GAB_C - 1.0)
    b = -(x * (GAB_C - 2.0) - GAB_XM * GAB_C)
    c = -x
    u = (-b + math.sqrt(b*b - 4*a*c)) / (2*a)  # u = K*aw
    return bounded(u / GAB_K, 0.0, 1.0)


# Bread-crust browning rate: Arrhenius constants from Zanoni, Peri & Bruno
# (1995) LWT 28:604-609, as tabulated by Purlis (2010) J. Food Eng. 99:239-249.
BROWN_K0 = 42000.0     # s-1
BROWN_EA = 64151.0     # J mol-1
# Purlis & Salvadori (2009) Food Res. Int. 42:865-870: colour formation needs
# surface temperature > ~120 °C and water activity < ~0.6.
BROWN_MIN_C, BROWN_MAX_AW = 120.0, 0.6


def browning_rate(temp_c: float, aw: float) -> float:
    """First-order crust-colour rate [s-1], gated by the start conditions."""
    if temp_c < BROWN_MIN_C - 25.0 or aw > BROWN_MAX_AW + 0.25:
        return 0.0
    gate = sigmoid((temp_c - BROWN_MIN_C) / 4.0) * sigmoid((BROWN_MAX_AW - aw) / 0.04)
    return BROWN_K0 * math.exp(-BROWN_EA / (R_GAS * (temp_c + 273.15))) * gate


def evaporation_condensation_k(temp_c: float, water_frac: float, boil_c: float = 100.0) -> float:
    """Apparent conductivity [W m-1 K-1] from the evaporation-condensation 'heat pipe'.

    Water evaporates on the warm side of each gas cell, diffuses across it and
    condenses on the cooler side, carrying latent heat. This is represented as
    k_ec = D_eff * L_v * d(rho_sat)/dT (de Vries-type equivalent property),
    switched off in cells that have dried out. The solver also relocates the
    matching water (q_ec / L_v) from the warm cell to the cool one, so the
    latent heat is counted once (in the conductance) and water is conserved.
    D_eff is a single effective vapour diffusivity fitted to ONE published
    loaf (Papasidero et al. 2015, see reference_bakes.json); not a measured
    property of any particular dough.
    """
    if water_frac <= 0.01:
        return 0.0
    t = bounded(temp_c, 1.0, boil_c - 0.5)
    slope = (_vapour_density(t + 0.5) - _vapour_density(t - 0.5))  # per 1 K
    g = bounded((water_frac - 0.01) / 0.05, 0.0, 1.0)  # exactly off below 1 % water
    wet_gate = g * g * (3.0 - 2.0 * g)
    return EC_DIFFUSIVITY * LV * slope * wet_gate


def composition_of(catalog: list[dict], amounts: dict[str, float]) -> dict[str, Any]:
    by_id = {x["id"]: x for x in catalog}
    unknown = [key for key in amounts if key not in by_id]
    if unknown:
        raise ValueError("Unknown ingredient: " + ", ".join(unknown))
    total = 0.0
    comp = {name: 0.0 for name in COMPONENTS}
    for key, raw in amounts.items():
        mass = float(raw)
        if not math.isfinite(mass) or mass < 0 or mass > 100000:
            raise ValueError(f"Bad mass for {key}; use finite nonnegative grams <= 100000")
        if mass == 0:
            continue
        total += mass
        item = by_id[key]
        for name in COMPONENTS:
            comp[name] += mass * float(item.get(name, 0))
        residue = 1.0 - sum(float(item.get(name, 0)) for name in COMPONENTS)
        if residue > 0:
            comp["starch"] += mass * residue  # approximate uncharacterized solids
    if total <= 0:
        raise ValueError("At least one ingredient must have nonzero mass")
    comp = {k: v / total for k, v in comp.items()}
    comp["ash"] += max(0.0, 1.0 - sum(comp.values()))
    flour_mass = sum(amounts.get(x, 0.0) for x in ("bread_flour", "ap_flour", "whole_wheat", "rye_flour"))
    wheat_mass = sum(amounts.get(x, 0.0) for x in ("bread_flour", "ap_flour", "whole_wheat"))
    gluten = (sum(float(amounts.get(x, 0.0)) * by_id[x]["protein"] * by_id[x].get("gluten", 0.0)
                  for x in by_id) / total)
    return {"total_g": total, "fraction": comp, "flour_g": flour_mass,
            "wheat_flour_g": wheat_mass, "gluten_fraction": gluten,
            "salt_g": amounts.get("salt", 0.0), "yeast_g": amounts.get("instant_yeast", 0.0),
            "baking_powder_g": amounts.get("baking_powder", 0.0),
            "baking_soda_g": amounts.get("baking_soda", 0.0), "cocoa_g": amounts.get("cocoa", 0.0),
            "milk_g": amounts.get("milk", 0.0), "free_oil_g": amounts.get("olive_oil", 0.0),
            "banana_g": amounts.get("banana", 0.0), "oats_g": amounts.get("oats", 0.0)}




def ferment_activity(temp_c: float) -> float:
    """Bounded *illustrative* dry-yeast activity curve, not a validated strain fit."""
    return (math.exp(-((temp_c-33.0)/21.0)**2)
            * sigmoid((49.0-temp_c)/2.4) * sigmoid((temp_c-0.0)/4.0))

def gas_retention_factor(recipe: dict) -> float:
    """Empirical screening proxy for ability to retain bubbles in wheat matrices.

    Not a gluten rheology/viscoelastic model; intentionally collapses toward
    low retention for fluid, dry or non-wheat formulations.
    """
    c = recipe["fraction"]
    gluten = sigmoid((recipe["gluten_fraction"]-0.035)/0.018)
    wet_gate = sigmoid((c["water"]-0.23)/0.055) * sigmoid((0.70-c["water"])/0.09)
    return bounded(0.025 + 0.84*gluten*wet_gate/(1+1.2*c["fat"]), 0.025, 0.88)

def fermentation_rate(recipe: dict, temperature: float) -> float:
    """Potential yeast CO2 generation [g/min], before substrate exhaustion.

    Parametric hypothesis informed by known thermal and salt/sugar dependence;
    the 0.0045 g CO2/(g instant yeast min) prefactor is NOT literature-calibrated.
    """
    yeast = recipe["yeast_g"]
    if yeast <= 0:
        return 0.0
    c = recipe["fraction"]
    f = max(recipe["flour_g"], 1.0)
    sugar_per_flour = c["sugar"] * recipe["total_g"] / f
    salt_per_flour = recipe["salt_g"] / f
    osmotic = 1.0 / (1 + max(0.0,sugar_per_flour-0.10)**2/0.12**2)
    saline = 1.0 / (1 + (salt_per_flour/0.07)**2)
    water_gate = sigmoid((c["water"]-0.18)/0.045)
    return 0.0045 * yeast * ferment_activity(temperature) * osmotic * saline * water_gate

def validate_run(recipe: dict, settings: dict) -> tuple[dict, list[str]]:
    limits = {"oven_c": (-20, 600), "minutes": (0, 1440), "thickness_mm": (2, 250),
              "initial_c": (-20, 100), "steam_pct": (0, 100), "fan": (0, 1),
              "proof_minutes": (0, 720), "proof_c": (-10, 55), "air_access_pct": (0,100),
              "altitude_m": (-500, 9000)}
    cfg = {}
    for key, (lo, hi) in limits.items():
        val = float(settings.get(key, {"oven_c": 220, "minutes": 35, "thickness_mm": 80,
                                       "initial_c": 22, "steam_pct": 5, "fan": 0,
                                       "proof_minutes": 0, "proof_c": 25, "air_access_pct":100,
                                       "altitude_m": 0}[key]))
        if not math.isfinite(val) or not lo <= val <= hi:
            raise ValueError(f"{key}: expected a finite value in [{lo}, {hi}]")
        cfg[key] = val
    cfg["pressure_pa"] = round(pressure_at_altitude(cfg["altitude_m"]), 1)
    cfg["boil_c"] = round(boiling_point_c(cfg["pressure_pa"]), 3)
    cfg["shape"] = str(settings.get("shape", "slab"))
    cfg["pan"] = str(settings.get("pan", "none"))
    if cfg["shape"] not in SHAPES:
        raise ValueError("shape: expected one of " + ", ".join(SHAPES))
    if cfg["pan"] not in PANS:
        raise ValueError("pan: expected one of " + ", ".join(PANS))
    w = []
    c = recipe["fraction"]
    f = recipe["flour_g"]
    if f < 1:
        w.append("No flour: the heat/moisture solver still runs, but bread-specific transitions do not apply.")
    if c["water"] < 0.15:
        w.append("Extremely dry composition: moisture/gelatinization assumptions are outside typical doughs.")
    if c["water"] > 0.80:
        w.append("Mostly liquid: this is not a mechanically stable bread dough model.")
    if c["fat"] > 0.25:
        w.append("Very high fat: phase separation and fat crystallization are not modeled yet.")
    if c["sugar"] > 0.25:
        w.append("High sugar: glass transition, caramelization and dissolved-sugar effects are under-modeled.")
    if f > 0 and recipe["salt_g"] / f > 0.05:
        w.append("Salt exceeds 5% of flour; fermentation and texture may fall far outside calibrated bread ranges.")
    if f > 0 and recipe["yeast_g"] / f > 0.04:
        w.append("Yeast exceeds 4% of flour; no validated fermentation kinetics at this ratio.")
    if recipe["baking_soda_g"] > 0.02 * recipe["total_g"]:
        w.append("Excess baking soda: acid-base chemistry and flavour are not simulated.")
    if cfg["oven_c"] < 0 or cfg["initial_c"] < 0:
        w.append("Sub-zero conditions: freezing, latent heat of fusion and frozen-water transport are not modeled.")
    if cfg["oven_c"] < 120 or cfg["oven_c"] > 300:
        w.append("Oven temperature is outside conventional bread-baking calibration ranges; fire and material decomposition are not modeled.")
    if cfg["thickness_mm"] < 10 or cfg["thickness_mm"] > 140:
        w.append("Unusual thickness: effective 1D geometry and surface coefficients are uncertain.")
    if cfg["minutes"] > 120:
        w.append("Long heating: dry-residue darkening is heuristic; char chemistry, fire and structural collapse are NOT simulated.")
    if cfg["proof_minutes"] > 0 and cfg["proof_c"] > 45:
        w.append("Proofing above 45°C: yeast activity and survival are uncertain; no kill-time history is modeled.")
    if recipe["baking_powder_g"] > 0:
        w.append("Baking-powder CO2 yield and temperature release are approximate; brand chemistry varies.")
    if recipe["baking_soda_g"] > 0:
        w.append("Baking soda gas requires acid or a reaction path; baking soda is NOT counted as a gas source here.")
    if cfg["altitude_m"] > 3000:
        w.append("High altitude: boiling point and gas expansion follow the standard atmosphere; recipe adjustments bakers make at altitude are not modelled.")
    if recipe["total_g"] > 5000:
        w.append("Very large batch; actual geometry matters more than bulk mass.")
    return cfg, w


# Most decision-relevant first. The first warning matching a pattern earlier
# in this list becomes the headline the app shows next to the preview.
HEADLINE_PRIORITY = (
    "Almost no mass remains", "Liquid water exhausted", "Extreme oven setting",
    "Pure oil", "Gas model hit its", "Mostly liquid", "Extremely dry",
    "At very high temperatures", "Very high oven temperature", "Coldest point ended below",
    "High altitude", "Salt exceeds", "Yeast exceeds", "Excess baking soda",
    "Pan/support contact is only modelled",
)


GENERIC_CAVEATS = ("Expansion uses uncalibrated", "Screening model", "Liquid branch:",
                   "Pan area is inferred", "Upper-end decomposition", "Physical fracture:",
                   "Baking-powder CO2 yield", "Pan/support:")


def headline_warning(warnings: list[str]) -> str | None:
    """The single most decision-relevant warning, or None if only the
    standing model caveats apply (those are always listed in full)."""
    for pattern in HEADLINE_PRIORITY:
        for w in warnings:
            if w.startswith(pattern):
                return w
    specific = [w for w in warnings if not w.startswith(GENERIC_CAVEATS)]
    return specific[0] if specific else None


def simulate(payload: dict) -> dict:
    result = _simulate(payload)
    result["summary"]["headline_warning"] = headline_warning(result["warnings"])
    return result


def _simulate(payload: dict) -> dict:
    catalog = payload["catalog"]
    amounts = payload["amounts"]
    recipe = composition_of(catalog, amounts)
    cfg, warnings = validate_run(recipe, payload.get("settings", {}))
    kind = liquid_kind(recipe)
    if kind != "solid":
        return annotate_fracture(annotate_high_heat(simulate_liquid(recipe, cfg, warnings, kind, VERSION),recipe),recipe)
    frac = recipe["fraction"]
    mass_kg = recipe["total_g"] / 1000.0
    shape = cfg["shape"]
    pan = PANS[cfg["pan"]]
    radial = shape != "slab"
    if radial and pan["kind"] != "symmetric":
        warnings.append("Pan/support contact is only modelled for the flat slab shape; this round shape is heated evenly from all sides.")
        pan = PANS["none"]
    symmetric = pan["kind"] == "symmetric"
    p_exp = geometry_exponent(shape)
    n_half = int(bounded(round(cfg["thickness_mm"] / 3.5), 4, 26))
    # Symmetric shapes solve centre -> surface. A slab whose bottom differs
    # from its top is solved bottom -> top over its full thickness.
    n = n_half if symmetric else min(2 * n_half, 36)  # cap keeps extreme runs fast
    span = cfg["thickness_mm"] / 2000.0 if symmetric else cfg["thickness_mm"] / 1000.0
    vols, areas = build_grid(shape, span, n)
    dx = span / n
    initial_w = frac["water"]
    dry_comp = {k: (frac[k] / (1.0-initial_w)) if initial_w < 1 else 0.0 for k in COMPONENTS if k != "water"}
    props = property_function(dry_comp)
    density = 920.0  # effective dough density (kg m-3); approximate, held fixed
    dry = [(1 - initial_w) * density * v for v in vols]  # kg per unit measure
    wet = [initial_w * density * v for v in vols]
    total_vol = sum(vols)
    weights = [v / total_vol for v in vols]  # mass fraction of each cell
    temps = [cfg["initial_c"] for _ in range(n)]
    gel = [0.0 for _ in range(n)]
    protein = [0.0 for _ in range(n)]
    dry_total = sum(dry)
    original_total = dry_total + sum(wet)
    evaporated = 0.0
    surface_brown = 0.0
    bottom_brown = 0.0
    pan_c = None
    if pan["kind"] == "solid":
        pan_c = cfg["oven_c"] if pan["preheated"] else ROOM_C
    # Ideal-solute water-activity proxy (assumes dissolved sugar and salt).
    # Real flour-bound water, phase separation and solubility are not captured.
    n_water = max(0.0, frac["water"] / 0.018015)
    n_solute = frac["sugar"] / 0.34230 + 1.8*recipe["salt_g"]/max(recipe["total_g"],1e-9)/0.05844
    water_activity_proxy = n_water/(n_water+n_solute) if n_water+n_solute else 0.0
    # Gas expansion changes the shape's size: slab thickness on a fixed
    # footprint, cylinder radius at fixed length, sphere radius. Mass per
    # cell is unchanged. NOT a free-loaf mechanics calculation.
    retention = gas_retention_factor(recipe)
    base_matrix_v = mass_kg / 1250.0  # assumed zero-porosity matrix density
    entrained_fraction = 0.015 + 0.085*retention
    entrained_air_v = base_matrix_v * entrained_fraction / (1-entrained_fraction)
    v_reference = base_matrix_v + entrained_air_v
    p_amb = cfg["pressure_pa"]
    boil_c = cfg["boil_c"]
    n_air = p_amb * entrained_air_v / (R_GAS * (cfg["initial_c"]+273.15))
    substrate_limit_g = 0.48*(frac["sugar"] * recipe["total_g"] + 0.045*recipe["flour_g"])
    co2_generated_g = 0.0
    n_co2 = 0.0
    if cfg["proof_minutes"] > 0:
        potential_g = fermentation_rate(recipe, cfg["proof_c"]) * cfg["proof_minutes"]
        produced_g = min(substrate_limit_g, potential_g)
        co2_generated_g += produced_g
        n_co2 = (produced_g / CO2_G_MOL) * retention * math.exp(-cfg["proof_minutes"] * (1-retention) / 1600.0)
    powder_co2_remaining_g = recipe["baking_powder_g"] * 0.12
    def desired_volume_factor(temperature: float) -> float:
        gas_v = (n_air+n_co2) * R_GAS * (max(-20.0,temperature)+273.15) / p_amb
        return (base_matrix_v + gas_v) / v_reference
    def linear_factor(vf: float) -> float:
        return vf ** (1.0 / (1 + p_exp))
    volume_factor = bounded(desired_volume_factor(cfg["initial_c"]),0.5,3.5)
    proof_rise_pct = (volume_factor-1.0)*100.0
    max_volume_factor = volume_factor
    volume_cap_hit = False
    # Fermentation and baking-powder gas are screening submodels. Their source
    # chemistry and CO2 venting mass are omitted from the water-only mass balance.
    total_s = cfg["minutes"] * 60.0
    # explicit heat + moisture stability bound, including extreme thickness
    cp0, k0 = physical_properties(frac, cfg["initial_c"])
    alpha = k0 / (density * cp0)
    dt_stable = 0.75 * dx * dx / max(alpha, 2e-8)
    dt = min(5.0, max(0.25, dt_stable))
    steps = max(1, math.ceil(total_s / dt)) if total_s > 0 else 0
    if steps > 40000:
        steps = 40000
        warnings.append("Numerical time step was coarsened for a very long/thin scenario; check discretization sensitivity before interpreting results.")
    dt = total_s / steps if steps else 0.0
    stride = max(1, steps // 100)
    timeline = []
    heat_transfer = 16.0 + 13.0 * cfg["fan"]  # convective W m-2 K-1 heuristic
    p_air = cfg["steam_pct"] / 100.0 * 101325.0
    bottom_open = pan["kind"] == "open"
    evap_scale_bottom = pan.get("evap_scale", 0.0)
    heat_scale_bottom = pan.get("heat_scale", 1.0)
    # Index of the cell treated as "centre" for reporting.
    centre_i = 0 if symmetric else n // 2
    mid_i = n // 2 if symmetric else (3 * n) // 4

    def centre_temp() -> float:
        if symmetric or n % 2:
            return temps[centre_i]
        return 0.5 * (temps[n//2 - 1] + temps[n//2])

    def record(second):
        moisture = [wet[i] / (wet[i]+dry[i]) if wet[i]+dry[i] else 0.0 for i in range(n)]
        frame = {
            "minute": round(second / 60, 4),
            "center_c": round(centre_temp(), 3),
            "surface_c": round(temps[-1], 3),
            "mid_c": round(temps[mid_i], 3),
            "coldest_c": round(min(temps), 3),
            "mass_loss_pct": round(100 * evaporated / original_total, 4),
            "surface_moisture_pct": round(100 * moisture[-1], 3),
            "center_moisture_pct": round(100 * moisture[centre_i], 3),
            "starch_progress_pct": round(100 * sum(g*w for g, w in zip(gel, weights)), 2),
            "protein_progress_pct": round(100 * sum(p*w for p, w in zip(protein, weights)), 2),
            "temp_profile": [round(t, 2) for t in temps],
            "water_profile": [round(x*100, 2) for x in moisture],
            "browning_index": round(100 * (1.0 - math.exp(-surface_brown)), 2),
            "crust_surface_c": round(top_face_c, 3),
            "rise_pct": round((volume_factor-1.0)*100.0, 3),
            "thickness_mm_est": round(cfg["thickness_mm"]*linear_factor(volume_factor), 3),
            "co2_generated_g": round(co2_generated_g, 4),
            "co2_retained_g": round(n_co2*CO2_G_MOL, 4),
        }
        if not symmetric:
            frame["bottom_c"] = round(temps[0], 3)
            frame["bottom_browning_index"] = round(100 * (1.0 - math.exp(-bottom_brown)), 2)
            frame["bottom_face_c"] = round(bottom_face_c, 3)
            if pan_c is not None:
                frame["pan_c"] = round(pan_c, 3)
        timeline.append(frame)

    def surface_evaporation(i: int, area: float, h_area: float, neighbour_g: float, scale: float) -> float:
        """Water [kg per measure] leaving cell i through an exposed face this step."""
        p_sat = _vapor_pressure(temps[i], boil_c, p_amb)
        aw = water_activity_proxy * crust_water_activity(wet[i] / max(dry[i] + wet[i], 1e-12))
        vapor_flux = 1.5e-8 * max(0.0, aw*p_sat - p_air) * scale
        nb = i + 1 if i == 0 else i - 1
        available_rate = max(0.0, h_area*(cfg["oven_c"]-temps[i]) + neighbour_g*(temps[nb]-temps[i]))
        return min(wet[i], vapor_flux * area * dt,
                   (available_rate*dt + 0.01*max(0.0,temps[i]-20)*cps[i]) / LV)

    # Reactant availability relative to a lean flour-water-salt bread, the kind
    # of dough the browning constants were measured on. Not calibrated.
    def substrate_factor(sugar, protein):
        return bounded((sugar+0.006)/0.03, 0.1, 4.0) * bounded((protein+0.015)/0.12, 0.2, 2.0)
    substrate_rel = substrate_factor(frac["sugar"], frac["protein"]) / substrate_factor(0.0075, 0.08)
    soda_effect = 1 + 0.8 * bounded(recipe["baking_soda_g"]/max(recipe["total_g"],1e-8) / 0.012, 0, 2)

    top_face_c = bottom_face_c = cfg["initial_c"]
    record(0.0)
    for step in range(steps):
        s_lin = linear_factor(volume_factor)
        dx_current = dx * s_lin
        area_now = [a * s_lin**p_exp for a in areas]
        # composition and properties are recomputed from each cell's retained water
        cps, ks, kecs = [], [], []
        porosity_factor = 0.75 + 0.15 * min(1.0, recipe["gluten_fraction"] / 0.10)
        for i in range(n):
            water_frac = wet[i] / max(wet[i]+dry[i], 1e-12)
            cp, k = props(water_frac, temps[i])
            # gas pores and crumb structure lower effective conduction; provisional
            cps.append((dry[i] + wet[i]) * cp)  # J/(measure K)
            kecs.append(evaporation_condensation_k(temps[i], water_frac, boil_c))
            ks.append(k * porosity_factor + kecs[-1])

        # Linearized radiative+convective boundaries; implicit Euler heat flow.
        oven_k = cfg["oven_c"] + 273.15
        def h_rad_unit(t_c):
            t_k = t_c + 273.15
            return SIGMA * (oven_k**2 + t_k**2) * (oven_k + t_k)
        h_top = (heat_transfer + 0.86 * h_rad_unit(temps[-1])) * area_now[n]
        face = [0.0] * (n + 1)  # dough-internal conductances; face[0]/face[n] are boundaries
        for j in range(1, n):
            face[j] = area_now[j] * (2*ks[j-1]*ks[j] / max(ks[j-1]+ks[j], 1e-12)) / dx_current
        face[n] = h_top
        h_bottom = 0.0
        pan_under = pan_contact = pan_cap = 0.0
        if bottom_open:
            h_bottom = (heat_transfer + 0.86 * h_rad_unit(temps[0])) * heat_scale_bottom * area_now[0]
            face[0] = h_bottom
        elif pan_c is not None:
            under, contact, capacity = solid_pan_conductances(pan, 0.8 * heat_transfer, h_rad_unit(pan_c))
            pan_under, pan_contact, pan_cap = under * area_now[0], contact * area_now[0], capacity * area_now[0]
            face[0] = pan_contact
        # Vapour escaping through exposed faces, bounded by the heat supplied.
        vapor_top = surface_evaporation(n-1, area_now[n], h_top, face[n-1], 1.0)
        wet[-1] -= vapor_top
        evaporated += vapor_top
        vapor_bottom = 0.0
        if bottom_open and evap_scale_bottom > 0:
            vapor_bottom = surface_evaporation(0, area_now[0], h_bottom, face[1], evap_scale_bottom)
            wet[0] -= vapor_bottom
            evaporated += vapor_bottom

        # Assemble the tridiagonal system. With a solid pan, node 0 is the pan.
        off = 1 if pan_c is not None else 0
        N = n + off
        caps = ([pan_cap] if off else []) + cps
        old = ([pan_c] if off else []) + temps
        cond = [0.0] * (N + 1)  # cond[m] couples node m-1 and node m; cond[0]/cond[N] link to the oven
        if off:
            cond[0] = pan_under
            cond[1] = pan_contact
            for j in range(1, n):
                cond[j+1] = face[j]
        else:
            cond[0] = face[0]  # 0 for symmetric centre, h_bottom for an open bottom
            for j in range(1, n):
                cond[j] = face[j]
        cond[N] = h_top
        lower = [0.0] * N
        diag = [0.0] * N
        upper = [0.0] * N
        right = [0.0] * N
        inv_dt = 1.0 / max(dt, 1e-12)
        for m in range(N):
            d = caps[m] * inv_dt
            lo, hi = cond[m], cond[m+1]
            diag[m] = d + lo + hi
            lower[m] = -lo if m > 0 else 0.0
            upper[m] = -hi if m < N-1 else 0.0
            right[m] = d * old[m]
        right[0] += cond[0] * cfg["oven_c"]
        right[-1] += h_top * cfg["oven_c"] - vapor_top*LV*inv_dt
        if bottom_open:
            right[0] -= vapor_bottom*LV*inv_dt
        for m in range(1, N):
            factor = lower[m]/diag[m-1]
            diag[m] -= factor * upper[m-1]
            right[m] -= factor * right[m-1]
        solved = [0.0]*N
        solved[-1] = right[-1]/diag[-1]
        for m in range(N-2, -1, -1):
            solved[m] = (right[m]-upper[m]*solved[m+1])/diag[m]
        if off:
            pan_c = solved[0]
        temps = solved[off:]
        # Temperature of the actual outer skin (the face), not the outer cell's
        # average: what browns is the surface itself. From the flux balance
        # h*(T_oven - T_face) = G_half*(T_face - T_cell).
        g_top = ks[-1] * area_now[n] / (0.5 * dx_current)
        top_face_c = (h_top*cfg["oven_c"] + g_top*temps[-1]) / (h_top + g_top)
        if not symmetric:
            g_bot = ks[0] * area_now[0] / (0.5 * dx_current)
            if pan_c is not None:
                bottom_face_c = (pan_contact*pan_c + g_bot*temps[0]) / (pan_contact + g_bot)
            else:
                bottom_face_c = (h_bottom*cfg["oven_c"] + g_bot*temps[0]) / (h_bottom + g_bot)
        # The heat-pipe share of each face's heat flow is carried by water that
        # evaporated on the warm side and condensed on the cool side, so move
        # that water (q_ec * dt / L_v) as well. Energy is already accounted for
        # by the conductance; this keeps the warm side drying and lets the
        # crumb gain some moisture, as observed in real loaves.
        moved = [0.0] * n
        for j in (range(1, n) if any(kecs) else ()):
            k_mean = 0.5 * (ks[j-1] + ks[j])
            if k_mean <= 0.0:
                continue
            q_ec = face[j] * (temps[j] - temps[j-1]) * 0.5 * (kecs[j-1] + kecs[j]) / k_mean
            mass = q_ec * dt / LV  # >0: from cell j to j-1
            src = j if mass > 0 else j-1
            mass = math.copysign(min(abs(mass), 0.5 * max(0.0, wet[src])), mass)
            moved[j] -= mass
            moved[j-1] += mass
        if any(moved):
            wet = [max(0.0, wet[i] + moved[i]) for i in range(n)]
        # Wet crumb cannot hold liquid water far above its boiling point. Any
        # sensible heat above BOIL_C in a cell that still has water is spent
        # boiling that water off; the vapour is assumed to vent.
        for i in range(n):
            if wet[i] > 0.0 and temps[i] > boil_c:
                boiled = min(wet[i], (temps[i]-boil_c) * cps[i] / LV)
                wet[i] -= boiled
                evaporated += boiled
                temps[i] -= boiled * LV / cps[i]
        # moisture diffusion; conservative and controlled by local temperature
        dm = [0.0] * n
        for j in range(1, n):
            D = (1e-9 + 7e-9 * sigmoid((0.5*(temps[j]+temps[j-1])-75)/15))
            conc_j = wet[j] / vols[j]
            conc_i = wet[j-1] / vols[j-1]
            flux = D * areas[j] * (conc_j - conc_i) / dx  # undeformed grid; per measure
            amount = bounded(flux * dt / max(s_lin * s_lin, 1e-9), -max(0.0, wet[j-1]*0.3), max(0.0, wet[j]*0.3))
            dm[j] -= amount
            dm[j-1] += amount
        wet = [max(0.0, wet[i] + dm[i]) for i in range(n)]
        # CO2 sources, finite carbohydrate budget and effective bubble retention.
        # The mass-weighted mean approximates yeast temperature; no cell-by-cell
        # dissolved CO2 diffusion, rheology or explicit internal gas pressure.
        bulk_temp = sum(t*w for t, w in zip(temps, weights))
        substrate_left = max(0.0, substrate_limit_g-co2_generated_g)
        ferment_g = min(substrate_left, fermentation_rate(recipe, bulk_temp)*dt/60.0)
        co2_generated_g += ferment_g
        n_co2 += ferment_g / CO2_G_MOL * retention
        if powder_co2_remaining_g > 0:
            # Empirical release over tens of seconds as batter heats; not a
            # manufacturer-specific double-acting powder dissolution model.
            triggered = sigmoid((bulk_temp-53.0)/8.0)
            powder_release_g = powder_co2_remaining_g * (1-math.exp(-dt*triggered/100.0))
            powder_co2_remaining_g -= powder_release_g
            co2_generated_g += powder_release_g
            n_co2 += powder_release_g / CO2_G_MOL * retention
        # Leakage increases in weak dough, and as the heated crumb becomes
        # increasingly open; dimensions are phenomenological, not calibrated.
        leak_rate = (0.00004*(1-retention) +
                     0.0007*sigmoid((bulk_temp-93.0)/6.0)*(1.0-retention*0.5))
        n_co2 *= math.exp(-leak_rate*dt)
        # A setting matrix resists further rise.
        target = desired_volume_factor(bulk_temp)
        if target > 3.5: volume_cap_hit = True
        target = bounded(target,0.5,3.5)
        gel_mean = sum(g*w for g, w in zip(gel, weights))
        set_gate = sigmoid((bulk_temp-84.0)/6.0) * (0.25 + 0.75*gel_mean)
        response = (1.0-set_gate) * (1-math.exp(-dt/25.0))
        volume_factor += (target-volume_factor)*response
        volume_factor = bounded(volume_factor,0.5,3.5)
        max_volume_factor = max(max_volume_factor, volume_factor)
        # phenomenological kinetic indices; not a measurement of doneness
        if recipe["flour_g"] > 0:
            for i in range(n):
                wlocal = wet[i] / max(wet[i]+dry[i], 1e-12)
                water_gate = sigmoid((wlocal - 0.16) / 0.035)
                g_rate = 0.0025 * sigmoid((temps[i] - 66.0)/5.5) * water_gate
                gel[i] += (1.0-gel[i]) * (1.0 - math.exp(-g_rate * dt))
                p_rate = 0.0018 * sigmoid((temps[i]-74)/8)
                protein[i] += (1.0-protein[i]) * (1.0 - math.exp(-p_rate*dt))
        # browning *indices*, not colorimetrically calibrated
        if recipe["flour_g"] > 0 or frac["protein"] > 0.03:
            def brown_rate(i, face_c):
                w_i = wet[i] / max(wet[i]+dry[i], 1e-12)
                aw_i = water_activity_proxy * crust_water_activity(w_i)
                return browning_rate(face_c, aw_i) * substrate_rel * soda_effect
            surface_brown += brown_rate(n-1, top_face_c) * dt
            if not symmetric:
                bottom_brown += brown_rate(0, bottom_face_c) * dt
        if (step+1) % stride == 0 or step == steps-1:
            record((step+1)*dt)
    moisture_profile = [100*wet[i]/(wet[i]+dry[i]) if wet[i]+dry[i] else 0 for i in range(n)]
    mass_loss = evaporated/original_total * 100
    if volume_cap_hit:
        warnings.append("Gas model hit its 3.5× volume cap; the predicted volume is NOT credible for this recipe.")
    warnings.append("Expansion uses uncalibrated CO2 generation, retention, and size coupling; not a free-loaf or cake-structure prediction.")
    if recipe["flour_g"] < 1:
        warnings.append("Starch and protein transition indices are disabled without flour; use the temperature and moisture traces only.")
    if sum(wet)+dry_total < 0.01*original_total:
        warnings.append("Almost no mass remains: the calculated temperature belongs to an empty computational grid and is not a material prediction.")
    if recipe["flour_g"] > 0 and cfg["minutes"] > 0 and min(temps) < boil_c - 10.0:
        warnings.append(f"Coldest point ended below {boil_c - 10.0:.0f} °C. Internal steam heat transport is one effective term fitted to a single published loaf (about ±2–3 min on an unseen bake); treat centre timing as approximate, not as doneness.")
    if pan["kind"] in ("open", "solid"):
        warnings.append("Pan/support: material properties are handbook values, but dough-pan contact and rack/paper shielding are assumptions; side walls of a tin are not modelled.")
    if cfg["oven_c"] > 280:
        warnings.append("At very high temperatures, pyrolysis, fire hazards and chemical decomposition are outside this model.")
    warnings.append(f"Screening model: 1D {shape}, simplified evaporation and reaction indices. Not validated for food safety or exact doneness.")
    if symmetric:
        axis = "centre_to_surface"
        position = [round(100*i/(n-1),2) for i in range(n)]
        exposure = [0.15+0.85*(i/(n-1))**1.3 for i in range(n)]
    else:
        axis = "bottom_to_top"
        position = [round(100*i/(n-1),2) for i in range(n)]
        # Top half: interior (0.15) to fully exposed top face (1.0). Bottom half:
        # interior to a partly shielded (rack) or pan-covered bottom face.
        bottom_face = 0.5 if bottom_open else 0.15
        exposure = []
        for i in range(n):
            u = abs(2*i/(n-1) - 1) ** 1.3  # 0 in the middle, 1 at either face
            exposure.append(0.15 + (0.85 if i >= n/2 else bottom_face - 0.15) * u)
    summary = {"total_g": round(recipe["total_g"], 3),
               "water_pct": round(frac["water"]*100, 3),
               "fiber_pct": round(frac["fiber"]*100, 3),
               "aw_proxy": round(water_activity_proxy, 4),
               "ash_pct": round(frac["ash"]*100, 3),
               "fat_pct": round(frac["fat"]*100, 3),
               "sugar_pct": round(frac["sugar"]*100, 3),
               "starch_pct": round(frac["starch"]*100, 3),
               "protein_pct": round(frac["protein"]*100, 3),
               "center_c": round(centre_temp(), 2), "surface_c": round(temps[-1], 2),
               "coldest_c": round(min(temps), 2),
               "mass_loss_pct": round(mass_loss, 3),
               "moisture_end_g": round(recipe["total_g"]*(initial_w - evaporated/original_total), 2),
               "dry_mass_g": round(recipe["total_g"]*(1-initial_w), 2),
               "end_mass_g": round(recipe["total_g"] * (1-evaporated/original_total), 2),
               "browning_index": round(100*(1-math.exp(-surface_brown)), 2),
               "starch_progress_pct": round(100*sum(g*w for g, w in zip(gel, weights)), 2),
               "protein_progress_pct": round(100*sum(p*w for p, w in zip(protein, weights)), 2),
               "rise_pct": round(100*(volume_factor-1),3),
               "max_rise_pct": round(100*(max_volume_factor-1),3),
               "proof_rise_pct": round(proof_rise_pct,3),
               "thickness_mm_est": round(cfg["thickness_mm"]*linear_factor(volume_factor),3),
               "co2_generated_g": round(co2_generated_g,4),
               "co2_retained_g": round(n_co2*CO2_G_MOL,4),
               "gas_retention_factor": round(retention,4),
               "shape": shape, "pan": cfg["pan"],
               "crust_surface_c": round(top_face_c, 2),
               "boil_c": round(boil_c, 2), "pressure_kpa": round(p_amb / 1000.0, 2),
               "surface_aw": round(water_activity_proxy * crust_water_activity(wet[-1] / max(wet[-1]+dry[-1], 1e-12)), 3)}
    # Whole-loaf colour change from Purlis & Salvadori (2007) J. Food Eng.
    # 80:1107-1115: dE = (0.0266*T_oven + 3.4991) * weight-loss %, fitted on
    # bread at 180-220 °C for weight losses above 7 %. Reported only there.
    if recipe["flour_g"] > 0 and 180.0 <= cfg["oven_c"] <= 220.0 and mass_loss > 7.0:
        summary["colour_change_dE_purlis2007"] = round((0.0266*cfg["oven_c"] + 3.4991) * mass_loss, 1)
    else:
        summary["colour_change_dE_purlis2007"] = None
    if not symmetric:
        summary["bottom_c"] = round(temps[0], 2)
        summary["bottom_browning_index"] = round(100*(1-math.exp(-bottom_brown)), 2)
        if pan_c is not None:
            summary["pan_c"] = round(pan_c, 2)
    return annotate_fracture(annotate_high_heat({
        "version": VERSION, "settings": cfg,
        "summary": summary,
        "profile": {"position_pct": position,
                    "axis": axis,
                    "temp_c": [round(t,3) for t in temps],
                    "water_pct": [round(x,3) for x in moisture_profile],
                    "gelation_pct": [round(100*x,2) for x in gel]},
        "timeline": timeline,
        "warnings": warnings,
        "metadata": {"grid_cells": n, "steps": steps, "dt_s": round(dt,5),
                     "shape": shape, "pan": cfg["pan"], "profile_axis": axis,
                     "cell_mass_fraction": [round(w, 6) for w in weights],
                     "cell_air_exposure": [round(e, 4) for e in exposure],
                     "method": "1D implicit finite-volume heat (slab/cylinder/sphere, optional lumped pan node) + explicit moisture, evaporation-condensation apparent conductivity with matching vapour transfer, 100 °C wet-cell boiling cap, gas-index size coupling (experimental)",
                     "reference": "Choi–Okos thermal properties; Purlis/Salvadori heat/moisture modelling"}
    },recipe),recipe)


def simulate_json(json_text: str) -> str:
    return json.dumps(simulate(json.loads(json_text)), separators=(",", ":"), allow_nan=False)
