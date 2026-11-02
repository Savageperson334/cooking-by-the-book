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

VERSION = "0.1.0"
COMPONENTS = ("water", "protein", "fat", "starch", "sugar", "fiber", "ash")
SIGMA = 5.670374419e-8  # W / (m² K⁴)
LV = 2.26e6  # J / kg, reference latent heat of water
WATER_CP = 4180.0  # J/(kg K)


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


def _vapor_pressure(temp_c: float) -> float:
    """Antoine correlation for water at 1–100°C, capped at 1 atm."""
    t = bounded(temp_c, 1.0, 100.0)
    return min(101325.0, 133.322368 * 10 ** (8.07131 - 1730.63 / (233.426 + t)))


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
            "baking_soda_g": amounts.get("baking_soda", 0.0), "cocoa_g": amounts.get("cocoa", 0.0)}


def validate_run(recipe: dict, settings: dict) -> tuple[dict, list[str]]:
    limits = {"oven_c": (-20, 400), "minutes": (0, 300), "thickness_mm": (2, 250),
              "initial_c": (-20, 100), "steam_pct": (0, 100), "fan": (0, 1)}
    cfg = {}
    for key, (lo, hi) in limits.items():
        val = float(settings.get(key, {"oven_c": 220, "minutes": 35, "thickness_mm": 80,
                                       "initial_c": 22, "steam_pct": 5, "fan": 0}[key]))
        if not math.isfinite(val) or not lo <= val <= hi:
            raise ValueError(f"{key}: expected a finite value in [{lo}, {hi}]")
        cfg[key] = val
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
        w.append("Oven temperature is outside conventional bread-baking calibration ranges.")
    if cfg["thickness_mm"] < 10 or cfg["thickness_mm"] > 140:
        w.append("Unusual thickness: effective 1D geometry and surface coefficients are uncertain.")
    if cfg["minutes"] > 120:
        w.append("Long heating: charring, pyrolysis, fire and large structural deformation are NOT simulated.")
    if recipe["total_g"] > 5000:
        w.append("Very large batch; actual geometry matters more than bulk mass.")
    return cfg, w


def simulate(payload: dict) -> dict:
    catalog = payload["catalog"]
    amounts = payload["amounts"]
    recipe = composition_of(catalog, amounts)
    cfg, warnings = validate_run(recipe, payload.get("settings", {}))
    frac = recipe["fraction"]
    mass_kg = recipe["total_g"] / 1000.0
    n = int(bounded(round(cfg["thickness_mm"] / 3.5), 4, 26))
    L = cfg["thickness_mm"] / 2000.0  # half-thickness (m)
    dx = L/n
    initial_w = frac["water"]
    dry_comp = {k: (frac[k] / (1.0-initial_w)) if initial_w < 1 else 0.0 for k in COMPONENTS if k != "water"}
    density = 920.0  # effective dough density (kg m-3); approximate, held fixed
    dry = [(1 - initial_w) * density * dx for _ in range(n)]  # kg / m² per half-loaf
    wet = [initial_w * density * dx for _ in range(n)]
    temps = [cfg["initial_c"] for _ in range(n)]
    gel = [0.0 for _ in range(n)]
    protein = [0.0 for _ in range(n)]
    dry_kg_m2 = sum(dry)
    original_kg_m2 = dry_kg_m2 + sum(wet)
    evaporated = 0.0
    surface_brown = 0.0
    # Ideal-solute water-activity proxy (assumes dissolved sugar and salt).
    # Real flour-bound water, phase separation and solubility are not captured.
    n_water = max(0.0, frac["water"] / 0.018015)
    n_solute = frac["sugar"] / 0.34230 + 1.8*recipe["salt_g"]/max(recipe["total_g"],1e-9)/0.05844
    water_activity_proxy = n_water/(n_water+n_solute) if n_water+n_solute else 0.0
    # Yield m² full-slab projected area implied by initial dough mass; displayed
    # output is mass fraction so area does not need to be known independently.
    total_s = cfg["minutes"] * 60.0
    # explicit heat + moisture stability bound, including extreme thickness
    cp0, k0 = physical_properties(frac, cfg["initial_c"])
    alpha = k0 / (density * cp0)
    dt_stable = 0.75 * dx * dx / max(alpha, 2e-8)
    dt = min(5.0, max(0.25, dt_stable))
    steps = max(1, math.ceil(total_s / dt))
    dt = total_s / steps if total_s else 0.0
    stride = max(1, steps // 100)
    timeline = []
    heat_transfer = 16.0 + 13.0 * cfg["fan"]  # convective W m-2 K-1 heuristic
    p_air = cfg["steam_pct"] / 100.0 * 101325.0
    last_surface_rate = 0.0

    def record(second):
        remaining = sum(wet) + dry_kg_m2
        moisture = [wet[i] / (wet[i]+dry[i]) if wet[i]+dry[i] else 0.0 for i in range(n)]
        timeline.append({
            "minute": round(second / 60, 4),
            "center_c": round(temps[0], 3),
            "surface_c": round(temps[-1], 3),
            "mid_c": round(temps[n//2], 3),
            "mass_loss_pct": round(100 * evaporated / original_kg_m2, 4),
            "surface_moisture_pct": round(100 * moisture[-1], 3),
            "center_moisture_pct": round(100 * moisture[0], 3),
            "starch_progress_pct": round(100 * sum(gel)/n, 2),
            "protein_progress_pct": round(100 * sum(protein)/n, 2),
            "temp_profile": [round(t, 2) for t in temps],
            "water_profile": [round(x*100, 2) for x in moisture],
            "browning_index": round(100 * (1.0 - math.exp(-surface_brown)), 2),
        })

    record(0.0)
    for step in range(steps):
        # composition and properties are recomputed from each cell's retained water
        cps, ks = [], []
        for i in range(n):
            water_frac = wet[i] / max(wet[i]+dry[i], 1e-12)
            local = {"water": water_frac}
            for k in COMPONENTS:
                if k != "water":
                    local[k] = (1-water_frac) * dry_comp[k]
            cp, k = physical_properties(local, temps[i])
            # gas pores and crumb structure lower effective conduction; provisional
            porosity_factor = 0.75 + 0.15 * min(1.0, recipe["gluten_fraction"] / 0.10)
            cps.append((dry[i] + wet[i]) * cp)  # J/(m2 K)
            ks.append(k * porosity_factor)

        # Linearized radiative+convective boundary; implicit Euler heat flow.
        # Tridiagonal solve avoids explicit-scheme instability for very thin or
        # extreme formulations. Conductance & heat capacity remain finite.
        surface_k = temps[-1] + 273.15
        oven_k = cfg["oven_c"] + 273.15
        h_rad = 0.86 * SIGMA * (oven_k**2 + surface_k**2) * (oven_k + surface_k)
        h_eff = heat_transfer + h_rad
        face = [0.0] * (n + 1)
        for j in range(1, n):
            face[j] = (2*ks[j-1]*ks[j] / max(ks[j-1]+ks[j], 1e-12)) / dx
        face[n] = h_eff
        # Vapor escaping from the outside surface, bounded by heat supplied
        # through its boundary and the nearby interior at the old time.
        p_sat = _vapor_pressure(temps[-1])
        liquid_availability = bounded(wet[-1] / max(dry[-1] + wet[-1], 1e-12) / 0.22, 0.0, 1.0)
        vapor_flux = 1.5e-8 * max(0.0, water_activity_proxy*p_sat - p_air) * liquid_availability
        available_rate = max(0.0, h_eff*(cfg["oven_c"]-temps[-1]) +
                             face[n-1]*(temps[-2]-temps[-1]))
        vapor_mass = min(wet[-1], vapor_flux * dt,
                         (available_rate*dt + 0.01*max(0.0,temps[-1]-20)*cps[-1]) / LV)
        wet[-1] -= vapor_mass
        evaporated += vapor_mass
        last_surface_rate = vapor_mass / max(dt, 1e-12)

        lower = [0.0] * n
        diag = [0.0] * n
        upper = [0.0] * n
        right = [0.0] * n
        for i in range(n):
            d = cps[i] / max(dt, 1e-12)
            lo, hi = face[i], face[i+1]
            diag[i] = d + lo + hi
            lower[i] = -lo
            upper[i] = -hi
            right[i] = d * temps[i]
        right[-1] += h_eff * cfg["oven_c"] - vapor_mass*LV/max(dt,1e-12)
        for i in range(1,n):
            factor = lower[i]/diag[i-1]
            diag[i] -= factor * upper[i-1]
            right[i] -= factor * right[i-1]
        next_temp = [0.0]*n
        next_temp[-1] = right[-1]/diag[-1]
        for i in range(n-2,-1,-1):
            next_temp[i] = (right[i]-upper[i]*next_temp[i+1])/diag[i]
        temps = next_temp
        # moisture diffusion; conservative and controlled by local temperature
        dm = [0.0] * n
        for j in range(1, n):
            D = (1e-9 + 7e-9 * sigmoid((0.5*(temps[j]+temps[j-1])-75)/15))
            flux = D * (wet[j]/dx - wet[j-1]/dx) / dx  # kg / (m2 s), toward center
            amount = bounded(flux * dt, -max(0.0, wet[j-1]*0.3), max(0.0, wet[j]*0.3))
            dm[j] -= amount
            dm[j-1] += amount
        wet = [max(0.0, wet[i] + dm[i]) for i in range(n)]
        # phenomenological kinetic indices; not a measurement of doneness
        if recipe["flour_g"] > 0:
            for i in range(n):
                wlocal = wet[i] / max(wet[i]+dry[i], 1e-12)
                water_gate = sigmoid((wlocal - 0.16) / 0.035)
                g_rate = 0.0025 * sigmoid((temps[i] - 66.0)/5.5) * water_gate
                gel[i] += (1.0-gel[i]) * (1.0 - math.exp(-g_rate * dt))
                p_rate = 0.0018 * sigmoid((temps[i]-74)/8)
                protein[i] += (1.0-protein[i]) * (1.0 - math.exp(-p_rate*dt))
        # surface browning *index*, not colorimetrically calibrated
        local_w = wet[-1] / max(wet[-1]+dry[-1], 1e-12)
        dry_gate = sigmoid((0.23-local_w) / 0.055)
        substrate = bounded((frac["sugar"]+0.006)/0.03, 0.1, 4.0) * bounded((frac["protein"]+0.015)/0.12, 0.2, 2.0)
        soda_effect = 1 + 0.8 * bounded(recipe["baking_soda_g"]/max(recipe["total_g"],1e-8) / 0.012, 0, 2)
        if recipe["flour_g"] > 0 or frac["protein"] > 0.03:
            browning_rate = 0.00019 * math.exp(bounded((temps[-1]-145)/28, -7, 6)) * dry_gate * substrate * soda_effect
            surface_brown += browning_rate * dt
        if (step+1) % stride == 0 or step == steps-1:
            record((step+1)*dt)
    moisture_profile = [100*wet[i]/(wet[i]+dry[i]) if wet[i]+dry[i] else 0 for i in range(n)]
    mass_loss = evaporated/original_kg_m2 * 100
    if recipe["flour_g"] < 1:
        warnings.append("Starch and protein transition indices are disabled without flour; use the temperature and moisture traces only.")
    if sum(wet)+dry_kg_m2 < 0.01*original_kg_m2:
        warnings.append("Almost no mass remains: the calculated temperature belongs to an empty computational grid and is not a material prediction.")
    if cfg["oven_c"] > 280:
        warnings.append("At very high temperatures, pyrolysis, fire hazards and chemical decomposition are outside this model.")
    warnings.append("Screening model: 1D slab, fixed geometry, simplified evaporation and reaction indices. Not validated for food safety or exact doneness.")
    return {
        "version": VERSION, "settings": cfg,
        "summary": {"total_g": round(recipe["total_g"], 3),
                    "water_pct": round(frac["water"]*100, 3),
                    "fiber_pct": round(frac["fiber"]*100, 3),
                    "aw_proxy": round(water_activity_proxy, 4),
                    "ash_pct": round(frac["ash"]*100, 3),
                    "fat_pct": round(frac["fat"]*100, 3),
                    "sugar_pct": round(frac["sugar"]*100, 3),
                    "starch_pct": round(frac["starch"]*100, 3),
                    "protein_pct": round(frac["protein"]*100, 3),
                    "center_c": round(temps[0], 2), "surface_c": round(temps[-1], 2),
                    "mass_loss_pct": round(mass_loss, 3),
                    "moisture_end_g": round(recipe["total_g"]*(initial_w - evaporated/original_kg_m2), 2),
                    "dry_mass_g": round(recipe["total_g"]*(1-initial_w), 2),
                    "end_mass_g": round(recipe["total_g"] * (1-evaporated/original_kg_m2), 2),
                    "browning_index": round(100*(1-math.exp(-surface_brown)), 2),
                    "starch_progress_pct": round(100*sum(gel)/n, 2),
                    "protein_progress_pct": round(100*sum(protein)/n, 2)},
        "profile": {"position_pct": [round(100*i/(n-1),2) for i in range(n)],
                    "temp_c": [round(t,3) for t in temps],
                    "water_pct": [round(x,3) for x in moisture_profile],
                    "gelation_pct": [round(100*x,2) for x in gel]},
        "timeline": timeline,
        "warnings": warnings,
        "metadata": {"grid_cells": n, "steps": steps, "dt_s": round(dt,5),
                     "method": "1D implicit finite-volume heat + explicit moisture, approximate evaporation",
                     "reference": "Choi–Okos thermal properties; Purlis/Salvadori heat/moisture modelling"}
    }


def simulate_json(json_text: str) -> str:
    return json.dumps(simulate(json.loads(json_text)), separators=(",", ":"), allow_nan=False)
