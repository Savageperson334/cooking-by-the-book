"""Open-pan, well-mixed liquid approximation for BakeLab.

This branch is deliberately distinct from the bread conduction model. It uses
lumped energy and a water-only evaporation balance, simple additive component
volumes and a fixed pan footprint inferred from the initial fluid depth.
No fluid dynamics, agitation model, foam, emulsion stability fit, or oil ignition
prediction is implied. Standard-library-only for CPython and browser Pyodide.
"""
from __future__ import annotations
import math

DENSITY_G_ML = {'water': 0.997, 'protein': 1.33, 'fat': 0.92, 'starch': 1.58,
                'sugar': 1.59, 'fiber': 1.40, 'ash': 2.40}
COMPONENT_CP = {'water': 4180.0, 'protein': 2100.0, 'fat': 2100.0,
                'starch': 1700.0, 'sugar': 1900.0, 'fiber': 1900.0, 'ash': 1100.0}
L_V = 2.26e6
SIGMA = 5.670374419e-8


def clamp(x, low, high):
    return max(low, min(high, x))


def _sigmoid(x):
    return 1 / (1 + math.exp(-clamp(x, -50, 50)))


def liquid_kind(recipe: dict) -> str:
    """Coarse classification for choosing a lumped open-pan model.

    Simple low-protein liquids with little starch/flour are supported. Egg-
    rich batters, custards and water-rich doughs stay on the dough model;
    gelation/setting would invalidate a well-mixed liquid assumption.
    """
    c = recipe['fraction']
    if c['starch'] > 0.19 or c['protein'] > 0.14 or (recipe['flour_g'] > recipe['total_g'] * 0.13 and c['starch'] > 0.09):
        return 'solid'
    if c['water'] > 0.34 and (c['water'] + c['fat'] + c['sugar']) > 0.78:
        if c['sugar'] > 0.32:
            return 'syrup'
        if c['fat'] > 0.20:
            return 'biphasic'
        return 'aqueous'
    if c['fat'] > 0.60 and (c['fat'] + c['water']) > 0.80:
        return 'oil'
    if c['sugar'] > 0.55 and c['water'] > 0.08:
        return 'syrup'
    return 'solid'


def _sugar_bp_c(sugar_g: float, water_g: float) -> float:
    """Smooth empirical screening curve. Not a real candy thermometer model."""
    if water_g < 1e-8:
        return 160.0
    fraction = clamp(sugar_g / max(1e-8, sugar_g + water_g), 0, 0.999)
    ratio = fraction / max(0.001, 1-fraction)
    return 100.0 + clamp(3.8 * ratio**0.7, 0, 55)


def simulate_liquid(recipe: dict, cfg: dict, warnings: list[str], kind: str, version: str) -> dict:
    frac = recipe['fraction']
    total_g = recipe['total_g']
    component_g = {name: total_g*frac[name] for name in DENSITY_G_ML}
    dry_g = total_g - component_g['water']
    water_g = component_g['water']
    initial_water_g = water_g
    sugar_g = component_g['sugar']
    # Fixed footprint area based on additive apparent component volumes and
    # the user's starting depth. Pan shape and sidewall geometry are unknown.
    init_volume_ml = sum(component_g[k]/rho for k, rho in DENSITY_G_ML.items())
    initial_depth_mm = cfg['thickness_mm']
    pan_area_cm2 = init_volume_ml / max(0.2, initial_depth_mm/10)
    pan_area_m2 = pan_area_cm2 / 1e4
    T = cfg['initial_c']
    evap_g = 0.0
    milk_g = float(recipe.get('milk_g', 0.0))
    free_oil_g = float(recipe.get('free_oil_g', 0.0))
    milk_share = milk_g / max(total_g, 1e-10)
    milk_skin_history = 0.0
    syrup_colour_history = 0.0
    steps = max(1, math.ceil(cfg['minutes']*60.0 / 3.0))
    dt = cfg['minutes']*60.0 / steps if cfg['minutes'] else 0.0
    interval = max(1, steps//115)
    timeline = []
    def record(second):
        volume_ml = max(0., init_volume_ml - evap_g / 0.997)
        depth_mm = max(0., initial_depth_mm * volume_ml / max(init_volume_ml, 1e-9))
        end_g = water_g+dry_g
        sg_frac = sugar_g/max(sugar_g+water_g, 1e-9) if (sugar_g+water_g)>0 else 0.0
        thick = clamp(100*max(0, sg_frac-.46)/.42,0,100) if sugar_g>0 else 0.
        # Kinetic 'skin' is an illustrative visualization of hot, largely
        # undisturbed dairy protein at an interface, not a measured film.
        film = clamp(100*(1-math.exp(-milk_skin_history/320)),0,100)
        film *= min(1, water_g/max(initial_water_g*0.015,1e-9))
        film = max(0., film)
        is_two_phase = free_oil_g>0 and initial_water_g>0 and kind in ('aqueous','biphasic','syrup')
        # No mixing/agitator is modeled. Gradual separation is merely a cue.
        dairy_emulsion = clamp(milk_share*1.8, 0, 1)
        separation = (1-math.exp(-second/60 / (5+40*dairy_emulsion))) if is_two_phase else 0
        oil_depth = min(depth_mm, free_oil_g/0.91 / max(pan_area_cm2,1e-9)*10 * separation)
        water_loss_pct = 100*evap_g/total_g
        brown = 100*(1-math.exp(-syrup_colour_history)) if sugar_g>0 else 0
        timeline.append({
            'minute':round(second/60,4), 'center_c':round(T,3), 'mid_c':round(T,3),
            'surface_c':round(T,3),'mass_loss_pct':round(water_loss_pct,4),
            'center_moisture_pct':round(100*water_g/max(end_g,1e-9),3),
            'surface_moisture_pct':round(100*water_g/max(end_g,1e-9),3),
            'starch_progress_pct':0.,'protein_progress_pct':0.,
            'temp_profile':[round(T,2)]*6,
            'water_profile':[round(100*water_g/max(end_g,1e-9),2)]*6,
            'browning_index':round(brown,2),'rise_pct':0.,
            'thickness_mm_est':round(depth_mm,3),
            'liquid_depth_mm':round(depth_mm,4),'liquid_volume_ml':round(volume_ml,2),
            'water_remaining_g':round(water_g,3),'sugar_concentration_pct':round(100*sg_frac,3),
            'syrup_thickening_index_pct':round(thick,2),
            'milk_skin_index_pct':round(film,2),
            'oil_layer_mm':round(oil_depth,3),
            'separation_index_pct':round(100*separation,2),
            'co2_generated_g':0.,'co2_retained_g':0.,
        })
    record(0)
    for step in range(steps):
        if dt == 0: break
        if water_g + dry_g < 1e-9:
            # A physically empty pan has no food temperature. Keep the
            # numeric trace finite and flag this as a computational sentinel.
            T = cfg['oven_c']
            if (step+1)%interval == 0 or step == steps-1:
                record((step+1)*dt)
            continue
        t_k = max(200.0,T+273.15)
        oven_k = max(200.0,cfg['oven_c']+273.15)
        h_rad = 0.84*SIGMA*(t_k*t_k+oven_k*oven_k)*(t_k+oven_k)
        h_top = 12.0 + 10.0*cfg['fan'] + h_rad
        h_bottom = 9.0 + 2.0*cfg['fan']  # uncertain pan heat-transfer coefficient
        # Exact first-order sensible exchange for a lumped heat capacity,
        # avoiding high-temperature oscillation when only a trace remains.
        cp_J_K = (sum(component_g[k]*COMPONENT_CP[k] for k in COMPONENT_CP if k!='water') + water_g*4180)/1000
        cp_J_K = max(0.05,cp_J_K)
        H = (h_top+h_bottom)*pan_area_m2
        Q = cp_J_K*(cfg['oven_c']-T)*(1-math.exp(-H*dt/cp_J_K))  # J
        bp = _sugar_bp_c(sugar_g, water_g)
        # Gentle below-boiling evaporation: a small fraction of a bounded
        # surface mass-transfer estimate. Boiling loss is energy-limited.
        vapor_flux = 1.1e-8 * max(0., (min(101325,610.8*math.exp(17.27*min(99,T)/(min(99,T)+237.3)))) -
                                    0.01*cfg['steam_pct']*101325)
        sub_gate = 1-_sigmoid((T-bp+3)/2.0)
        sub_evap_g = min(water_g, max(0.,vapor_flux*pan_area_m2*dt*1000*0.20*sub_gate),
                         max(0., Q*0.20 / L_V*1000))
        water_g -= sub_evap_g
        evap_g += sub_evap_g
        Tnew = T+(Q-sub_evap_g/1000*L_V)/cp_J_K
        if water_g>1e-12 and Tnew>bp:
            needed_g = (Tnew-bp)*cp_J_K / L_V*1000
            extra_g = min(water_g,max(0.,needed_g))
            water_g -= extra_g
            evap_g += extra_g
            Tnew -= extra_g/1000*L_V/cp_J_K
        # If water remains, bulk temperature is bounded by estimated boiling
        # point, while a fully dried residue may heat toward the oven setpoint.
        if water_g>1e-10:
            Tnew=min(Tnew,bp)
        T=clamp(Tnew,-50,450)
        # Milk-skin heuristic; requires milk and retained liquid.
        if milk_share>0 and water_g>0:
            milk_skin_history += dt * milk_share * _sigmoid((T-72)/6) * (0.65+0.35*min(1,evap_g/max(1,initial_water_g*0.05)))
        # Surface syrup colour is a rough, not colorimetrically calibrated cue.
        if sugar_g>0 and water_g>0:
            conc=sugar_g/max(sugar_g+water_g,1e-9)
            syrup_colour_history += dt*0.000015*_sigmoid((T-116)/10)*_sigmoid((conc-0.77)/0.065)
        if (step+1)%interval == 0 or step==steps-1:
            record((step+1)*dt)
    warnings = list(warnings)
    warnings.append('Liquid branch: well-mixed open-pan energy balance; convection, pan contact, boiling elevation and vapor transport are approximations, not validated measurements.')
    warnings.append('Pan area is inferred from additive ingredient volumes and the initial-depth slider; ingredient dissolution, bubbles, foams, skin resistance and stir rate are not resolved.')
    if free_oil_g>0 and initial_water_g>0:
        warnings.append('Oil/water separation is a qualitative time cue, not a predicted layer-formation rate; no emulsion or mixing history is specified.')
    if milk_g>0:
        warnings.append('Milk-skin shading is heuristic; protein denaturation, stirring and membrane mechanics are not modeled.')
    if sugar_g>0 and initial_water_g>0:
        warnings.append('Sugar concentration is a mass ratio. Thickening/browning are illustrative; crystallization, viscosity and exact boiling elevation are not calculated.')
    if water_g<1e-8 and initial_water_g>0:
        warnings.append('Liquid water exhausted: further heating of residue/empty-pan material is outside validated model behaviour.')
    if kind == 'oil':
        warnings.append('Pure oil: smoke, oxidation, decomposition and fire hazards are not modeled. Temperature trace is not a safety assessment.')
    if cfg['oven_c']>280:
        warnings.append('Very high oven temperature: scorching, combustion, fire and material breakdown are excluded.')
    warnings.append('Screening model only; never use this output as a safe food doneness or cooking-time determination.')
    last=timeline[-1]
    moisture_end = water_g
    return {
        'version':version,'settings':cfg,
        'summary':{
            'total_g':round(total_g,3),'water_pct':round(frac['water']*100,3),
            'fat_pct':round(frac['fat']*100,3),'protein_pct':round(frac['protein']*100,3),
            'starch_pct':round(frac['starch']*100,3),'sugar_pct':round(frac['sugar']*100,3),
            'fiber_pct':round(frac['fiber']*100,3),'ash_pct':round(frac['ash']*100,3),
            'aw_proxy':round(initial_water_g/max(initial_water_g+sugar_g,1e-9),4),
            'center_c':round(T,2),'surface_c':round(T,2),
            'mass_loss_pct':round(100*evap_g/total_g,3),
            'moisture_end_g':round(moisture_end,3),'dry_mass_g':round(dry_g,3),
            'end_mass_g':round(dry_g+water_g,3),
            'browning_index':last['browning_index'],
            'starch_progress_pct':0.,'protein_progress_pct':0.,
            'rise_pct':0.,'max_rise_pct':0.,'proof_rise_pct':0.,
            'thickness_mm_est':last['liquid_depth_mm'],
            'co2_generated_g':0.,'co2_retained_g':0.,'gas_retention_factor':0.,
            'liquid_mode':kind,'liquid_depth_mm':last['liquid_depth_mm'],
            'liquid_volume_ml':last['liquid_volume_ml'],
            'pan_area_cm2':round(pan_area_cm2,2),
            'water_remaining_g':round(water_g,3),
            'sugar_concentration_pct':last['sugar_concentration_pct'],
            'syrup_thickening_index_pct':last['syrup_thickening_index_pct'],
            'milk_skin_index_pct':last['milk_skin_index_pct'],
            'oil_layer_mm':last['oil_layer_mm'],
        },
        'profile':{'position_pct':[0,20,40,60,80,100],
                   'temp_c':[round(T,3)]*6,
                   'water_pct':[round(100*water_g/max(water_g+dry_g,1e-9),3)]*6,
                   'gelation_pct':[0]*6},
        'timeline':timeline,
        'warnings':warnings,
        'metadata':{'grid_cells':6,'steps':steps,'dt_s':round(dt,5),
                    'method':'0D open-pan well-mixed heat balance + water evaporation, additive volume and qualitative phase cues',
                    'reference':'Heat/latent energy balance; qualitative milk skin, oil float and sugar-concentration literature'},
    }
