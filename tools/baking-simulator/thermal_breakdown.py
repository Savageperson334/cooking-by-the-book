"""Qualitative thermal-decomposition and triglyceride-cracking screening.

A POSTPROCESSOR of simulated temperature and water; NOT coupled energy/reaction
chemistry. The equations/coefficients are illustrative, not experimentally
calibrated, and do not predict ignition, flames, gas speciation, smoke toxicity,
cracking temperatures, or safe processing. Physical fracture is modelled
separately in ``physical_fracture.py``.

Mass ledger: initial water + organics + minerals = retained water + intact
organics + intermediate low-molecular products + char + minerals + loss via
volatilization and char oxidation. Water evaporation is supplied by the original
thermal solver. The ledger is a bookkeeping approximation, not a mass balance
including oxygen uptake during combustion (which is deliberately omitted).
"""
from __future__ import annotations
import math

ORGANICS = ('sugar', 'starch', 'protein', 'fiber', 'fat')
# Kinetic constants are ILLUSTRATIVE and not linked to temperature observations.
KINETICS = {
    'sugar':   {'onset_c':165.0,'k300':0.00085,'char_yield':0.17},
    'starch':  {'onset_c':215.0,'k300':0.00062,'char_yield':0.20},
    'protein': {'onset_c':205.0,'k300':0.00056,'char_yield':0.24},
    'fiber':   {'onset_c':235.0,'k300':0.00050,'char_yield':0.25},
    # Bulk non-cracking oil degradation (oxidation, volatilization, reactions).
    'fat':     {'onset_c':240.0,'k300':0.00008,'char_yield':0.035},
}


def clamp(x, low=0.0, high=1.0):
    return max(low, min(high, x))


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-max(-50, min(50, x))))


def thermal_cracking_rate(temp_c, wet_access):
    """Screening cleavage of triacylglycerol feedstock, seconds^-1.

    The 300–500 C literature is evidence of a *regime*, not a sharply defined
    molecular crack point or a measured universal first-order rate.
    """
    return min(0.1, 0.00030 * math.exp(clamp((temp_c-375.0)/51.0,-25.0,5.7))
               * sigmoid((temp_c-325.0)/18.0) * wet_access)


def annotate_high_heat(result: dict, recipe: dict) -> dict:
    frames = result['timeline']
    if not frames: return result
    frac = recipe['fraction']; total = recipe['total_g']
    n = len(frames[0].get('temp_profile',[])) or 1
    pools = [{key:total*frac[key]/n for key in ORGANICS} for _ in range(n)]
    chars = [0.0]*n
    light_products = [0.0]*n  # retained lighter thermal-cleavage products
    minerals_g = total*frac['ash']
    initial_organics = sum(total*frac[k] for k in ORGANICS)
    initial_fat = total*frac['fat']
    organic_volatile = 0.0
    char_oxidized = 0.0
    chemical_feedstock_cracked = 0.0
    lighter_products_released = 0.0
    crossing_min = None
    prev_minute = None
    prev_t = [result['settings']['initial_c']]*n
    for frame in frames:
        dt = (frame['minute']-prev_minute)*60.0 if prev_minute is not None else 0.0
        temps = frame.get('temp_profile') or [frame['surface_c']]*n
        current_water = frame.get('water_remaining_g')
        if current_water is None:
            current_water = max(0.0,total*frac['water']-total*frame['mass_loss_pct']/100.0)
        profile_w = frame.get('water_profile') or [100*current_water/max(total,1e-9)]*n
        if dt>0:
            for j in range(n):
                temperature = (prev_t[j]+temps[j])*0.5
                water_frac = clamp(profile_w[j]/100.0)
                exposure = clamp(1.0-water_frac/0.45, 0.04, 1.0)
                # Non-lipid macromolecule decomposition and devolatilization.
                for comp in ('sugar','starch','protein','fiber'):
                    model = KINETICS[comp]
                    rate = min(.10, model['k300']
                               * math.exp(clamp((temperature-300.)/49.,-25,6))
                               * sigmoid((temperature-model['onset_c'])/16.)*exposure)
                    gone = pools[j][comp] * (-math.expm1(-rate*dt))
                    pools[j][comp] -= gone
                    new_char = gone*model['char_yield']
                    chars[j] += new_char
                    organic_volatile += gone-new_char

                # Fat has TWO independent competing pathways. Only one counts
                # as actual (proxy) chemical cleavage of glyceride chains.
                model = KINETICS['fat']
                noncrack_rate = min(.10,model['k300']
                    * math.exp(clamp((temperature-300.)/49.,-25,6))
                    * sigmoid((temperature-model['onset_c'])/16.)*exposure)
                crack_rate = thermal_cracking_rate(temperature, exposure)
                combined_rate = noncrack_rate+crack_rate
                gone = pools[j]['fat']*(-math.expm1(-combined_rate*dt))
                pools[j]['fat'] -= gone
                chemical = gone*crack_rate/max(combined_rate,1e-20)
                other = gone-chemical
                chemical_feedstock_cracked += chemical
                chars[j] += other*model['char_yield'] + chemical*.04
                organic_volatile += other*(1-model['char_yield']) + chemical*.62
                light_products[j] += chemical*.34

                # Intermediates can leave the pan; this is NOT a predicted
                # product distribution, molecular-weight spectrum or boiling curve.
                release_rate = min(.15,.00013*math.exp(clamp((temperature-330.)/60.,-25,7))
                                  * sigmoid((temperature-180.)/24.))
                release = light_products[j]*(-math.expm1(-release_rate*dt))
                light_products[j] -= release
                lighter_products_released += release
                organic_volatile += release

                air = clamp(result['settings'].get('air_access_pct',100)/100.)
                accessibility = (1.0 if 'liquid_mode' in result['summary'] or n==1
                                  else (0.15+0.85*(j/(n-1))**1.3)) * air
                oxidation_rate = min(.09,.00040
                    * math.exp(clamp((temperature-430.)/58.,-25,5))
                    * sigmoid((temperature-340.)/22.))*exposure*accessibility
                oxidized = chars[j]*(-math.expm1(-oxidation_rate*dt))
                chars[j] -= oxidized
                char_oxidized += oxidized
        prev_minute = frame['minute']
        prev_t = list(temps)

        intact = sum(sum(row.values()) for row in pools)
        char_g = sum(chars)
        intermediate_g = sum(light_products)
        retained = max(0.,current_water+minerals_g+intact+char_g+intermediate_g)
        loss = max(0.,total-retained)
        pct_cracked = 100*chemical_feedstock_cracked/max(initial_fat,1e-9) if initial_fat>0 else 0.0
        if initial_fat>0 and crossing_min is None and pct_cracked>=1.0:
            crossing_min = frame['minute']
        if retained<0.01:
            stage='empty / trace'
        elif current_water > .35*retained:
            stage='wet / boiling'
        elif char_g>.15*max(intact,1e-8) and char_g>.002*total:
            stage='charred'
        elif intact < .15*max(initial_organics,1e-8) and minerals_g>0:
            stage='mineral / ash residue'
        elif (organic_volatile+char_oxidized)>.2*max(initial_organics,1e-8):
            stage='thermally decomposing'
        elif current_water/max(retained,1e-9)<.20:
            stage='dry / browning'
        else:
            stage='wet / setting'
        frame.update({
            'estimated_remaining_mass_g':round(retained,4),
            'estimated_total_mass_loss_pct':round(100*loss/total,3),
            'estimated_intact_organic_g':round(intact,4),
            'estimated_char_g':round(char_g,4),
            'estimated_ash_g':round(minerals_g,4),
            'estimated_volatile_loss_g':round(organic_volatile,4),
            'estimated_char_oxidation_loss_g':round(char_oxidized,4),
            'estimated_char_pct_of_initial_organics':round(100*char_g/max(initial_organics,1e-10),3),
            # This is a cumulative conversion of the original triglyceride
            # feedstock, NOT a count of individual cracked bonds.
            'estimated_triglyceride_cracked_g':round(chemical_feedstock_cracked,4),
            'estimated_triglyceride_cracked_pct':round(pct_cracked,3),
            'estimated_light_fragments_g':round(intermediate_g,4),
            'estimated_light_fragments_released_g':round(lighter_products_released,4),
            'thermal_stage':stage,
        })
    last=frames[-1]
    for key in ('estimated_remaining_mass_g','estimated_total_mass_loss_pct',
                'estimated_intact_organic_g','estimated_char_g','estimated_ash_g',
                'estimated_volatile_loss_g','estimated_char_oxidation_loss_g',
                'estimated_char_pct_of_initial_organics',
                'estimated_triglyceride_cracked_g','estimated_triglyceride_cracked_pct',
                'estimated_light_fragments_g','estimated_light_fragments_released_g',
                'thermal_stage'):
        result['summary'][key]=last[key]
    result['summary']['estimated_cracking_1pct_crossing_min'] = (None if crossing_min is None else round(crossing_min,2))
    if max(f['surface_c'] for f in frames)>=200:
        result['warnings'].append(
            'Upper-end decomposition and triglyceride cracking are POST-PROCESSING ESTIMATES: '
            'neither feeds back into temperature, reaction enthalpy, evaporation, air flow or geometry.')
    if initial_fat>0 and max(f['surface_c'] for f in frames)>300:
        result['warnings'].append(
            'Triglyceride thermal cracking index is uncalibrated. Oil breakdown may include oxidation, '
            'hydrolysis, radical cleavage and evaporation; the cleavage fraction is not a universal crack point.')
    if result['settings'].get('air_access_pct',100)<20 and max(f['estimated_char_g'] for f in frames)>0.1:
        result['warnings'].append('Low air-access proxy retains more char; actual oxygen and combustion are not simulated.')
    if result['settings']['oven_c']>=350:
        result['warnings'].append('Extreme oven setting: possible real smoking, ignition and flames are NOT modeled; no safe oil-heating conditions are implied.')
    result['metadata']['upper_end']='Uncalibrated independent organic degradation / triglyceride-cleavage / char screening, not combustion.'
    return result
