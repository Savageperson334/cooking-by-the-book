"""Shapes and pan/support presets for BakeLab's dough solver (stdlib only).

Shapes are 1-D: a flat slab (heat through its thickness), a long cylinder
(radial heat, e.g. baguette) or a sphere (radial heat, e.g. roll or boule).
Pan/support presets change the slab's BOTTOM face: open air, a rack with
baking paper, or a solid pan/stone that is solved as an extra lumped
temperature node in the implicit heat system.

Material properties (density, specific heat, conductivity, emissivity) are
ordinary handbook values for the material. Dough-pan contact conductance and
the rack/paper shielding factors are ASSUMPTIONS, not measurements.
"""
from __future__ import annotations

SHAPES = {
    "slab": "Flat slab (thickness)",
    "cylinder": "Long cylinder, e.g. baguette (diameter)",
    "sphere": "Ball, e.g. roll or boule (diameter)",
}

# kind 'symmetric': both faces identical and open (legacy BakeLab behaviour).
# kind 'open': bottom face open to oven but partly shielded.
# kind 'solid': lumped pan node between the oven and the dough's bottom face.
PANS = {
    "none": {"label": "None, both faces open (legacy)", "kind": "symmetric"},
    "rack": {"label": "Wire rack + baking paper", "kind": "open",
             "heat_scale": 0.95, "evap_scale": 0.35},
    "aluminium_sheet": {"label": "Aluminium sheet, light (1.5 mm)", "kind": "solid",
                        "thickness_mm": 1.5, "density": 2700.0, "cp": 900.0, "k": 200.0,
                        "emissivity": 0.12, "contact_h": 250.0, "preheated": False},
    "dark_steel_pan": {"label": "Dark steel pan (1 mm)", "kind": "solid",
                       "thickness_mm": 1.0, "density": 7850.0, "cp": 480.0, "k": 50.0,
                       "emissivity": 0.80, "contact_h": 250.0, "preheated": False},
    "glass_dish": {"label": "Glass dish (5 mm)", "kind": "solid",
                   "thickness_mm": 5.0, "density": 2230.0, "cp": 830.0, "k": 1.1,
                   "emissivity": 0.90, "contact_h": 250.0, "preheated": False},
    "cast_iron": {"label": "Cast iron / Dutch oven base, preheated (5 mm)", "kind": "solid",
                  "thickness_mm": 5.0, "density": 7200.0, "cp": 460.0, "k": 50.0,
                  "emissivity": 0.85, "contact_h": 300.0, "preheated": True},
    "baking_stone": {"label": "Baking stone, preheated (15 mm)", "kind": "solid",
                     "thickness_mm": 15.0, "density": 2000.0, "cp": 1000.0, "k": 1.5,
                     "emissivity": 0.90, "contact_h": 300.0, "preheated": True},
    "baking_steel": {"label": "Baking steel, preheated (6 mm)", "kind": "solid",
                     "thickness_mm": 6.0, "density": 7850.0, "cp": 480.0, "k": 50.0,
                     "emissivity": 0.80, "contact_h": 300.0, "preheated": True},
}

ROOM_C = 22.0  # starting temperature of a pan that is not preheated


def exponent(shape: str) -> int:
    """Area grows as r**p: 0 for slab, 1 for cylinder, 2 for sphere."""
    return {"slab": 0, "cylinder": 1, "sphere": 2}[shape]


def build_grid(shape: str, span_m: float, n: int) -> tuple[list[float], list[float]]:
    """Cell volumes and face areas per unit 'measure'.

    Slab: per m² of footprint. Cylinder: per m of length per radian.
    Sphere: per steradian. Faces run from index 0 (inner side) to n (outer).
    For radial shapes face 0 is the centre (area 0).
    """
    p = exponent(shape)
    dr = span_m / n
    faces = [j * dr for j in range(n + 1)]
    if p == 0:
        return [dr] * n, [1.0] * (n + 1)
    vols = [(faces[i+1]**(p+1) - faces[i]**(p+1)) / (p+1) for i in range(n)]
    areas = [f**p for f in faces]
    return vols, areas


def solid_pan_conductances(pan: dict, h_under_air: float, h_rad_unit: float) -> tuple[float, float, float]:
    """(underside conductance to oven, pan-to-dough conductance, heat capacity) per m².

    Half the plate thickness is put in series on each side, which matters for
    glass and stone and is negligible for metals.
    """
    t = pan["thickness_mm"] / 1000.0
    half_r = (t / 2.0) / pan["k"]
    h_under = h_under_air + pan["emissivity"] * h_rad_unit
    under = 1.0 / (1.0 / h_under + half_r)
    contact = 1.0 / (1.0 / pan["contact_h"] + half_r)
    capacity = pan["density"] * t * pan["cp"]
    return under, contact, capacity
