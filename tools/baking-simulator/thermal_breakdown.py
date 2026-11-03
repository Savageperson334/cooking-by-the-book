"""High-temperature material-survival *diagnostic* for BakeLab.

Post-processes the existing temperature/water history rather than pretending
that the bread/liquid solvers resolve chemical decomposition, reaction enthalpy,
oxygen transport, aerosolization or actual fire. Kinetic constants are
ILLUSTRATIVE. Only conservation / qualitative behaviour is verified.

At high heat, organic solids may volatilize or form char; accessible char may
oxidize; mineral/inorganic material can remain. A fixed food-solid mass at
600 °C is physically indefensible. This module provides a bounded screening
correction without changing the original energy solution. DO NOT use for
flammability, hazards, or quantitative residue predictions.
"""
from __future__ import annotations
import math

ORGANICS = ('sugar','starch','protein','fiber','fat')
# Nominal kinetic modelling parameters, NOT fitted activation energies.
# Temperatures are °C and rate at 300 °C is s^-1 in a dry/accessible sample.
KINETICS = {
    'sugar':   {'onset_c':165.0,'k300':0.00085,'char_yield':0.17},
    'starch':  {'onset_c':215.0,'k300':0.00062,'char_yield':0.20},
    'protein': {'onset_c':205.0,'k300':0.00056,'char_yield':0.24},
    'fiber':   {'onset_c':235.0,'k300':0.00050,'char_yield':0.25},
    'fat':     {'onset_c':300.0,'k300':0.00070,'char_yield':0.035},
}


def clamp(v, lo=0.0, hi=1.0):
    return max(lo,min(hi,v))


def sigmoid(v):
    return 1.0/(1.0+math.exp(-max(-50.0,min(50.0,v))))


def annotate_high_heat(result:dict, recipe:dict) -> dict:
    """Add independent thermal breakdown, ash, char and crack-risk estimates.

    Existing mass_loss_pct/end_mass_g still represent *water-only* mass and are
    deliberately retained so 1D heat/mass equations are not misrepresented.
    The clearly named estimated_* fields include uncertain organic loss.
    """
    frames = result['timeline']
    if not frames: return result
    frac = recipe['fraction']; total = recipe['total_g']
    n = len(frames[0].get('temp_profile',[])) or 1
    pools = [{key:total*frac[key]/n for key in ORGANICS} for _ in range(n)]
    chars = [0.0]*n
    minerals_g = total*frac['ash']
    initial_dry_organic = sum(total*frac[k] for k in ORGANICS)
    initial_fat_g = total * frac['fat']
    initial_pools = {k:total*frac[k] for k in ORGANICS}
    cumulative_conversion_g = {k:0.0 for k in ORGANICS}
    fat_10pct_min = None
    fat_10pct_material_c = None
    organic_10pct_min = None
    organic_volatile = 0.0
    char_oxidized = 0.0
    prev_minute = None
    prev_t = [result['settings']['initial_c']]*n
    crack_index = 0.0
    first_crack_min = None
    first_crack_surface_c = None
    fracture_damage = 0.0
    initial_surface_water = None
    # One phase model for low-water residue, and 1D profiles for dough.
    is_lumped = 'liquid_mode' in result['summary']
    assumed_air_access = result['settings'].get('air_access_pct', 100.0)/100.0
    for frame in frames:
        dt = (frame['minute']-prev_minute)*60.0 if prev_minute is not None else 0.0
        temps = frame.get('temp_profile') or [frame['surface_c']]*n
        current_water = frame.get('water_remaining_g')
        if current_water is None:
            current_water = max(0.0,total*frac['water']-total*frame['mass_loss_pct']/100.0)
        moisture = max(0.0, current_water) / max(1e-10, total - total*frame['mass_loss_pct']/100.0)
        profile_w = frame.get('water_profile') or [100*moisture]*n
        if initial_surface_water is None:
            initial_surface_water = (frame.get('water_profile') or [100*moisture])[-1]/100.0
        if dt>0:
            for j in range(n):
                t = (prev_t[j]+temps[j])*0.5
                wf = clamp(profile_w[j]/100.0)
                # Wet, evaporating specimens resist heating/decomposition.
                # This dampens, but does not imply, reaction-free behaviour.
                exposure = clamp(1.0 - wf/0.45,0.04,1.0)
                for comp in ORGANICS:
                    model = KINETICS[comp]
                    onset = sigmoid((t-model['onset_c'])/16.0)
                    rate = min(0.10, model['k300']*math.exp(clamp((t-300.0)/49.0,-25,6))*onset*exposure)
                    consumed = pools[j][comp] * (-math.expm1(-rate*dt))
                    pools[j][comp] -= consumed
                    cumulative_conversion_g[comp] += consumed
                    char = consumed*model['char_yield']
                    chars[j] += char
                    organic_volatile += consumed-char
                # Ambient-air exposure, NOT a defined oxygen mass-transfer solve.
                # Less accessible char in the centre of a thick sample.
                access = 1.0 if is_lumped or n==1 else (0.15+0.85*(j/(n-1))**1.3)
                oxidation = min(0.09, 0.00040*math.exp(clamp((t-430.0)/58.0,-25,5))*sigmoid((t-340.0)/22.0)) * exposure * access * assumed_air_access
                lost = chars[j]*(-math.expm1(-oxidation*dt))
                chars[j] -= lost
                char_oxidized += lost

            # PHYSICAL fracture screening (distinct from chemical chain breaking):
            # shrink mismatch and thermal/expansion strain are proxies for a
            # drying skin restrained by a wetter core or the baking pan.
            # No real elastic modulus, fracture toughness, geometry or cooling
            # history is available: stress ratio is normalized and qualitative.
            surface_w = clamp(profile_w[-1]/100.0)
            center_w = clamp(profile_w[0]/100.0)
            surface_shrink = max(0.0, initial_surface_water-surface_w)
            differential_shrink = max(0.0, center_w-surface_w)
            thermal_strain = min(0.025, abs(temps[-1]-temps[0])*0.000065)
            oven_rise_strain = min(0.10,max(0.0,frame.get('rise_pct',0.0))*0.0005)
            moisture_strain = 0.24*differential_shrink+0.075*surface_shrink
            # Lumped slurry develops pan-restrained drying tension only after
            # it crosses from suspension to coherent paste/residue.
            constrained_strain = 0.11*surface_shrink if is_lumped else 0.0
            total_strain = moisture_strain + constrained_strain + thermal_strain + oven_rise_strain
            cohesion = clamp((frac['starch'] + frac['protein'] + frac['fiber'] + .65*frac['sugar'])*1.7
                             + min(0.35, recipe.get('banana_g',0.0)/max(total,1e-9)*0.85)
                             + min(0.15, recipe.get('oats_g',0.0)/max(total,1e-9)*0.45))
            if frac['fat']>0.55 or frac['ash']>0.55: cohesion *= 0.02
            dry_gate = sigmoid((.23-surface_w)/.055)
            # Mechanical strain threshold (not an empirical tensile strength).
            normalized_strength = .035 + .030*clamp(frac['protein']+frac['fat']*.4)
            stress_ratio = total_strain / normalized_strength * cohesion * dry_gate
            fracture_drive = max(0., stress_ratio-0.85)
            fracture_damage += (1.0-fracture_damage) * (1.0-math.exp(-dt/60.0*.035*fracture_drive))
        else:
            stress_ratio = 0.0
            total_strain = 0.0
        prev_minute=frame['minute']
        prev_t=list(temps)
        remaining_organic = sum(sum(row.values()) for row in pools)
        char_remaining = sum(chars)
        remaining_total = max(0.0,current_water+minerals_g+remaining_organic+char_remaining)
        total_loss = max(0.0,total-remaining_total)
        fracture_damage_pct = 100*clamp(fracture_damage)
        # Physical cracks cannot remain as a visible intact crust after most
        # of its parent organic matrix is consumed by thermal breakdown.
        remaining_structure = remaining_organic+char_remaining
        structure_retained = clamp(remaining_structure/max(0.10*initial_dry_organic,1e-8))
        fracture_visible_pct = fracture_damage_pct * structure_retained
        if first_crack_min is None and fracture_damage_pct>=25 and structure_retained>0.2:
            first_crack_min=frame['minute']
            first_crack_surface_c=frame['surface_c']
        # Separate CHEMICAL cracking / thermolysis: 10% mass conversion of
        # initial triglyceride-rich fat pool, not a universal crack point.
        fat_conversion_pct = 100*cumulative_conversion_g['fat']/max(initial_fat_g,1e-10) if initial_fat_g>0 else 0.0
        organics_conversion_pct = 100*sum(cumulative_conversion_g.values())/max(initial_dry_organic,1e-10) if initial_dry_organic>0 else 0.0
        if fat_10pct_min is None and initial_fat_g>0.01 and fat_conversion_pct>=10:
            fat_10pct_min=frame['minute']
            fat_10pct_material_c=sum(temps)/len(temps)
        if organic_10pct_min is None and initial_dry_organic>0.01 and organics_conversion_pct>=10:
            organic_10pct_min=frame['minute']
        crack_risk = fracture_visible_pct
        char_pct = 100*char_remaining/max(1e-10,initial_dry_organic)
        if remaining_total<0.01:
            stage='empty / trace'
        elif current_water > 0.35*remaining_total:
            stage='wet / boiling'
        elif char_remaining>0.15*max(remaining_organic,1e-8) and char_remaining>0.002*total:
            stage='charred'
        elif remaining_organic < 0.15*max(initial_dry_organic,1e-8) and minerals_g>0:
            stage='mineral / ash residue'
        elif (organic_volatile+char_oxidized)>0.20*max(initial_dry_organic,1e-8):
            stage='thermally decomposing'
        elif moisture < 0.20:
            stage='dry / browning'
        else:
            stage='wet / setting'
        # Only a visual correction for the drying-height rendering, NOT
        # measured density or coupled reaction-induced shrinkage.
        water_only_mass = max(1e-9,total - total*frame['mass_loss_pct']/100)
        depth_guess = frame.get('liquid_depth_mm', 0.0) * clamp(remaining_total/water_only_mass) if is_lumped else 0.0
        frame.update({
            'estimated_residue_depth_mm':round(depth_guess,4),
            'estimated_remaining_mass_g':round(remaining_total,3),
            'estimated_total_mass_loss_pct':round(100*total_loss/total,3),
            'estimated_intact_organic_g':round(remaining_organic,3),
            'estimated_char_g':round(char_remaining,3),
            'estimated_ash_g':round(minerals_g,3),
            'estimated_volatile_loss_g':round(organic_volatile,3),
            'estimated_char_oxidation_loss_g':round(char_oxidized,3),
            'estimated_char_pct_of_initial_organics':round(char_pct,3),
            'crack_risk_index_pct':round(crack_risk,2),
            'fracture_stress_ratio_proxy':round(stress_ratio,3),
            'fracture_strain_proxy_pct':round(total_strain*100,3),
            'fracture_damage_pct':round(fracture_damage_pct,2),
            'visible_fracture_pct':round(fracture_visible_pct,2),
            'chemical_conversion_pct':round(organics_conversion_pct,2),
            'fat_thermal_conversion_pct':round(fat_conversion_pct,2),
            'fat_intact_g':round(sum(row['fat'] for row in pools),3),
            'thermal_stage':stage,
        })
    last=frames[-1]
    result['summary'].update({key:last[key] for key in (
        'estimated_remaining_mass_g','estimated_total_mass_loss_pct',
        'estimated_residue_depth_mm','estimated_intact_organic_g','estimated_char_g','estimated_ash_g',
        'estimated_volatile_loss_g','estimated_char_oxidation_loss_g',
        'estimated_char_pct_of_initial_organics','crack_risk_index_pct',
        'fracture_stress_ratio_proxy','fracture_strain_proxy_pct',
        'fracture_damage_pct','visible_fracture_pct','chemical_conversion_pct',
        'fat_thermal_conversion_pct','fat_intact_g',
        'thermal_stage')})
    result['summary']['crack_risk_onset_min'] = None if first_crack_min is None else round(first_crack_min,2)
    result['summary']['physical_fracture_onset_surface_c'] = None if first_crack_surface_c is None else round(first_crack_surface_c,1)
    result['summary']['fat_conversion_10pct_min'] = None if fat_10pct_min is None else round(fat_10pct_min,2)
    result['summary']['fat_conversion_10pct_material_c'] = None if fat_10pct_material_c is None else round(fat_10pct_material_c,1)
    result['summary']['organic_conversion_10pct_min'] = None if organic_10pct_min is None else round(organic_10pct_min,2)
    # Inform users of key separation between calculated temperatures and hazard.
    if max(f['surface_c'] for f in frames)>=200:
        result['warnings'].append(
          'Upper-end thermal accounting is a POST-PROCESSING SCREENING ESTIMATE: '
          'illustrative decomposition, char oxidation and ash pools do NOT feed '
          'back into heat flow, latent heats, air/fuel supply, gas transport or geometry.')
    if result['settings']['oven_c']>=350:
        result['warnings'].append(
          'At this temperature, smoking/ignition/flames may occur in reality, '
          'but NO combustion, flame or safe operating conditions are predicted; '
          'user-selected oxygen exposure only scales an illustrative char-oxidation rate.')
    if max(f['fracture_damage_pct'] for f in frames)>15:
        result['warnings'].append(
          'Physical fracture is a qualitative drying/gradient/restraint stress screening only; '
          'real strength, fracture energy, pan adhesion and post-bake cooling are unmeasured.')
    if initial_fat_g>0:
        result['warnings'].append(
          'Triglyceride conversion is an illustrative thermolysis proxy, not an experimentally '
          'identified cracking temperature; fat oxidation, smoke, vapour chemistry and ignition are NOT predicted.')
    result['warnings'].append('Inorganic ash is approximated from the ingredient catalogue ash fraction (including salt and some leavening chemicals); carbonate/salt reactions are not explicitly calculated.')
    result['metadata']['upper_end'] = 'Independent qualitative decomposition/char/ash and drying-fracture screening, not coupled chemistry or solid mechanics.'
    return result
