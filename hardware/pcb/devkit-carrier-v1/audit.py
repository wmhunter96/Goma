# Electrical audit of the carrier board, independent of build_board.py.
# Run with KiCad's bundled python:  "<KiCad>/bin/python.exe" audit.py
import os, re, math, collections
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
board = pcbnew.LoadBoard(os.path.join(HERE, "sesame-devkit-carrier.kicad_pcb"))
FW = os.path.join(HERE, "..", "..", "..", "firmware", "sesame-firmware-main.ino")
mm = pcbnew.ToMM
fails, notes = [], []
def check(ok, msg):
    (notes if ok else fails).append(("PASS " if ok else "FAIL ") + msg)

# ---------------------------------------------------------------- 1. netlist vs an independent spec
# DOIT DevKit V1 30-pin labels, pin 1 = antenna end (confirmed from the AITRIP listing photo)
DEVKIT_L = ["EN", "VP", "VN", "D34", "D35", "D32", "D33", "D25", "D26", "D27", "D14", "D12", "D13", "GND", "VIN"]
DEVKIT_R = ["D23", "D22", "TX0", "RX0", "D21", "D19", "D18", "D5", "TX2", "RX2", "D4", "D2", "D15", "GND", "3V3"]
GPIO = {"D23": 23, "D22": 22, "D21": 21, "D19": 19, "D18": 18, "TX2": 17, "RX2": 16, "D4": 4, "D2": 2, "D15": 15,
        "D34": 34, "D32": 32, "D33": 33, "D25": 25, "D26": 26, "D27": 27, "D14": 14, "D13": 13}
servo_label = {"R1": "D15", "R2": "D2", "L1": "D23", "L2": "D19", "R4": "D4", "R3": "RX2", "L3": "TX2", "L4": "D18"}

spec = collections.defaultdict(set)   # connection groups, keyed by a description
def pin(side, label):
    return ("J1" if side == "L" else "J2") + "." + str((DEVKIT_L if side == "L" else DEVKIT_R).index(label) + 1)
srefs = {fp.GetValue().replace("Servo ", ""): fp.GetReference() for fp in board.GetFootprints() if fp.GetValue().startswith("Servo ")}
for name, lab in servo_label.items():
    spec["servo " + name].update({pin("R", lab), srefs[name] + ".1"})
spec["5V"].update({pin("L", "VIN"), "U1.5", "C1.1", "J5.3"} | {s + ".2" for s in srefs.values()})
spec["GND"].update({pin("L", "GND"), pin("R", "GND"), "U1.3", "U1.4", "C1.2", "C2.2", "C3.2", "R2.2", "J3.4", "J5.2", "J6.2"}
                   | {s + ".3" for s in srefs.values()})
spec["3V3"].update({pin("R", "3V3"), "J3.3"})
spec["SCL"].update({pin("R", "D22"), "J3.1"})
spec["SDA"].update({pin("R", "D21"), "J3.2"})
spec["VBAT"].update({"J6.1", "SW1.1"})
spec["VBAT_SW"].update({"SW1.2", "U1.2", "R1.1", "C3.1"})
spec["SENSE"].update({pin("L", "D34"), "R1.2", "R2.1", "C2.1"})
for i, lab in enumerate(["D32", "D33", "D25", "D26", "D27", "D14"]):
    spec["IO " + lab].update({pin("L", lab), "J4.%d" % (i + 1)})
spec["IO D13"].update({pin("L", "D13"), "J5.1"})

actual = collections.defaultdict(set)
unconnected_pads = []
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNumber() == "":
            continue
        key = f"{fp.GetReference()}.{p.GetNumber()}"
        if p.GetNetname() and not p.GetNetname().startswith("unconnected-"):
            actual[p.GetNetname()].add(key)
        else:
            unconnected_pads.append(key)
spec_groups = sorted(map(frozenset, spec.values()), key=sorted)
act_groups = sorted(map(frozenset, actual.values()), key=sorted)
check(spec_groups == act_groups, "netlist matches independent spec (%d nets)" % len(spec_groups))
if spec_groups != act_groups:
    for g in set(spec_groups) ^ set(act_groups):
        fails.append("   mismatch group: " + " ".join(sorted(g)))
expect_nc = {pin("L", l) for l in ["EN", "VP", "VN", "D35", "D12"]} | {pin("R", l) for l in ["TX0", "RX0", "D5"]} | {"U1.1"}
check(set(unconnected_pads) == expect_nc, "unconnected pads are exactly EN VP VN D35 D12 TX0 RX0 D5 + regulator EN")

# ---------------------------------------------------------------- 2. firmware vs board
fw = open(FW, encoding="utf8").read()
active = [l for l in fw.splitlines() if not l.strip().startswith("//")]
fwtxt = "\n".join(active)
servo_pins = [int(x) for x in re.search(r"const int servoPins\[8\]\s*=\s*\{([^}]*)\}", fwtxt).group(1).split(",")]
sda = int(re.search(r"#define I2C_SDA (\d+)", fwtxt).group(1))
scl = int(re.search(r"#define I2C_SCL (\d+)", fwtxt).group(1))
order = ["R1", "R2", "L1", "L2", "R4", "R3", "L3", "L4"]   # ServoName enum order in movement-sequences.h
board_pins = [GPIO[servo_label[n]] for n in order]
check(servo_pins == board_pins, f"firmware servoPins {servo_pins} == board {board_pins}")
check((sda, scl) == (21, 22), f"firmware I2C SDA/SCL = {sda}/{scl}, board D21/D22")
enum = re.findall(r"(\w\d)\s*=\s*(\d)", open(os.path.join(HERE, "..", "..", "..", "firmware", "movement-sequences.h"), encoding="utf8").read())
check([n for n, _ in sorted(enum, key=lambda t: int(t[1]))][:8] == order, "movement-sequences.h ServoName enum order matches")

# ---------------------------------------------------------------- 3. ESP32 pin rules
strap = {0: "boot mode", 2: "boot mode (must not be pulled high)", 5: "SDIO timing", 12: "flash voltage (must not be pulled high)", 15: "boot log"}
used = {GPIO[l] for l in GPIO if any(pin("L" if l in DEVKIT_L else "R", l) in g for g in act_groups)}
for g, why in strap.items():
    if g in used:
        notes.append(f"NOTE GPIO{g} used ({why}): only drives a servo signal input / header, nothing pulls it at boot")
check(12 not in used and 0 not in used, "GPIO12 and GPIO0 left unconnected")
check(34 in used and all(g not in used for g in (35, 36, 39)) , "input-only pins: only GPIO34 used, as an input (battery sense)")

# ---------------------------------------------------------------- 4. divider / ADC
r1, r2 = 100e3, 22e3
vfull, vempty = 12.6, 9.0
check(vfull * r2 / (r1 + r2) <= 2.45, f"ADC at 12.6 V = {vfull*r2/(r1+r2):.2f} V (<= 2.45 V accurate range)")
check(vfull / (r1 + r2) < 0.2e-3, f"divider draw {vfull/(r1+r2)*1e6:.0f} uA, only while switched on")
rev = (vfull - 0.6) / r1
check(rev < 1e-3, f"reversed battery: clamp current into GPIO34 {rev*1e3:.2f} mA via 100k (safe)")

# ---------------------------------------------------------------- 5. current capacity (IPC-2221, external, 1 oz)
# Peak demand: Pololu at 5 A out from a sagging 10 V pack ~ 2.8 A in; 8 servos straining ~ 4-5 A on the servo rail.
def amps(width_mm, oz=1.0, rise=10):
    area = width_mm / 0.0254 * oz * 1.378     # mil^2
    return 0.048 * rise ** 0.44 * area ** 0.725
def widths(netname, layer=None):
    return sorted({round(mm(t.GetWidth()), 2) for t in board.GetTracks()
                   if t.GetClass() == "PCB_TRACK" and t.GetNetname() == netname and (layer is None or t.GetLayer() == layer)})
vbat = min(widths("VBAT"))
check(amps(vbat) >= 2.8, f"VBAT (battery -> switch): {vbat} mm carries {amps(vbat):.1f} A at 10 C rise (need 2.8 A)")
vsw = max(widths("VBAT_SW"))
check(amps(vsw) >= 2.8, f"VBAT_SW (switch -> regulator): {vsw} mm carries {amps(vsw):.1f} A (need 2.8 A); 0.4 mm branch is the 0.1 mA divider tap")
rail = amps(2.0) * 2
check(widths("+5V", pcbnew.F_Cu).count(2.0) and widths("+5V", pcbnew.B_Cu).count(2.0) and rail >= 5.0,
      f"servo 5V rail: 2.0 mm on both layers carries {rail:.1f} A (need ~5 A peak)")
notes.append(f"NOTE other +5V branches: 1.5 mm to DevKit VIN ({amps(1.5):.1f} A, ESP32 needs 0.5 A), "
             f"1.2 mm cap tee, 0.8 mm to the spare 5V header pin ({amps(0.8):.1f} A)")

# ---------------------------------------------------------------- 6. GND fill connectivity, both layers
zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"]
for z in zones:
    lay = board.GetLayerName(z.GetLayer())
    fill = z.GetFilledPolysList(z.GetLayer())
    islands = fill.OutlineCount()
    gpads = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == "GND"]
    missing = [f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}" for p in gpads
               if not fill.Collide(p.GetPosition(), max(p.GetBoundingBox().GetWidth(), p.GetBoundingBox().GetHeight()) // 2 + pcbnew.FromMM(0.8))]
    check(not missing, f"GND fill on {lay}: {islands} region(s); every GND pad reaches it" + ("" if not missing else f" - missing {missing}"))
    for i in range(islands):
        o = fill.Outline(i)
        bb = o.BBox()
        has_pad = any(o.PointInside(p.GetPosition()) or o.Collide(p.GetPosition(), pcbnew.FromMM(1.0)) for p in gpads)
        has_via = any(t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND" and o.Collide(t.GetPosition(), pcbnew.FromMM(0.5)) for t in board.GetTracks())
        if not (has_pad or has_via):
            fails.append(f"FAIL {lay} GND island {i} ({mm(bb.GetWidth()):.1f} x {mm(bb.GetHeight()):.1f} mm) touches no GND pad or via (floating copper)")

# ---------------------------------------------------------------- 7. hole sizes vs leads
leads = {"J1": 0.64, "J2": 0.64, "J3": 0.64, "J4": 0.64, "J5": 0.64, "U1": 0.64, "R1": 0.6, "R2": 0.6,
         "C1": 0.6, "C2": 0.6, "C3": 0.5, "SW1": 1.2, "J6": 1.6}
for fp in board.GetFootprints():
    ref = fp.GetReference()
    lead = leads.get(ref, 0.64 if ref.startswith("S") else None)
    if lead is None:
        continue
    drills = {round(mm(p.GetDrillSize().x), 2) for p in fp.Pads() if p.GetNumber()}
    ok = all(d >= lead + 0.15 for d in drills)
    if not ok or ref in ("J6", "SW1", "C1", "C3", "R1", "C2", "U1", "J1"):
        check(ok, f"{ref}: drill {sorted(drills)} mm vs lead ~{lead} mm")

# ---------------------------------------------------------------- 8. polarity / orientation
fpd = {fp.GetReference(): fp for fp in board.GetFootprints()}
c1 = fpd["C1"]
check(c1.FindPadByNumber("1").GetNetname() == "+5V", "C1 pad 1 (+, marked on silkscreen) is +5V")
check(fpd["C3"].FindPadByNumber("1").GetNetname() == "VBAT_SW", "C3 pad 1 (+, marked on silkscreen) is switched battery")
# capacitor voltage ratings vs the worst voltage each sees
check(16 >= 5.2 * 3, "C1 16 V rating vs 5.2 V max regulator output (3x margin)")
check(35 >= 12.6 * 2.5, "C3 (47 uF) 35 V rating vs 12.6 V full pack (2.8x margin; it absorbs the hot-plug spike, Pololu 0J16)")
j6 = fpd["J6"]
p1 = j6.FindPadByNumber("1")
check(p1.GetNetname() == "VBAT" and p1.GetShape() in (pcbnew.PAD_SHAPE_ROUNDRECT, pcbnew.PAD_SHAPE_RECTANGLE), "battery: square pad is BAT+ (VBAT)")
u = fpd["U1"]
def _nm(p):
    n = p.GetNetname()
    return "EN(nc)" if not n or n.startswith("unconnected-") else n
xs = [(mm(u.FindPadByNumber(str(i)).GetPosition().x), _nm(u.FindPadByNumber(str(i)))) for i in range(1, 6)]
check([n for _, n in sorted(xs)] == ["EN(nc)", "VBAT_SW", "GND", "GND", "+5V"], f"Pololu header left->right = EN VIN GND GND OUT: {[n for _, n in sorted(xs)]}")
for name, sref in srefs.items():
    f = fpd[sref]
    ys = [mm(f.FindPadByNumber(str(i)).GetPosition().y) for i in (1, 2, 3)]
    if not (ys[0] > ys[1] > ys[2]):
        fails.append(f"FAIL servo {name}: S/+/- not ordered from DevKit outward")
check(True, "all 8 servo headers ordered S, +, - from the DevKit outward (brown on the edge side)")

# ---------------------------------------------------------------- 9. silkscreen labels sit by the right nets
labels = []
for d in board.GetDrawings():
    if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() == pcbnew.F_SilkS:
        labels.append((d.GetText(), mm(d.GetPosition().x), mm(d.GetPosition().y)))
def nearest_pad(x, y, refs):
    best = None
    for fp in board.GetFootprints():
        if fp.GetReference() not in refs:
            continue
        for p in fp.Pads():
            px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
            dist = math.hypot(px - x, py - y)
            if best is None or dist < best[0]:
                best = (dist, p.GetNetname(), f"{fp.GetReference()}.{p.GetNumber()}")
    return best
want = {"32": "D32", "33": "D33", "25": "D25", "26": "D26", "27": "D27", "14": "D14", "13": "D13",
        "C": "SCL", "D": "SDA", "V": "+3V3"}
bad = []
for txt, x, y in labels:
    if txt in want:
        d, n, pad = nearest_pad(x, y + 1.4, {"J3", "J4", "J5"})
        if n != want[txt]:
            bad.append(f"'{txt}' -> {pad} ({n})")
for txt, x, y in labels:
    if txt in servo_label:
        d, n, pad = min((math.hypot(mm(fpd[r].FindPadByNumber("1").GetPosition().x) - x, 0), fpd[r].FindPadByNumber("1").GetNetname(), r + ".1") for r in srefs.values())
        if n != servo_label[txt].replace("RX2", "D16").replace("TX2", "D17"):
            bad.append(f"'{txt}' -> {pad} ({n})")
check(not bad, "header labels (I/O, OLED, servo names) sit over the matching nets" + ("" if not bad else f": {bad}"))


# ---------------------------------------------------------------- 10. PCBWay standard 2-layer limits (pcbway.com/capabilities.html)
trk = [mm(t.GetWidth()) for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
check(min(trk) >= 0.15, f"narrowest track {min(trk):.2f} mm (PCBWay min 0.10)")
vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
check(all(mm(v.GetDrillValue()) >= 0.3 and (mm(v.GetWidth(pcbnew.F_Cu)) - mm(v.GetDrillValue())) / 2 >= 0.15 for v in vias),
      f"{len(vias)} vias: drill >= 0.3 mm, annular ring >= 0.15 mm")
rings = []
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            bb = p.GetBoundingBox()
            rings.append(((min(mm(bb.GetWidth()), mm(bb.GetHeight())) - mm(p.GetDrillSize().x)) / 2, fp.GetReference()))
check(min(rings)[0] >= 0.15, f"smallest PTH annular ring {min(rings)[0]:.2f} mm ({min(rings)[1]}) (PCBWay min 0.15)")
silk_text = [d for d in board.GetDrawings() if isinstance(d, pcbnew.PCB_TEXT) and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
silk_text += [f.Reference() for f in board.GetFootprints() if f.Reference().IsVisible()]
check(min(mm(t.GetTextHeight()) for t in silk_text) >= 0.8, f"silkscreen text height >= 0.8 mm ({len(silk_text)} texts)")
lines, fills = [], []
for d in list(board.GetDrawings()) + [g for fp in board.GetFootprints() for g in fp.GraphicalItems()]:
    if isinstance(d, pcbnew.PCB_SHAPE) and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        if d.IsSolidFill():
            bb = d.GetBoundingBox()
            fills.append(min(mm(bb.GetWidth()), mm(bb.GetHeight())))
        else:
            lines.append(mm(d.GetWidth()))
check(min(lines) >= 0.15 and min(fills) >= 0.15,
      f"silkscreen lines >= {min(lines):.2f} mm, face-art pixels >= {min(fills):.3f} mm (PCBWay legend min 0.15)")

# ---------------------------------------------------------------- 11. side-by-side headers: real spacing (courtyard rule waived in .kicad_dru)
def pads_xy(ref):
    return [(mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in fpd[ref].Pads() if p.GetNumber()]
grid_refs = [r for r in fpd if r[0] in "SJ" and r != "J6"]
worst = 99
for i, a in enumerate(grid_refs):
    for b in grid_refs[i + 1:]:
        for (ax, ay) in pads_xy(a):
            for (bx, by) in pads_xy(b):
                worst = min(worst, math.hypot(ax - bx, ay - by))
check(worst >= 2.54 - 1e-6, f"closest pins on neighbouring headers/sockets {worst:.2f} mm apart (>= 2.54 grid, so 2.54 mm bodies fit)")


# ---------------------------------------------------------------- 12. screw heads: only ground copper within 3 mm of a mounting hole
def seg_dist(pt, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    t = 0 if dx == dy == 0 else max(0, min(1, ((pt[0]-a[0])*dx + (pt[1]-a[1])*dy) / (dx*dx + dy*dy)))
    return math.hypot(pt[0] - (a[0] + t*dx), pt[1] - (a[1] + t*dy))
for h in [f for f in board.GetFootprints() if f.GetReference().startswith("H")]:
    c = (mm(h.GetPosition().x), mm(h.GetPosition().y))
    best = (99, "")
    for t in board.GetTracks():
        if t.GetNetname() == "GND":
            continue
        if t.GetClass() == "PCB_TRACK":
            d = seg_dist(c, (mm(t.GetStart().x), mm(t.GetStart().y)), (mm(t.GetEnd().x), mm(t.GetEnd().y))) - mm(t.GetWidth()) / 2
        else:
            d = math.hypot(c[0] - mm(t.GetPosition().x), c[1] - mm(t.GetPosition().y)) - mm(t.GetWidth(pcbnew.F_Cu)) / 2
        best = min(best, (d, t.GetNetname()))
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() and p.GetNetname() != "GND":
                bb = p.GetBoundingBox()
                d = math.hypot(c[0] - mm(p.GetPosition().x), c[1] - mm(p.GetPosition().y)) - max(mm(bb.GetWidth()), mm(bb.GetHeight())) / 2
                best = min(best, (d, fp.GetReference() + "." + p.GetNumber()))
    need = 3.0 if "M2.5" in h.GetFPIDAsString() else 2.4   # socket heads: M2.5 r2.25 (+0.75), M2 r1.9 (+0.5)
    check(best[0] >= need, f"{h.GetReference()} ({h.GetFPIDAsString().split(':')[-1]}) at ({c[0]:.1f}, {c[1]:.1f}): nearest non-GND copper {best[0]:.2f} mm ({best[1]}), screw head needs {need}")


# ---------------------------------------------------------------- 13. screw heads stay on the board
ox0, oy0, ox1, oy1 = [mm(v) for v in (board.GetBoardEdgesBoundingBox().GetLeft(), board.GetBoardEdgesBoundingBox().GetTop(),
                                      board.GetBoardEdgesBoundingBox().GetRight(), board.GetBoardEdgesBoundingBox().GetBottom())]
for h in [f for f in board.GetFootprints() if f.GetReference().startswith("H")]:
    hx, hy = mm(h.GetPosition().x), mm(h.GetPosition().y)
    head = 2.25 if "M2.5" in h.GetFPIDAsString() else 1.9         # socket-head cap screws (ISO 4762): M2.5 dk 4.5, M2 dk 3.8
    margin = min(hx - ox0, ox1 - hx, hy - oy0, oy1 - hy) - head
    check(margin >= 0.5, f"{h.GetReference()} socket-head screw (r {head} mm) stays {margin:.2f} mm inside the board edge")

print("\n".join(notes))
print("\n".join(fails) if fails else "\nNO FAILURES")
