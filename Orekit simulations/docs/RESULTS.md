# RESULTS — Orekit validation of the manuscript's claims

## Revision update (October 2026)

The sections below were written for the submitted manuscript and are kept as a
record. The revision (`../../STK simulations/docs/REVISION_NOTES.md`) changed
three things, and the current numbers in `../results/*.json` supersede the
headline values quoted further down (flagged in place with
"*Superseded — see Revision update*").

**What changed**

1. *Atmosphere table corrected.* The open-source `_ATM_TABLE` paired the
   US-1976 base densities with scale heights shifted by one layer, giving the
   discontinuous profile recorded under V3 (×1.198 at 700 km, ×1.206 at
   800 km). It is now interpolated exponentially between the tabulated US-1976
   values and is continuous (3.070×10⁻¹⁴ kg/m³ at 700 km, 1.136×10⁻¹⁴ at
   800 km). `orekit_core`'s `US1976Atmosphere` delegates to the same function,
   so V2–V9 and the runners all inherit the fix.
2. *Two STK configuration errors found and corrected.* The Astrogator initial
   state carried a default 50 kg fuel tank (STK propagated a 60 kg vehicle —
   the "−7 km" decay), and the attitude quaternion was passed scalar-first to
   a scalar-last API (plate normal ~80° off the Sun — the "0 m²" finding).
   With both fixed STK reproduces the SRP response (14 d, J2 + N-plate SRP,
   800 km: STK +15.554 km vs open-source +15.565 km; effective SRP area
   81.97 m² at epoch) and the gain (full model, 14 d: +6.441 vs +5.846 km;
   75 d peak +12.92 vs +10.60 km). Corrected STK spherical drag: −60.295 km
   (700 km) and −17.678 km (800 km) vs −70.564 / −18.547 km open-source,
   ratios 0.854 / 0.953 — explained by STK's co-rotating atmosphere and
   geodetic altitude (V6 factors below) to within 1.5% / 3%.
3. *Anchor moved* to **800 km, LTAN 14.0 h, pitch +35°** (from 700 km /
   12.27 h / +24.8°), and "LTDN" renamed **LTAN** throughout.

**New headline numbers**

| item | value |
|---|---|
| V2, 14-day J2 + spherical drag, RK4 30 s, Orekit = open-source | 700 km **−69.872 km** (max&#124;diff&#124; 4.0×10⁻¹⁰), 800 km **−18.382 km** (2.8×10⁻¹⁰); orbit-averaged −70.009 / −18.454 km |
| V4, effective Sun-facing area at the 24.8° pitch | Orekit 90.76 m² (analytic 90.78); STK, corrected, 81.97 m² at the 35° anchor |
| V6, 700 km: co-rotation / geodetic / both / Harris-Priester / NRLMSISE-00 | −72.280 (×1.034) / −57.037 (×0.816) / −58.815 (×0.842) / −494.745 (×7.081, re-entry day 10.45) / −179.859 km (×2.574) |
| V6, 800 km | −18.817 (×1.024) / −16.568 (×0.901) / −16.953 (×0.922) / −57.843 (×3.147) / −29.174 km (×1.587) |
| V7, DP853 + eclipse-event reference, 800 km anchor | full model **+5.9401 km**, umbra off −10.5864 km, drag only −9.8989 km |
| V7, RK4 ladder, full model (120 / 60 / 30 / 15 / 7.5 / 5 / 2.5 s) | +6.068 / +7.229 / +6.127 / +5.996 / +5.971 / +5.964 / +5.957 km; observed order 0.94 (continuous cases converge by 30 s) |
| V8, gain case 800 km (pitch 35°, RK4 30 s, 14 d) | open-source fixed-1 AU +5.438 vs Orekit analytic Sun +5.605 km (max&#124;diff&#124; 0.181); open-source 1/d² +5.933 vs Orekit DE-440 +6.127 km (0.194); ephemeris effect 0.522 km |
| V8, former anchor 700 km (pitch 24.8°) | −21.478 vs −21.180 km (0.299); −21.158 vs −20.842 km (0.318); ephemeris effect 0.355 km |
| V9, analytic secular drag integral | 700 km −63.938 vs propagated −69.872 km (8.5%); 800 km −17.617 vs −18.382 km (4.2%) |
| LTAN × pitch map, 800 km (`results/revision/orekit_map_compare.json`) | Orekit 24×19 subset of the 48×37 Python grid, 456 common cells: **82/82** positive cells (sign agreement 1.0), RMS diff 0.029 km (0.068 km on positive cells), max 0.236 km, peak 5.753 vs 5.776 km, both at LTAN 14.0 h / pitch 30° |
| eclipse causality, 30 d | 800 km / 35°: ON +10.33 km, OFF −28.53 km; 700 km / 24.8°: ON −90.66 km, OFF −459 km |
| 75-day transient, 800 km gain case | peak **+10.95 km on day 37.9**, final −2.371 km, e 0.01225, apogee 885.6 km, perigee 709.7 km (open-source: +10.86 km on day 38.1, final −2.69 km); 700 km former anchor re-enters, −412.5 km at day 39.3 |
| one-orbit SRP power, 800 km anchor (node-to-node, 6052 s, 5 s sampling) | umbra 32.0%, sign-selectivity 77.6%, work eclipse ON +309.7 J/kg, OFF +0.77 J/kg (open-source +310.3 / +1.4 J/kg) |
| V10 space weather, 800 km, DP853, 14 d — Δa_max (SRP on) / Δa(14 d) (SRP off) | US-1976 +5.940 / −9.899; NRLMSISE-00 low (F10.7 = 70, Ap = 4) +13.178 / −2.327; moderate (140, 15) +2.215 / −12.724; high (200, 40) 0 (Δa −45.455) / −59.583; CSSI file, Jan 2026 +0.500 / −14.426 km |
| V10 space weather, 700 km | US-1976 0 (−13.766) / −31.152; low +10.685 / −4.685; moderate 0 (−30.872) / −45.154; high: re-entry within 14 d, both; CSSI 0 (−38.517) / −52.777 km |

The conclusions that survive unchanged: the force-law port is exact (V1), the
sign flip under eclipse removal reproduces, the gain is transient and
self-limiting, and the binary umbra makes fixed-step RK4 converge at ~first
order. What no longer holds: "STK is the outlier" (both STK errors were ours),
and the −84 km / ×5.9 / +4.85 km / +8.2 km / +8.5 km figures below.

---

Every number below is produced by the scripts in this directory and stored in
`../results/*.json`. STK figures are quoted from the existing STK study in this
repository and were **not** re-run here: STK 13 with an Astrogator licence is
Windows-only.

Environment: Orekit 13.1.7 (Hipparchus 4.0.3) via `orekit_jpype` 13.1.7.0 and
JPype 1.7.1, CPython 3.14.6, OpenJDK 21.0.11, Arch Linux.

---

## Bottom line

> *Superseded — see Revision update:* items 2–5 quote pre-revision numbers
> (−84.040 km → −69.872 km; STK's −7 km and 0 m² were STK build errors, now
> −60.295 km and 81.97 m²; ×5.89 → ×7.08; the 30 s / 60 s overstatement is now
> 3.1% / 22% against a DP853 reference of +5.9401 km at the 800 km anchor).

1. **The port is exact.** Orekit's gravity, drag, SRP and eclipse flag reproduce
   the paper's own force code to between 3×10⁻¹⁴ and 3×10⁻¹⁷ relative, at every
   state along a real orbit.
2. **Orekit corroborates the open-source propagator and localises the STK
   discrepancy.** The 14-day propagated mean semi-major axis agrees to
   3.7×10⁻¹⁰ km, including the −84.040 km drag decay at 700 km that STK
   reported as −7 km. The disagreement is therefore attributable to STK's drag
   application, not to the open-source implementation.
3. **Orekit passes the test STK failed.** Its N-plate SRP model does consume an
   inertially-fixed attitude: effective Sun-facing area 90.8 m² at the anchor
   pitch against STK's reported 0 m², and an SRP-only 14-day propagation gives
   +14.61 km against −0.012 km for J2 alone.
4. **The manuscript's three candidate explanations for the drag gap are all too
   small.** Co-rotation ×1.035, geodetic altitude ×0.810, both ×0.836,
   element definition <1%. The atmosphere *model* spans ×1.33 to ×5.89.
5. **New numerical caveat.** A binary umbra makes the SRP force discontinuous;
   fixed-step integration converges at ≈1st rather than 4th order and overstates
   the gain — by 3.6% at Δt = 30 s and 27% at Δt = 60 s.

---

## V1 — component gates (`v1_component_gates.py`)

198 states along one orbit at the 700 km gain anchor. Orekit force models vs the
paper's own code, evaluated at identical states with a shared Sun position.

| component | max relative vector difference |
|---|---|
| gravity (Newtonian + J2OnlyPerturbation vs `gravity_j2_eci`) | 2.79×10⁻¹⁷ |
| drag (`DragForce` + N-plate vs `drag_acceleration_eci`) | 3.22×10⁻¹⁴ |
| SRP (`RadiationPressureModel` + N-plate vs `nplate_srp_acceleration_eci`) | 1.04×10⁻¹⁵ |

Eclipse-flag mismatches: **0 / 198** (0 boundary-quantisation samples).
Plate normal recovered from the propagated attitude vs the frozen sail normal:
**0.0** (exact).
SRP cos²α law error over 128 lit samples: 1.37×10⁻¹⁵.

### G6 — the difference that is *not* controlled out

The gates above share a Sun position, so they isolate the force law. In a
propagated run the tools use their own:

- DE-440 vs the paper's analytic Sun, max direction difference over 75 days:
  **0.369°**
- true Earth–Sun distance vs the paper's fixed 1 AU: up to **1.67%**, i.e. a
  **3.4% flux difference**. The epoch (1 Jan 2026) is within days of perihelion,
  so the reduced model understates the solar flux at the start of every run.

## V2 — propagated cross-validation (`v2_crossvalidation.py`)

14 days, fixed-step RK4 at Δt = 30 s in Cartesian coordinates, spherical drag,
no SRP, A/m = 10 m² kg⁻¹, C_D = 2.2. Mean SMA by ascending-node sampling.

> *Superseded — see Revision update:* with the corrected atmosphere table the
> J2 + drag rows are −69.872 km (700 km) and −18.382 km (800 km), and the
> corrected STK values are −60.295 / −17.678 km.

| configuration | Orekit | open-source | max&#124;diff&#124; | STK (reported) |
|---|---|---|---|---|
| J2 only, 700 km | −0.011983 km | −0.011983 km | 2.57×10⁻¹⁰ km | < 0.05 km agreement |
| J2 only, 800 km | −0.011283 km | −0.011283 km | 2.77×10⁻¹⁰ km | < 0.05 km agreement |
| J2 + drag, 700 km | **−84.040310 km** | **−84.040310 km** | 3.66×10⁻¹⁰ km | **−7 km** |
| J2 + drag, 800 km | −21.897976 km | −21.897976 km | 2.06×10⁻¹⁰ km | not quoted |

Switching the mean-element definition from node sampling to an orbit-averaged
energy mean moves the 700 km endpoint from −84.040 to −84.669 km (0.75%).

**Read this honestly:** the two propagators share the US-1976 density
tabulation (that is what the model *specifies*) and the integration scheme and
step. What is independently exercised is Orekit's orbit and frame handling,
attitude provider, force assembly from a panel geometry, shadow model and Sun
ephemeris. Sub-micron agreement is strong evidence about force assembly and
coordinate handling, weaker evidence about the atmosphere — which V6 addresses.

## V3 — instantaneous drag at a matched state (`v3_instantaneous_drag.py`)

| | 700 km | 800 km |
|---|---|---|
| geocentric altitude of the epoch state | 699.292 km | 799.282 km |
| speed | 7505.0 m/s | 7452.6 m/s |
| density, Orekit = open-source | 3.7073×10⁻¹⁴ | 1.3785×10⁻¹⁴ kg/m³ |
| density at the *reference* altitude | 3.0700×10⁻¹⁴ | 1.1360×10⁻¹⁴ kg/m³ |
| &#124;a_drag&#124; spherical, Orekit = open-source | 2.2970×10⁻⁵ | 8.4221×10⁻⁶ m/s² |
| &#124;a_drag&#124; N-plate | 1.8027×10⁻⁵ | 6.6034×10⁻⁶ m/s² |
| relative difference Orekit vs open-source | 1.5×10⁻¹⁶ | 2.0×10⁻¹⁶ |

STK reported 3.2×10⁻¹⁴ kg/m³ and 1.9×10⁻⁵ m/s² at 700 km.

> *Superseded — see Revision update:* the discontinuity described next was the
> scale-height defect, since fixed; the profile is now continuous and equals
> the US-1976 table at 700 km (3.070×10⁻¹⁴) and 800 km (1.136×10⁻¹⁴ kg/m³).

**A fragility worth recording:** the paper's 16-segment piecewise-exponential
fit anchors each layer at its own floor with its own scale height, so it is
**discontinuous at the layer boundaries** — by a factor 1.198 across 700 km and
1.206 across 800 km. The study orbit (e = 10⁻⁴, true anomaly 0) starts just
*below* the 700 km boundary and samples the denser layer. Quoted at exactly
700.000 km the density is within 4.1% of STK's; quoted at the sampled state it
is 15.9% higher. Any LEO drag comparison at a round altitude should say which
side of a layer boundary it was evaluated on.

## V4 — SRP under a passively fixed attitude (`v4_srp_attitude_coupling.py`)

**This is the test STK Astrogator failed.**

> *Superseded — see Revision update:* STK's "0 m²" was a quaternion
> component-order error in the STK build; corrected, STK gives 81.97 m² at the
> 800 km / 35° anchor and reproduces the SRP response to 0.1%.

| | Orekit | STK (reported) |
|---|---|---|
| plate normal recovered from the propagated attitude | matches to 1.24×10⁻¹⁶ | — |
| effective Sun-facing area at the 24.8° anchor pitch | **90.778 m²** | **0 m²** |
| SRP force at pitch 0 / pitch 90° | 8.0185×10⁻⁴ N / 0 N | 0 N |
| flat-plate law error over 0–90° pitch | 1.81×10⁻¹⁴ | — |
| 14-day propagation, J2 only | −0.0120 km | −0.0120 km |
| 14-day propagation, J2 + N-plate SRP | **+14.6096 km** | identical to J2 only |

## V5 — SRP calibration gate (`v5_calibration_gate.py`)

α sweep, Orekit N-plate (0.3, 0.7, 0) vs the reduced C_r cos²α model:
worst magnitude deviation for α ≤ 45° is **1.55%** — the manuscript reports 1.6%
from its own offline check. Direction offset grows to 35° at α = 45°, which is
the physical content of the reduced model, not a disagreement: the N-plate
carries an along-normal specular component the Sun-line form does not.

One orbit at the 700 km anchor (5 s sampling, 35.6% umbra):

| quantity | value |
|---|---|
| peak &#124;SRP power&#124;, Orekit N-plate / reduced model | 4.947×10⁻¹ / 4.923×10⁻¹ W/kg (ratio 1.0049) |
| power-profile correlation | 0.9699 |
| net per-orbit SRP work, N-plate, umbra **on** | **+292.76 J/kg** |
| net per-orbit SRP work, N-plate, umbra **off** | +2.73 J/kg |
| net per-orbit SRP work, reduced Sun-line model | +0.95 J/kg |
| eclipse sign-selectivity | 65.6% (manuscript Fig. 4: 85.7%) |

The umbra-off value confirms the manuscript's central claim exactly: without
shadowing the orbit-averaged SRP work cancels.

## V6 — what actually drives the drag spread (`v6_drag_decomposition.py`)

14-day Δa (node-sampled), J2 + spherical drag, no SRP. Each row changes one
thing and holds everything else fixed.

> *Superseded — see Revision update:* current factors are ×1.034 / ×0.816 /
> ×0.842 / ×7.081 / ×2.574 at 700 km and ×1.024 / ×0.901 / ×0.922 / ×3.147 /
> ×1.587 at 800 km (baselines −69.872 / −18.382 km); the "factor of twelve"
> gap to STK was the default fuel tank, and the corrected STK/open-source
> ratios (0.854 / 0.953) are explained by the co-rotation + geodetic rows.

| configuration | 700 km | ×baseline | 800 km | ×baseline |
|---|---|---|---|---|
| baseline (US-1976, geocentric, no co-rotation) | −84.040 km | 1.000 | −21.898 km | 1.000 |
| + co-rotating atmosphere | −86.972 km | 1.035 | −22.420 km | 1.024 |
| + geodetic (WGS-84) altitude | −68.092 km | 0.810 | −18.825 km | 0.860 |
| + both | −70.286 km | 0.836 | −19.312 km | 0.882 |
| Harris-Priester (Orekit built-in) | −494.745 km † | 5.887 | −57.843 km | 2.641 |
| NRLMSISE-00 (Orekit built-in, CSSI space weather) | −180.662 km | 2.150 | −29.216 km | 1.334 |

† reentered on day 10.45.

**None of the manuscript's three candidates can bridge a factor of twelve**, and
two of the three push the decay the wrong way. The atmosphere *model* moves it
by factors of several. Since every alternative atmosphere *increases* the decay
while STK's is twelve times smaller, the residual difference is most consistent
with the density STK actually applied being well below the tabulated US-1976
profile — consistent with the note in the STK study's `docs/PHASE1_FINDINGS.md`.

## V7 — step-size convergence of an eclipse-gated force (`v7_eclipse_discontinuity.py`)

14-day run at the reproduced 800 km gain geometry. Metric is the 14-day
endpoint, because the two continuous-forcing configurations decay monotonically
and their Δa_max is identically zero.

> *Superseded — see Revision update:* at the revised anchor (LTAN 14.0 h,
> pitch 35°) the DP853 + eclipse-event reference is +5.9401 km (umbra off
> −10.5864, drag only −9.8989 km); RK4 30 s gives +6.127 km (+3.1%), 60 s
> +7.229 km (+22%), observed order 0.94.

| Δt | full model (eclipse-gated) | SRP, umbra off | drag only |
|---|---|---|---|
| 120 s | +4.888 km | −19.609 km | −19.367 km |
| 60 s | +6.157 km | −11.859 km | −12.020 km |
| 30 s | +5.022 km | −11.623 km | −11.783 km |
| 15 s | +4.893 km | −11.615 km | −11.767 km |
| 7.5 s | +4.868 km | −11.617 km | −11.769 km |
| 5 s | +4.861 km | −11.617 km | −11.769 km |
| 2.5 s | +4.854 km | −11.617 km | −11.769 km |
| **DP853 + eclipse events** | **+4.850 km** | −11.617 km | −11.769 km |

The two continuous configurations reach their converged value by Δt = 30 s and
show the scheme's nominal fourth-order behaviour. The eclipse-gated case does
not: at Δt = 30 s — the step the open-source propagator uses — it overstates the
converged gain by 3.6%, and at Δt = 60 s by 27%. The coarse-step error is also
**erratic rather than asymptotic**: Δt = 120 s happens to land closer to the
truth than Δt = 60 s, because the error depends on where in each shadow crossing
the step boundary falls. Accuracy therefore cannot be inferred from step size in
the usual way for this problem.

## Reproduction of the gain regime (`runners/`)

All runs use the adaptive integrator with eclipse event detection.

> *Superseded — see Revision update:* the three subsections below predate the
> atmosphere fix and the move to pitch +35° ("LTDN" is now "LTAN"). Current
> values: eclipse ON +10.33 km / OFF −28.53 km at 30 d; one-orbit work
> +309.7 / +0.77 J/kg (selectivity 77.6%); 75-day peak +10.95 km on day 37.9,
> final −2.37 km.

### Eclipse causality (30 days)

| case | eclipse | Δa_max | Δa(30 d) |
|---|---|---|---|
| gain case, 800 km, LTDN 14 h, pitch 34° | ON | +8.213 km | +8.213 km |
| gain case, 800 km, LTDN 14 h, pitch 34° | OFF | 0 | **−31.948 km** |

The sign flip reproduces, and closely matches the open-source result
(ON +7 km, OFF −31 km).

### One-orbit SRP power, 800 km gain case

| quantity | Orekit | manuscript |
|---|---|---|
| umbra fraction | 32.0% | — |
| eclipse sign-selectivity | 76.8% | 85.7% (Fig. 4) |
| net per-orbit SRP work, eclipse ON | **+309.31 J/kg** | +799 J/kg (Fig. 5) |
| net per-orbit SRP work, eclipse OFF | +0.78 J/kg | −9.7 J/kg (Fig. 5) |

Two independent propagators therefore agree both that the mechanism is real and
that the reduced model overstates its magnitude by roughly a factor 2.6.

### 75-day transient, 800 km gain case

Δa peaks at **+8.476 km on day 35.18**, then falls to **−7.108 km by day 75**.
Eccentricity grows 1.4×10⁻⁴ → 1.24×10⁻², apogee rises 801.0 → 881.7 km and
perigee erodes 799.0 → 704.1 km. This is the transient, self-limiting signature
the manuscript describes, reproduced independently (open-source: +7.3 km at
day 34).
