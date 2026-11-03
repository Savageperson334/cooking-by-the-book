"""Drying and thermal-stress cracking *risk* diagnostic.

PHYSICAL crack formation is distinct from chemical cracking of triglycerides.
This model uses moisture loss, a 1-D gradient and matrix composition as stress
proxies. It does not calculate a strain/stress tensor, elastic modulus, fracture
energy, adhesion, a material-specific critical stress, or a real crack point.
All reported 50-point crossing times are MODEL THRESHOLDS, NOT FRACTURE TIMES.
"""
from __future__ import annotations
import math


def clamp(x,lo=0.,hi=1.): return max(lo,min(hi,x))


def sigmoid(x): return 1/(1+math.exp(-clamp(x,-50,50)))


def annotate_fracture(result:dict,recipe:dict)->dict:
    frames=result['timeline']
    if not frames:return result
    frac=recipe['fraction']; total=recipe['total_g']
    water_start=total*frac['water']
    dry_start=total*(1-frac['water'])
    organics_start=total*sum(frac[x] for x in ('sugar','starch','protein','fiber','fat'))
    # A powder, liquid pool and a plastic oil have weak fractureable networks.
    matrix=frac['starch']+frac['protein']+1.4*frac['fiber']+0.35*frac['sugar']
    structure=1-math.exp(-4.5*matrix)
    structure*=1-clamp((frac['fat']-.3)/.65)*.94
    structure*=1-clamp((frac['ash']-.45)/.5)*.96
    if recipe.get('banana_g',0)>0 or recipe.get('oats_g',0)>0:
        structure=max(structure,min(.85,2.0*(recipe.get('banana_g',0)*.25+recipe.get('oats_g',0)*.915)/max(total,1e-8)))
    prior_water=water_start
    prev_min=None
    cumulative_shrink=0.
    cumulative_thermal=0.
    crossing=None
    crossing_surface_c=None
    for frame in frames:
        minute=frame['minute']
        dt=max(0.,(minute-prev_min)*60) if prev_min is not None else 0.
        current_water=frame.get('water_remaining_g')
        if current_water is None:current_water=max(0.,water_start-total*frame['mass_loss_pct']/100.)
        water_frac=current_water/max(current_water+dry_start,1e-9)
        dry_gate=sigmoid((.58-water_frac)/.12)
        hot_gate=sigmoid((frame['surface_c']-75.)/18.)
        gradient=max(0.,max(frame.get('temp_profile') or [frame['center_c'],frame['surface_c']])-
                     min(frame.get('temp_profile') or [frame['center_c'],frame['surface_c']]))
        moist_prof=frame.get('water_profile') or []
        wet_gradient=max(0.,(moist_prof[0]-moist_prof[-1])/100.) if len(moist_prof)>1 else 0.
        drying_fraction=max(0.,prior_water-current_water)/max(water_start,1e-9) if water_start>0 else 0.
        # Dimensionless stress-drive is accumulated from differential shrinkage
        # and thermal/moisture gradients. Constants are not measured moduli.
        cumulative_shrink += structure*dry_gate*hot_gate*(6.3*drying_fraction+dt*1.8e-5*wet_gradient)
        cumulative_thermal += structure*dry_gate*hot_gate*(dt*3.5e-7*gradient)
        raw_index=100*(1-math.exp(-(cumulative_shrink+cumulative_thermal)))
        remaining_org=frame.get('estimated_intact_organic_g',organics_start)+frame.get('estimated_char_g',0.)
        surviving=clamp(remaining_org/max(organics_start*.07,1e-8)) if organics_start>0 else 0.
        physical_index=raw_index*surviving
        # Compatibility with v0.9's independent damage vs visible fissure
        # indicators. Damage may persist while the material is later consumed;
        # visible fissures cease to be meaningful when little structure remains.
        screening_stress_ratio=max(0.0,cumulative_shrink+cumulative_thermal)
        strain_proxy_pct=100*0.03*screening_stress_ratio
        if crossing is None and physical_index>=20:
            crossing=minute
            crossing_surface_c=frame['surface_c']  # uncalibrated index threshold, not failure temperature
        frame.update({
            'physical_crack_risk_pct':round(physical_index,3),
            'visible_fracture_pct':round(physical_index,3),
            'fracture_damage_pct':round(raw_index,3),
            'fracture_stress_ratio_proxy':round(screening_stress_ratio,4),
            'fracture_strain_proxy_pct':round(strain_proxy_pct,4),
            'physical_shrinkage_drive':round(cumulative_shrink,4),
            'physical_gradient_drive':round(cumulative_thermal,4),
            'physical_moisture_contrast_pct':round(100*wet_gradient,3),
            # Compatibility with the v0.9 scene and chart selector.
            'crack_risk_index_pct':round(physical_index,3),
        })
        prior_water=current_water
        prev_min=minute
    end=frames[-1]
    for key in ('physical_crack_risk_pct','visible_fracture_pct','fracture_damage_pct',
                'fracture_stress_ratio_proxy','fracture_strain_proxy_pct','physical_shrinkage_drive',
                'physical_gradient_drive','physical_moisture_contrast_pct','crack_risk_index_pct'):
        result['summary'][key]=end[key]
    result['summary']['physical_crack_proxy_20pct_crossing_min']=None if crossing is None else round(crossing,2)
    result['summary']['physical_crack_proxy_20pct_surface_c']=None if crossing_surface_c is None else round(crossing_surface_c,2)
    result['summary']['physical_crack_proxy_50pct_crossing_min']=None if crossing is None else round(crossing,2)  # legacy alias, avoid for display
    result['summary']['crack_risk_onset_min']=result['summary']['physical_crack_proxy_50pct_crossing_min']
    if max(f['physical_crack_risk_pct'] for f in frames)>5:
        result['warnings'].append(
            'Physical fracture: model uses drying/shrinkage and temperature/moisture-gradient stress drives, '
            'NOT tensile strength, adhesion, fracture energy, or a measured crack point. '
            '20-point crossing (if any) is an arbitrary risk-index threshold.')
    result['metadata']['physical_fracture']='Uncalibrated drying and thermal-stress screening; no fracture mechanics solver.'
    return result
