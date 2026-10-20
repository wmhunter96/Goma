# Design review — Sesame DevKit Carrier v1

Independent review with [kicad-happy](https://github.com/aklofas/kicad-happy) (commit 6a91aaa, 2026-10-14), run from a local
clone against `sesame-devkit-carrier.kicad_sch`, `.kicad_pcb` and `gerbers/`, alongside KiCad ERC/DRC and `audit.py`.

## Verdict

**Ready to order.** One real issue was found (mounting-hole screw heads at the board edge) and fixed. Every other finding
is either expected for this design, a tool heuristic that doesn't apply, or a prototype-stage BOM note.

| Check | Result |
|---|---|
| KiCad ERC | 0 errors, 0 warnings |
| KiCad DRC + schematic parity | 0 violations, 0 unconnected pads, 0 footprint errors |
| Schematic netlist vs board | 86/86 pins match |
| `audit.py` | all checks pass |
| kicad-happy gerber analyzer | 0 findings |
| kicad-happy thermal analyzer | 0 findings (skipped: no SMD power parts on the carrier itself) |

## Analyses run

| Analyzer | Ran | Notes |
|---|---|---|
| `analyze_schematic.py` | yes | 28 findings |
| `analyze_pcb.py --full` | yes | 53 findings |
| `cross_analysis.py` | yes | 1 finding |
| `analyze_gerbers.py` | yes | 0 findings |
| `analyze_thermal.py` | yes | 0 findings |
| `analyze_emc.py` | yes | 29 findings, score 70/100 |
| SPICE | **skipped** | no simulator installed (ngspice/LTspice/Xyce). The only analog subcircuit is the 100k/22k divider + 100 nF, checked by hand: ratio 0.180, 12.6 V → 2.27 V, corner ≈ 87 Hz |
| Lifecycle audit | **skipped** | needs MPNs + DigiKey API access |
| Datasheet sync | **skipped** | no MPNs; datasheets were checked manually instead (see README "Verified against official documentation") |

## Fixed

| Finding | Detail | Fix |
|---|---|---|
| PM-002 `H5 courtyard overhangs board edge by 0.55mm` | A 5.0 mm M2.5 pan head at H5 would overhang the bottom edge. Checking all holes showed H1 and H3 also overhung the top edge slightly. Holes were sized for 4.5 mm socket heads (the screws actually used), but KiCad's courtyard assumes a 5.0 mm pan head. | H1, H3, H5 moved so every M2.5 hole is ≥ 2.95 mm from the edge (courtyard on the board, ≥ 0.75 mm around a socket head); servo 5V rail dip lowered to keep H1's 3 mm copper keep-out. `audit.py` checks socket-head clearance to the edge (≥ 0.75 mm of board around every M2.5 head). |

## Changed after review

| Change | Detail |
|---|---|
| Short-risk pass | Plain-Python analysis of every different-net copper pair, ranked by what a short would do. Two fixes: C3's pads (battery + to GND) narrowed to 1.2 mm along the pitch, so the gap went 0.40 → 0.80 mm (it had been the tightest pad gap on the board; now the narrowest anywhere is 0.80 mm); the 12.6 V battery-sense tap no longer threads between socket pins (it passed 0.22 mm from D13) but runs from C3 through the open space between the DevKit's socket rows to R1. Re-ran ERC, DRC + parity, audit and every kicad-happy analyzer: no new findings. |
| Power-trace spacing | Wide 5V/battery traces moved off neighbouring pins: 5V servo feed 0.33 → 2.2 mm from the DevKit's GND/3V3 socket pins, battery + 0.30 → 0.70 mm from BAT−, regulator output 0.25 → 0.53 mm from BAT+ (that 10 mm run is 1.7 mm wide to fit between the module pins and BAT+). `audit.py` now requires power traces ≥ 0.4 mm from other nets (closest: 0.42 mm, masked trace under the regulator's own pins). |
| Signal traces widened | All signal traces 0.3 → 0.5 mm for margin against etch variation and rework; 3 short segments (11.9 mm total, after the short-risk pass) neck to 0.4 mm where they thread between 2.54 mm socket pins (0.22 mm clearance each side). Narrowest trace on the board went 0.3 → 0.4 mm. Re-ran ERC, DRC + parity, audit and every kicad-happy analyzer: no new findings. |

## Reviewed, no change needed

| Finding | Why it doesn't apply |
|---|---|
| KO-001 holes "inside keepout zone" (7) | Those keep-outs are the 3 mm screw-head copper keep-outs drawn *around* each hole on purpose. |
| PM-001 courtyard overlaps J1/J3/J4/J5 and S2–S8 (8), U1/HP1 | Headers deliberately side by side on the 2.54 mm grid; documented in `sesame-devkit-carrier.kicad_dru`, real body spacing checked by `audit.py`. HP1 is Pololu's own hole beside its header. |
| PM-002 J1–J5, S1 0.35–0.73 mm from edge | That's the plastic header body; copper pads are ≥ 1.27 mm from the edge (PCBWay needs 0.25 mm). |
| PU-001 U1 EN missing pull-up | Pololu documents a 100 kΩ pull-up to VIN on the module; EN is intentionally left unconnected. |
| RS-001 VBAT has no declared source | VBAT comes from the battery through the J6 pigtail pads; the regulator input (VBAT_SW) carries a PWR_FLAG. |
| PR-DET U1 "LDO", capacitors "X7R" | Tool classification only: U1 is a switching buck module; C1/C3 are aluminium electrolytics. No effect on the board. |
| DC-001 C1 8.6 mm from U1 | The Pololu module carries its own input/output capacitors. C1 is a bulk reservoir for servo current surges, not high-frequency decoupling for U1. |
| GP-001 signals with reference-plane gaps (16 errors, 2 warnings) | The 15 "0 %" nets are the 2.8–3.8 mm stubs from the DevKit socket to the servo / I/O headers, where pads leave no room for ground fill between rows. They carry 50 Hz servo PWM and slow GPIO. SDA/SCL (~90 % covered, 100 kHz I2C) and BAT_SENSE (DC) are fine. No high-speed or clock nets on the board. |
| PS-002 "+5V plane split: 8 islands" | There is no +5V plane; +5V is routed as tracks (2 mm servo rail on both layers). The tool appears to treat the track network as a plane. |
| CG-AUD / IO-002 connector ground ratio, J4 has no ground pin | DevKit sockets have the DevKit's own 2 GND pins. J4 is the spare I/O header; ground and 5V for it are on J5 next to it. |
| EP-AUD / IO-001 no ESD or EMC filtering on connectors | Hobby robot with short internal wiring; the ESP32 has internal ESD diodes. Acceptable for this use. |
| CP-002 "no opposite-layer copper under" parts (23) | Info only: ground fill clearances around through-hole pads. |
| TE-001 no test points | Every net is reachable on a header pin or socket. |
| OR-001 C1 orientation | Cosmetic. |
| CERT-001 wireless module | Applies to selling a product, not a personal build. |
| DS-001 / SS-001 no MPNs | Prototype parts are bought individually (Amazon/Pololu). Specific parts were checked against datasheets by hand; adding MPNs is a future BOM task, not a fab blocker. |

## Manual verification basis

ESP32 datasheet v5.3 (GPIO34 input-only, ADC range, strapping pins), Pololu D24V50F5 product page and dimension drawing
0J1436, Pololu app note 0J16 (LC spikes), DevKit pinout from the AITRIP listing photo plus measured row spacing and antenna
offset, PCBWay capabilities page. Details in README.md.
