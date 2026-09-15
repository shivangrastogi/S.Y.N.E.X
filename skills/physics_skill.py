"""Physics — Newton's F=ma + kinetic/potential energy. Offline."""
from __future__ import annotations

from core.skill_registry import skill


@skill(
    name="force_calc",
    description="Newton's law F=ma: find force, mass or acceleration from the other two (offline).",
    patterns=[
        "mass 5 kg acceleration 10 force", "force calculate karo",
        "newton second law se force", "mass aur acceleration se force",
        "force 100 mass 20 acceleration", "f=ma nikaalo",
    ],
    required_entities=[],
)
def force_calc(slots: dict) -> str:
    from core.physics_calc import force_calc as _fc
    return _fc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="energy_calc",
    description="Kinetic energy (½mv²) or potential energy (mgh) from mass, velocity or height (offline).",
    patterns=[
        "mass 5 velocity 10 kinetic energy", "energy calculate karo",
        "kinetic energy nikaalo", "potential energy mass height se",
        "mass 2 height 10 potential energy", "ke ya pe nikaalo",
    ],
    required_entities=[],
)
def energy_calc(slots: dict) -> str:
    from core.physics_calc import energy_calc as _ec
    return _ec(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="density_calc",
    description="Density = mass/volume: find any of the three from the other two (offline).",
    patterns=[
        "mass 10 volume 2 density", "density calculate karo",
        "mass aur volume se density", "ghanatv nikaalo",
        "density 5 volume 4 mass", "density formula se nikaalo",
    ],
    required_entities=[],
)
def density_calc(slots: dict) -> str:
    from core.physics_calc import density_calc as _dc
    return _dc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="pressure_calc",
    description="Pressure = force/area: find any of the three from the other two (offline).",
    patterns=[
        "force 100 area 2 pressure", "pressure calculate karo",
        "force aur area se pressure", "dabav nikaalo",
        "pressure 50 area 4 force", "pressure formula se",
    ],
    required_entities=[],
)
def pressure_calc(slots: dict) -> str:
    from core.physics_calc import pressure_calc as _pc
    return _pc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="momentum_calc",
    description="Momentum p=mv: find momentum, mass or velocity from the other two (offline).",
    patterns=[
        "mass 5 velocity 10 momentum", "momentum calculate karo",
        "sanveg nikaalo", "mass aur velocity se momentum",
        "momentum 50 velocity 10 mass", "p=mv nikaalo",
    ],
    required_entities=[],
)
def momentum_calc(slots: dict) -> str:
    from core.physics_calc import momentum_calc as _mc
    return _mc(slots.get("raw_text") or slots.get("text") or "")


@skill(
    name="work_power",
    description="Work = force×distance and Power = work/time (offline).",
    patterns=[
        "force 10 distance 5 work", "work aur power nikaalo",
        "kaam kitna hua force distance se", "power calculate karo work time se",
        "work 100 time 20 power", "kaam aur shakti batao",
    ],
    required_entities=[],
)
def work_power(slots: dict) -> str:
    from core.physics_calc import work_power as _wp
    return _wp(slots.get("raw_text") or slots.get("text") or "")
