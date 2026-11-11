# Revision notes — Acta Astronautica AA-D-26-02719 (October 2026)

Three defects were found and fixed while answering the reviewers. All results
quoted in the revised manuscript were regenerated after these fixes
(`runners/rev_*.py`, `validation/rev_stk_*.py`, `results/revision/`).

## 1. STK Astrogator: default fuel load (drag "8x too weak")

The Astrogator *Initial State* segment carries a fuel tank whose default
`FuelMass` is 50 kg. Astrogator adds it to `DryMass` when it evaluates drag and
SRP, so the submitted STK build propagated a 60 kg vehicle (A/m = 1.67 m²/kg)
while every read-back property (`DryMass` 10 kg, `DragArea` 100 m², `Cd` 2.2,
density 3.2e-14 kg/m³ at 700 km) looked right. Diagnosis:
`validation/rev_stk_retest.py` (read-back of effective properties) and
`validation/rev_stk_probe.py` (vary `DryMass`, `DragArea`, `Cd`, tank, `K1`
one at a time: decay scales with area and Cd, barely with `DryMass`, and jumps
x6 when the tank is zeroed). Fix: `core/astrogator_mcs.build_satellite`
zeroes `FuelTank.FuelMass` and `MaximumFuelMass` (`zero_fuel=True`).

## 2. STK Astrogator: quaternion component order (N-plate "ignores attitude")

`IAgOrientationQuaternion.AssignQuaternion` takes `(qx, qy, qz, qs)` — scalar
last. The build passed `(qs, qx, qy, qz)`. The resulting attitude put the
plate normal ~80° from the Sun (effective SRP area 16 m² instead of
A cos α = 83 m²), which is the "SRPArea = 0 / N-plate SRP does not use the
attitude" finding of `docs/PHASE1_FINDINGS.md`. With the correct order STK's
effective SRP area is 82.96 m² at epoch and the 3-day J2+SRP response agrees
with the open-source propagator to 0.5% (`results/revision/stk_probe.json`).
Fix: `core/astrogator_mcs.py` and `core/scenario_builder.py`.

## 3. Open-source propagator: atmosphere table scale heights

`plugins/flatplate_drag_hpop._ATM_TABLE` paired the US Standard Atmosphere
1976 base densities with scale heights shifted by one layer (e.g. 124 km for
700–800 km, which is the 800–900 km value). The profile was therefore
discontinuous at the layer boundaries (x1.198 at 700 km, x1.206 at 800 km) and
up to 21% too dense just below each boundary — exactly where a near-circular
orbit at a round altitude samples it. The table is now interpolated
exponentially between the tabulated US-1976 values, which is continuous and
reproduces the table exactly at the nodes (3.070e-14 at 700 km, 1.136e-14 at
800 km). Orekit's `US1976Atmosphere` delegates to the same function, so the
Orekit cross-validation inherits the fix.

Effect: 14-day spherical-drag decay at 700 km changes from -84.0 km to
(see `results/revision/stk_validation.json`), bringing the open-source
propagator to within a few per cent of the corrected STK run.

## 4. Smaller points found by the code review of the revision scripts

- **One-orbit statistics** (`runners/rev_cases.py`): the dense one-orbit runs cover
  1.05 nodal periods; the SRP-power and cumulative-work statistics and figures are
  now truncated at the first ascending-node crossing, so they span exactly one
  node-to-node orbit (nodal period 100.8 min at 800 km).
- **Mean-element reference**: the propagator samples the osculating elements at
  ascending-node crossings detected from negative-to-positive z, so the first sample
  is one nodal period after epoch (the epoch state itself sits on the node but is not
  counted). All Delta a quantities are referenced to that first node; the first
  orbit's secular change (|da| < 0.1 km) is excluded. Stated in the manuscript.
- **STK comparison window** (`validation/rev_stk_validation.py`): both tools are
  propagated for 14 d + one period and compared between centred one-period means
  at t = T/2 and t = T/2 + 14 d, so the quoted change spans exactly 14 days.
- **STK drag conventions**: Astrogator applies a co-rotating atmosphere and
  evaluates the density at geodetic altitude; the open-source model uses the
  inertial velocity and geocentric altitude. Orekit, switching these one at a time
  (`v6_drag_decomposition`), gives x1.034/x0.816 (700 km) and x1.024/x0.901
  (800 km), combined x0.842/x0.922 — which accounts for the corrected STK/open-source
  ratios (0.855 / 0.953) to within 1.5 % / 3 %. The density read-back ratio
  (0.887 / 0.937 at the same geocentric altitude) is the geodetic-altitude effect.
- **Solar flux**: the open-source plate uses P_1AU = 4.5605e-6 N/m^2 (1367 W/m^2);
  the STK N-plate SRP `MeanFlux` was 1361 W/m^2 and is now set to the same 1367.2
  W/m^2 so the SRP comparison is like for like.
- `results/revision/stk_probe.json` and `stk_retest.json` are the diagnostic
  snapshots of the SUBMITTED build; `rev_stk_probe.py` re-creates that build
  explicitly (`zero_fuel=False`, scalar-first quaternion) so re-running it
  reproduces them.
- `runners/rev_convergence.py` now reads the Orekit DP853 reference from
  `v7_eclipse_discontinuity.json` (`reference` block) instead of a hard-coded value.

## What did not change

Gravity (J2), the N-plate SRP decomposition, the eclipse model, the attitude
construction, the LTAN→RAAN mapping (renamed from "LTDN"; the formula was
already the ascending-node one) and the mean-element extraction are unchanged
and were verified against Orekit to 1e-10 km (`../Orekit simulations/`).

## 5. Inclinations

The submitted Table 1 listed incorrect Sun-synchronous inclinations
(600/700/800/900 km -> 97.92/98.04/98.17/98.31 deg); the correct values from the
J2 nodal-rate formula are 97.79/98.19/98.60/99.03 deg. The simulations use
98.17 deg at 700 km (within 0.02 deg of exact) and 98.31 deg at 800 km (0.29 deg
below exact: the node lags the mean Sun by 0.033 deg/day, i.e. ~10 min of local
time over 75 days). Kept as is -- immaterial for the 14-day maps, small for the
75-day runs -- and stated in the manuscript (Section 4) as "near-Sun-synchronous".

## 6. Post-build fixes after reviewing the Editorial Manager PDF (18 October 2026)

EM's own LaTeX build of the uploaded source (AA-D-26-02719_R1.pdf, 159 pages) was compared page by
page with the local PDFs. The compile itself was faithful; every blemish found was in the sources and
has been fixed:

- `Sections/paramspace.tex`: the bare equation reference "required through 24." now reads
  "required through Eq. (24)".
- `Sections/validation.tex`: Table 9 (Orekit cross-validation) ran one row past the text block, so the
  page number printed inside its last row; six row labels were shortened and the table now fits.
- `main_aa.tex` / `Sections/scope.tex`: Figure 1 was forced to flush by a FloatBarrier at the start of
  Section 2, stranding the heading above 40% of blank page; the figure is now `[htbp]` and the barrier
  is gone.
- `main_aa.tex`: the Funding section began "Funding: ..." under a "Funding" heading.
- `cover_letter.tex`: the signature block was orphaned on a second page; margins and spacing were
  tightened so the letter is one page.
- Marked-up copy: latexdiff drops labels inside deleted floats, so five deleted sentences printed
  "Figure ??", and one deleted citation of the removed duplicate reference printed "[?]";
  `scripts/fix_diff_refs.py` (run by `scripts/build_revision.sh`) now substitutes the numbers those
  labels had in the as-submitted PDF. The new bibliography had been inlined by `latexdiff --flatten`
  and marked up as one unbreakable insertion whose lines ran off the page; both .bbl files are now
  kept out of latexdiff's way so the diff runs bibtex itself, and `\emergencystretch` is set, which
  took the diff from 132 overfull lines to none.

The three changed files (flattened `main_aa.tex`, `main_aa_diff.pdf`, `cover_letter.pdf`) were
re-uploaded through Edit Revision and the EM PDF rebuilt; the revision remains unapproved for the
author's final check.
