# Reference bakes: measured loaf centre temperatures

Published bakes with a measured **centre temperature**, used to check BakeLab's dough model. The machine-readable copy, including how each one is entered into BakeLab, is [`tools/baking-simulator/reference_bakes.json`](../tools/baking-simulator/reference_bakes.json). The checks run in `tests/test_reference_bakes.py`.

Values come from the papers' text only. No curves were digitised.

## A. Papasidero, Manenti & Pierucci — home-style round loaf (used for fitting)

- **Source:** *Bread baking modeling: Coupling heat transfer and weight loss by the introduction of an explicit vaporization term*, Journal of Food Engineering (online 30 Sept 2014). [doi:10.1016/j.jfoodeng.2014.09.031](https://doi.org/10.1016/j.jfoodeng.2014.09.031) · [accepted manuscript PDF](https://re.public.polimi.it/bitstream/11311/970550/4/Bread%20baking%20modeling-Coupling%20heat%20transfer%20and%20weight%20loss_11311-970550_Manenti.pdf)
- **Dough:** flour 100, water 58, salt 2, dry yeast 2 (baker's %), about 810 g, proofed about 1 h.
- **Shape:** Italian *pagnotta*, about 21.7 cm across and 5 cm high, on a grid with baking paper.
- **Oven:** domestic oven at a 200 °C setpoint, fan about 2 m/s, about 40 min.
- **Measured:** the centre barely warmed for about 5 min, then rose for about 20 min to a **97–99 °C plateau**. Baked mass was 738 g (**8.9 % loss**). The loaf rose from 5.0 cm to 7.0 cm high.

## B. Zhang, Yang, Xu, Long & Ye (2025) — thin layer in a glass mould (held out)

- **Source:** *Study on Moisture Phase Changes in Bread Baking Using a Coupling Model*, Foods 14:1649, CC BY 4.0. [doi:10.3390/foods14091649](https://doi.org/10.3390/foods14091649)
- **Dough:** flour, water (W/F 0.55) and yeast (1 g per 100 g flour); 64.5 g liquid water, 0.82 kg/kg dry-basis moisture.
- **Shape:** about 20 mm of dough in a 100 mm borosilicate glass cylinder. It rose to about 51 mm on the axis.
- **Oven:** domestic oven at a 180 °C setpoint, 30 min.
- **Measured:**
  - The probes at 5 mm and 15 mm height reached 100 °C at about 15 min.
  - The 10 mm probe on the axis reached 100 °C at about 21.7 min.
  - The coolest point passed **93 °C at about 17 min**.
  - **15.0 g of water was lost.**
- The authors attribute more than 60 % of the dough's effective thermal conductivity to evaporation–diffusion–condensation in closed pores.

## How BakeLab compares (v0.10.0)

| | Measured | Before (conduction only) | v0.10.0 steam term |
|---|---|---|---|
| A: centre reaches 97 °C | ~25 min | never (80 °C at 40 min) | 25 min *(fitted)* |
| A: weight loss | 8.9 % | 10.1 % | 7.9 % *(not fitted)* |
| B: centre passes 93 °C | ~17 min | 23.8 min | 16.5 min |
| B: mid-depth reaches ~100 °C | ~21.7 min | 29.3 min | 20.0 min |
| B: water lost | 15.0 g | 21.4 g | 20.7 g |

**Known gaps:**
- BakeLab treats the dough as a slab heated equally on both faces. Bake B sat in glass, open only on top, so the model loses water from twice the real evaporating area.
- Both bakes used cycling domestic ovens.
- The fitted effective vapour diffusivity (4.6×10⁻⁵ m²/s) is somewhat larger than water vapour's diffusivity in free air. It is therefore also absorbing missing physics, such as microscale enhancement, 3D geometry and the real loaf's larger rise. It is a fitted number, not a measured dough property.

## Wanted next

- Another independent bake with a **measured centre-temperature curve and mass loss**, ideally a tin loaf. A home bake with a probe thermometer logged every 5 min, weighed before and after, would do. Use the [experiment template](../experiments/TEMPLATE.md).
- Readings near the surface (crust) to check the drying front and browning.
