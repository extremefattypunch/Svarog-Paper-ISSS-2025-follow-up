# Figure 9 — 75-Day Orbital Element Evolution for the Representative Gain Case

**Paper reference**: `Sections/breakdown.tex`, label `fig:elementsvstime`. Source PNG: `Figures/fig9_rect.png`.

---

## Scientific objective

Show that the gain regime is **transient and self-limiting** — the early SMA rise is achieved by *apogee pumping with eccentricity growth*, not by clean uniform orbit raising. Perigee erodes, drag becomes concentrated near perigee, and eventually the orbit decays *below its initial level*. This is the paper's most important caveat: the effect is real but bounded.

What the figure must show:

1. **a(t)** non-monotonic: rises to a peak around day 26.5, then falls; ends below initial.
2. **h_a(t) (apogee)** rises substantially more than a (apogee carries the SMA growth).
3. **h_p(t) (perigee)** monotonically erodes.
4. **e(t)** grows from ~10⁻⁴ to ~10⁻², peak ~day 40.7.

These four together establish the bounded, self-limiting nature.

If a(t) is monotonically rising through day 75, the drag plugin is too weak (not catching the perigee erosion feedback). If a(t) decays from t=0, the SRP plugin is too weak (no gain in the first place).

---

## Setup

Gain anchor:
- Altitude: 700 km
- Inclination: 98.17°
- LTDN: 12.266 h
- Pitch: 24.8°
- Roll: 0°
- RAAN: 285.5° (verify via LTDN→RAAN at epoch 1 Jan 2026 12:00 UT)
- ε₀ = 1×10⁻⁴
- Sail area: 100 m², mass: 10 kg, C_r=1.7, C_D=2.2

Time horizon: **75 days**, step 60 s.

This is also the **Phase 1 validation gate** for the entire pipeline — if this single run reproduces the paper numbers within ±1%, the plugins are correct and we proceed to the rest of the figures.

---

## Acceptance gate

| Quantity | Paper value | Time | Tolerance |
|---|---|---|---|
| a₀ | 7078.137 km | t=0 | exact |
| a peak | 7098.211 km | day 26.50 | ±1% on value, ±2 days on time |
| a final (day 75) | 7064.717 km | day 75 | ±1% |
| h_a peak | 864.548 km | day 39.50 | ±2% |
| h_p min | 546.370 km | day 42.17 | ±2% |
| e peak | 2.176×10⁻² | day 40.72 | ±5% |

---

## Runner

`runners/run_fig9_long_horizon.py`

- Build gain-anchor scenario.
- Propagate 75 days.
- Extract Classical Elements at 60 s.
- Compute h_a = a(1+e) − R_earth, h_p = a(1−e) − R_earth.
- Save `results/fig9/elements_75d.csv` with columns `t_sec, t_days, a_km, e, ha_km, hp_km`.

---

## Plot

`post/plot_fig9_elements.py`

- 4-panel figure (one per element): a(t), h_a(t), h_p(t), e(t).
- X-axis (shared): time [days], 0–75.
- Annotate paper-reported peak/min times and values.
- Save to `reproduced_figures/fig9_elements_75d.png`.

Visual diff target: `Figures/fig9_rect.png`.

---

## Why this figure runs first

This single 75-day case exercises:
- The full orbital propagation loop (J₂ + SRP plugin + drag plugin).
- Eclipse hook (umbra is exercised many times across 75 d).
- Inertial-attitude vector (constant for whole run).
- Long-horizon stability (numerical drift would show up by day 75).
- All four orbital elements of interest.

If this run passes, every other figure becomes a parameter-sweep wrapper around this same machinery. If it fails, the failure is in the plugins/core, and there is no point running any of the other figures.
