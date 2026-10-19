# Generates the Sesame DevKit Carrier PCB (KiCad 10) for a 30-pin, 1.0"-row ESP32 DevKit.
# Run with KiCad's bundled python:  "<KiCad>/bin/python.exe" build_board.py
#
# Layout (69 x 42 mm): the DevKit lies along the board with its antenna end hanging off the left edge,
# so the whole antenna is clear of the carrier. USB points inward (flash the DevKit before plugging it in).
# With the antenna to the left, the DevKit's "right" pin row (servo signals) is on top, so the servo
# headers run along the top edge, each straight above its pin; spare I/O + OLED run along the bottom edge.
# Regulator, bulk cap, switch pads and battery pads fill the right end.
import math
import os
import pcbnew
from pcbnew import VECTOR2I, FromMM
from sesame_ids import symbol_uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sesame-devkit-carrier.kicad_pcb")
FPLIB = os.path.join(os.path.dirname(pcbnew.__file__), "..", "..", "share", "kicad", "footprints")
if not os.path.isdir(FPLIB):
    FPLIB = r"C:\Users\acehu\AppData\Local\Programs\KiCad\10.0\share\kicad\footprints"

W, H = 69.0, 42.0
board = pcbnew.BOARD()
board.SetCopperLayerCount(2)

def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(y))

# ---------------------------------------------------------------- nets
nets = {}
def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]

# ---------------------------------------------------------------- footprints
# Every footprint comes from the project library Sesame.pretty: KiCad's stock footprint with silkscreen lines lifted
# to PCBWay's 0.15 mm minimum, and for headers that sit side by side, the per-part outline moved to the Fab layer
# (one outline per group is drawn instead). Keeping these in a library means the board matches its library exactly.
SESAME_LIB = os.path.join(HERE, "Sesame.pretty")
os.makedirs(SESAME_LIB, exist_ok=True)
_io = pcbnew.PCB_IO_KICAD_SEXPR()
_saved = set()

def load(lib, name, group_silk=False):
    new = name + ("_GroupSilk" if group_silk else "")
    if new not in _saved:
        fp = _io.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
        assert fp is not None, (lib, name)
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS and isinstance(g, pcbnew.PCB_SHAPE):
                if group_silk:
                    g.SetLayer(pcbnew.F_Fab)
                elif g.GetWidth() < FromMM(0.15) and not g.IsSolidFill():
                    g.SetWidth(FromMM(0.15))
        fp.SetFPID(pcbnew.LIB_ID("Sesame", new))
        _io.FootprintSave(SESAME_LIB, fp)
        _saved.add(new)
    fp = _io.FootprintLoad(SESAME_LIB, new)
    fp.SetFPID(pcbnew.LIB_ID("Sesame", new))
    return fp

def place(ref, lib, name, pin1, pin2_dir=None, value="", pins=None, ref_off=None, show_ref=True, strip_silk=False):
    """Place a footprint so pad 1 lands on pin1 and pad 2 points along pin2_dir."""
    fp = load(lib, name, strip_silk)
    board.Add(fp)
    fp.SetReference(ref)
    fp.SetPath(pcbnew.KIID_PATH("/" + symbol_uuid(ref)))
    fp.SetValue(value or name)
    fp.Value().SetVisible(False)
    if pin2_dir is not None:
        for ang in (0, 90, 180, 270):
            fp.SetOrientationDegrees(ang)
            fp.SetPosition(P(0, 0))
            a = fp.FindPadByNumber("1").GetPosition()
            b = fp.FindPadByNumber("2").GetPosition()
            d = (b.x - a.x, b.y - a.y)
            if ((d[0] > 0) - (d[0] < 0), (d[1] > 0) - (d[1] < 0)) == pin2_dir:
                break
        else:
            raise RuntimeError("no orientation for " + ref)
    off = fp.FindPadByNumber("1").GetPosition() - fp.GetPosition()
    fp.SetPosition(P(*pin1) - off)
    for num, nname in (pins or {}).items():
        if nname:
            for pad in fp.Pads():
                if pad.GetNumber() == str(num):
                    pad.SetNet(net(nname))
    if ref_off is not None:
        fp.Reference().SetPosition(P(*ref_off))
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
    fp.Reference().SetTextThickness(FromMM(0.12))
    fp.Reference().SetVisible(show_ref)
    return fp

PITCH = 2.54
X1 = 2.5                          # x of DevKit pin 1 (antenna end); the board edge is 2.5 mm past it
def kx(k):                        # x of DevKit pin k (1..15)
    return X1 + PITCH * (k - 1)
DEV_X0, DEV_X1 = X1 - 11.0, kx(15) + 4.0   # DevKit board extent (antenna end is off the carrier)

# Top strip: servo headers (- + S from the edge inward), then the DevKit rows, then the bottom I/O strip
YM, Y5, YS = 2.8, 2.8 + PITCH, 2.8 + 2 * PITCH
YR = YS + 3.8                     # DevKit "right" row (D23 ... 3V3)
YL = YR + 25.4                    # DevKit "left" row (EN ... VIN)
YBOT = YL + 2.8                   # spare I/O + OLED header row
DEV_Y0, DEV_Y1 = YR - 1.3, YL + 1.3

# DOIT ESP32 DevKit V1 (30-pin). Pin 1 = antenna end.
LEFT = ["EN", "VP36", "VN39", "BAT_SENSE", "D35", "D32", "D33", "D25", "D26", "D27",
        "D14", "D12", "D13", "GND", "+5V"]
RIGHT = ["D23", "SCL", "TX0", "RX0", "SDA", "D19", "D18", "D5", "D17", "D16",
         "D4", "D2", "D15", "GND", "+3V3"]
UNUSED = {"EN", "VP36", "VN39", "D35", "D12", "TX0", "RX0", "D5"}
place("J2", "Connector_PinSocket_2.54mm", "PinSocket_1x15_P2.54mm_Vertical", (kx(1), YR), (1, 0),
      "DevKit R", {i + 1: (None if n in UNUSED else n) for i, n in enumerate(RIGHT)}, show_ref=False, strip_silk=True)
place("J1", "Connector_PinSocket_2.54mm", "PinSocket_1x15_P2.54mm_Vertical", (kx(1), YL), (1, 0),
      "DevKit L", {i + 1: (None if n in UNUSED else n) for i, n in enumerate(LEFT)}, show_ref=False, strip_silk=True)
# Unused pins get KiCad's standard "unconnected-(REF-PIN-PadN)" nets, matching the schematic's no-connect flags
SCH_NAME = {"VP36": "VP", "VN39": "VN"}
for ref, row in (("J1", LEFT), ("J2", RIGHT)):
    fpr = [f for f in board.GetFootprints() if f.GetReference() == ref][0]
    for i, n in enumerate(row):
        if n in UNUSED:
            fpr.FindPadByNumber(str(i + 1)).SetNet(net("unconnected-(%s-%s-Pad%d)" % (ref, SCH_NAME.get(n, n), i + 1)))

# Servo headers above the DevKit: S, +5V, GND from the DevKit outward
SERVOS = [("L1", "D23", 1), ("L2", "D19", 6), ("L4", "D18", 7), ("L3", "D17", 9),
          ("R3", "D16", 10), ("R4", "D4", 11), ("R2", "D2", 12), ("R1", "D15", 13)]
for i, (name, sig, k) in enumerate(SERVOS):
    place("S%d" % (i + 1), "Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical",
          (kx(k), YS), (0, -1), "Servo " + name, {1: sig, 2: "+5V", 3: "GND"}, show_ref=False, strip_silk=True)

# Bottom strip: spare I/O (each pin straight below its DevKit pin) and the OLED header
place("J4", "Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical", (kx(6), YBOT), (1, 0),
      "IO", {1: "D32", 2: "D33", 3: "D25", 4: "D26", 5: "D27", 6: "D14"}, show_ref=False, strip_silk=True)
place("J5", "Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical", (kx(13), YBOT), (1, 0),
      "IO2", {1: "D13", 2: "GND", 3: "+5V"}, show_ref=False, strip_silk=True)
# OLED pins sit between DevKit pins so their traces can pass between the socket pads: C D V G
XO = [kx(1) + 1.27, kx(2) + 1.27, kx(3) + 1.27, kx(4) + 1.27]
place("J3", "Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical", (XO[0], YBOT), (1, 0),
      "OLED", {1: "SCL", 2: "SDA", 3: "+3V3", 4: "GND"}, show_ref=False, strip_silk=True)

# Pololu D24V50F5 on a 5-pin header along its bottom edge: EN VIN GND GND OUT (EN unconnected, pulled up on the module)
# Dimensions from Pololu's drawing (pololu.com/file/0J1436): 17.8 x 20.3 mm board, pin row 1.27 mm above the
# bottom edge, OUT pin 1.91 mm in from the right edge (so EN is 5.73 mm from the left), mounting holes at (2.2, 2.2)
# and (15.7, 18.2) mm from the bottom-left corner.
U_X0, U_Y0 = 47.0, 1.0                     # module outline top-left
UY = U_Y0 + 20.3 - 1.27                    # pin row
def ux(n):
    return U_X0 + 17.8 - 1.91 - PITCH * (5 - n)
place("U1", "Connector_PinHeader_2.54mm", "PinHeader_1x05_P2.54mm_Vertical", (ux(1), UY), (1, 0),
      "Pololu D24V50F5", {1: "unconnected-(U1-EN-Pad1)", 2: "VBAT_SW", 3: "GND", 4: "GND", 5: "+5V"},
      show_ref=False, strip_silk=True)

# Bulk capacitor on 5V
C1P = (49.25, 27.0)
place("C1", "Capacitor_THT", "CP_Radial_D8.0mm_P3.50mm", C1P, (1, 0),
      "470uF 16V", {1: "+5V", 2: "GND"}, ref_off=(45.8, 27.0))

# Battery pigtail pads (16-18 AWG, e.g. an XT30 pigtail): square pad = +, round pad = -
BATP, BATN = (63.0, 26.5), (63.0, 26.5 + 7.8)
place("J6", "Connector_Wire", "SolderWire-1.5sqmm_1x02_P7.8mm_D1.7mm_OD3.9mm", BATP, (0, 1),
      "Battery pigtail", {1: "VBAT", 2: "GND"}, show_ref=False)

# Regulator input capacitor: damps the LC spike when the battery or switch connects (Pololu app note 0J16).
# 5 mm wide so it clears the DevKit's USB end even if that end sits 5 mm past pin 15.
C3P = (46.4, 33.8)
place("C3", "Capacitor_THT", "CP_Radial_D5.0mm_P2.00mm", C3P, (0, 1),
      "47uF 35V", {1: "VBAT_SW", 2: "GND"}, ref_off=(46.4, 39.4))

# Power switch wire pads (bridge with a wire if no switch)
SW1, SW2 = (57.4, 38.8), (52.0, 38.8)
place("SW1", "Connector_Wire", "SolderWire-1sqmm_1x02_P5.4mm_D1.4mm_OD2.7mm", SW1, (-1, 0),
      "Switch", {1: "VBAT", 2: "VBAT_SW"}, show_ref=False)

# Battery sense divider under the DevKit: 100k / 22k -> GPIO34 (12.6 V -> 2.27 V, inside the ADC's accurate range), 100nF filter
XR1 = kx(12) + 1.27               # in line with a gap between socket pins, so the sense trace can pass through
R1T, R1B = (XR1, 21.0), (XR1, 21.0 + 10.16)
R2T = (XR1 + 3.0, 21.0)
C2T = (XR1 + 6.0, 21.0)
place("R1", "Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", R1B, (0, -1),
      "100k", {1: "VBAT_SW", 2: "BAT_SENSE"}, ref_off=(XR1 - 2.4, 26.1))
place("R2", "Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", R2T, (0, 1),
      "22k", {1: "BAT_SENSE", 2: "GND"}, ref_off=(R2T[0], 33.0))
place("C2", "Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P5.00mm", C2T, (0, 1),
      "100nF", {1: "BAT_SENSE", 2: "GND"}, ref_off=(C2T[0] + 2.0, 23.5))

# Mounting holes. M2.5 board holes at the corners, top-middle and the DevKit's middle, so no edge cantilevers when
# servos, the OLED or the DevKit are pushed on. The top-right corner is covered by the Pololu's own holes: M2 holes
# straight under them (Pololu drawing: 2.18 mm holes at (2.2, 2.2) and (15.7, 18.2) from the module's bottom-left),
# so one screw clamps module, a printed standoff and the carrier together.
# (x, y, keep-out radius = screw head radius + 0.5 mm)
HOLES = [(8.85, 2.2, 3.0),    # top-left, between servo headers L1 and L2
         (3.8, 30.0, 3.0),    # bottom-left, under the DevKit's left end
         (40.5, 2.2, 3.0),    # top-middle, right of the servo block
         (31.0, 16.5, 3.0),   # middle, under the DevKit
         (66.6, 40.0, 3.0)]   # bottom-right corner
POLOLU_HOLES = [(U_X0 + 2.2, U_Y0 + 20.3 - 2.2, 2.4), (U_X0 + 15.7, U_Y0 + 20.3 - 18.2, 2.4)]
for ref, (x, y, r) in [("H%d" % (i + 1), h) for i, h in enumerate(HOLES)] + [("HP%d" % (i + 1), h) for i, h in enumerate(POLOLU_HOLES)]:
    fp = load("MountingHole", "MountingHole_2.7mm_M2.5" if r == 3.0 else "MountingHole_2.2mm_M2")
    board.Add(fp)
    fp.SetReference(ref)
    fp.SetPath(pcbnew.KIID_PATH("/" + symbol_uuid(ref)))
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetPosition(P(x, y))

# ---------------------------------------------------------------- tracks
F, B = pcbnew.F_Cu, pcbnew.B_Cu
def track(pts, netname, w, layer=F):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(*a))
        t.SetEnd(P(*b))
        t.SetWidth(FromMM(w))
        t.SetLayer(layer)
        t.SetNet(net(netname))
        board.Add(t)

def via(xy, netname, d=0.8, drill=0.4):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*xy))
    v.SetWidth(FromMM(d))
    v.SetDrill(FromMM(drill))
    v.SetNet(net(netname))
    board.Add(v)

SIG_W = 0.3

# Servo signals: straight up from the DevKit pin
for name, sig, k in SERVOS:
    track([(kx(k), YR), (kx(k), YS)], sig, SIG_W)
# +5V rail through the servo + pins, on both layers for peak servo current. Between L1 and L2 it dips down to stay
# clear of the top-left mounting hole's screw head.
RAIL = [(kx(1), Y5), (4.3, Y5), (5.6, 6.6), (12.1, 6.6), (13.4, Y5), (kx(13), Y5)]
track(RAIL, "+5V", 2.0)
track(RAIL, "+5V", 2.0, B)
# Regulator OUT -> servo rail and DevKit VIN on the bottom layer; bulk cap tees in
XF = 44.0
track([(ux(5), UY), (ux(5), 22.3), (53.5, 22.3), (52.3, 23.5), (XF, 23.5), (XF, 9.5), (35.5, 9.5), (35.5, Y5), (kx(13), Y5)],
      "+5V", 2.0, B)
track([(XF, 23.5), (XF, YL), (kx(15), YL)], "+5V", 1.5, B)
track([C1P, (C1P[0], 23.5)], "+5V", 1.2, B)
track([(kx(15), YL), (kx(15), YBOT)], "+5V", 0.8)

# Battery: pigtail + -> switch -> regulator VIN
track([BATP, (60.0, BATP[1]), (60.0, 37.7), (58.9, SW1[1]), SW1], "VBAT", 1.5)
track([SW2, (56.5, 34.3), (56.5, 22.5), (ux(2), 22.5), (ux(2), UY)], "VBAT_SW", 1.5)
track([C3P, (49.6, C3P[1]), (SW2[0], 35.95), SW2], "VBAT_SW", 1.0)

# Battery sense: switched battery along the bottom edge (bottom layer), up between socket pins to R1;
# divider node over to GPIO34 on top
track([SW2, (SW2[0], 41.3), (XR1, 41.3), R1B], "VBAT_SW", 0.4, B)
track([R1T, (16.0, R1T[1]), (16.0, 34.5), (kx(4), 34.5), (kx(4), YL)], "BAT_SENSE", SIG_W)
track([R1T, R2T, C2T], "BAT_SENSE", SIG_W)

# I2C to the OLED header: bottom layer under the DevKit, passing between the bottom-row socket pads
track([(kx(2), YR), (kx(2), 20.0), (10.5, 20.0), (10.5, 33.5), (XO[0], 33.5), (XO[0], YBOT)], "SCL", SIG_W, B)
track([(kx(5), YR), (kx(5), 35.0), (XO[1], 35.0), (XO[1], YBOT)], "SDA", SIG_W, B)
# 3V3 on top: from DevKit 3V3 along just inside the top row, then down between pins to the OLED header
track([(kx(15), YR), (kx(15), YR + 1.6), (XO[2], YR + 1.6), (XO[2], YBOT)], "+3V3", SIG_W)

# Spare I/O straight down to the bottom header
for k in [6, 7, 8, 9, 10, 11, 13]:
    track([(kx(k), YL), (kx(k), YBOT)], LEFT[k - 1], SIG_W)

# ---------------------------------------------------------------- outline
def line(a, b, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(FromMM(w))
    board.Add(s)

def rect(x0, y0, x1, y1, layer, w):
    for a, b in [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]:
        line(a, b, layer, w)

rect(0, 0, W, H, pcbnew.Edge_Cuts, 0.1)

# ---------------------------------------------------------------- silkscreen
SILK = pcbnew.F_SilkS
def text(s, x, y, size=1.0, layer=SILK, angle=0, just=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(size * 0.15))
    if angle:
        t.SetTextAngleDegrees(angle)
    if just == "left":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    elif just == "right":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)

# DevKit outline (its antenna end hangs off the left edge) and orientation notes
for a, b in [((0.15, DEV_Y0), (DEV_X1, DEV_Y0)), ((DEV_X1, DEV_Y0), (DEV_X1, DEV_Y1))]:   # bottom edge left off: labels live there
    line(a, b, SILK, 0.15)
text("ESP-WROOM-32", 15.0, 16.5, 1.2)
text("BAT->IO34 x5.55", 35.0, 34.6, 0.8)
# Servo labels above each column, S/+/- legend to the right of the block
for name, sig, k in SERVOS:
    text(name, kx(k), 1.0, 0.8)
for ks in ([1], [6, 7], [9, 10, 11, 12, 13]):   # one outline per group of side-by-side servo headers
    rect(kx(ks[0]) - 1.27, YM - 1.27, kx(ks[-1]) + 1.27, YS + 1.27, SILK, 0.12)
for y, s in [(YS, "S"), (Y5, "+"), (YM, "-")]:
    text(s, kx(13) + 2.2, y, 0.8)
# Bottom-strip labels (between the socket row and the header pins)
YLAB = (YL + YBOT) / 2
for k in [6, 7, 8, 9, 10, 11, 13]:
    text(LEFT[k - 1][1:], kx(k), YLAB, 0.8)
text("G", kx(14), YLAB, 0.8)
text("5V", kx(15), YLAB, 0.8)
for x, s in zip(XO, ["C", "D", "V", "G"]):
    text(s, x, YLAB, 0.8)
text("OLED", (XO[0] + XO[3]) / 2, YL - 2.2, 0.8)
# Regulator module outline + pin labels
rect(U_X0, U_Y0, U_X0 + 17.8, U_Y0 + 20.3, SILK, 0.15)
text("Pololu", U_X0 + 8.9, 7.0, 0.9)
text("D24V50F5", U_X0 + 8.9, 9.0, 0.9)
text("5V 5A", U_X0 + 8.9, 11.0, 0.9)
for n, s in enumerate(["EN", "VIN", "GND", "GND", "OUT"]):
    text(s, ux(n + 1), UY - 1.4, 0.8, angle=90, just="left")
# Power
text("SWITCH", (SW1[0] + SW2[0]) / 2, 41.0, 0.8)
text("BATT 3S", BATP[0], 23.7, 0.9)
text("BAT+", BATP[0], BATP[1] + 3.0, 0.9)
text("BAT-", BATN[0], BATN[1] + 2.9, 0.9)

# ---------------------------------------------------------------- face art
# Sesame's own "cute" face, read straight from the firmware's OLED bitmaps and drawn pixel-for-pixel.
import re
FACES_H = os.path.join(HERE, "..", "..", "..", "firmware", "face-bitmaps.h")

def face_pixels(name):
    src = open(FACES_H, encoding="utf8").read()
    m = re.search(r"const unsigned char epd_bitmap_%s\s*\[\]\s*PROGMEM\s*=\s*\{([^}]*)\}" % name, src)
    data = [int(v, 16) for v in re.findall(r"0x[0-9a-fA-F]+", m.group(1))]
    px = [[bool(data[y * 16 + x // 8] & (0x80 >> (x % 8))) for x in range(128)] for y in range(64)]
    ys = [y for y in range(64) if any(px[y])]
    xs = [x for x in range(128) if any(px[y][x] for y in range(64))]
    return [row[min(xs):max(xs) + 1] for row in px[min(ys):max(ys) + 1]]

def halve(px):   # 2x2 max-pool: keeps thin strokes when shrinking
    h, w = (len(px) + 1) // 2, (len(px[0]) + 1) // 2
    get = lambda y, x: y < len(px) and x < len(px[0]) and px[y][x]
    return [[get(2*y, 2*x) or get(2*y+1, 2*x) or get(2*y, 2*x+1) or get(2*y+1, 2*x+1) for x in range(w)] for y in range(h)]

def pixel_art(px, x0, y0, size, layer, mirror=False):
    w = len(px[0])
    for y, row in enumerate(px):
        x = 0
        while x < w:
            if row[x]:
                e = x
                while e < w and row[e]:
                    e += 1
                a, b = (w - e, w - x) if mirror else (x, e)
                r = pcbnew.PCB_SHAPE(board)
                r.SetShape(pcbnew.SHAPE_T_RECT)
                r.SetStart(P(x0 + a * size, y0 + y * size))
                r.SetEnd(P(x0 + b * size, y0 + (y + 1) * size))
                r.SetFilled(True)
                r.SetWidth(0)
                r.SetLayer(layer)
                board.Add(r)
                x = e
            else:
                x += 1

CUTE = face_pixels("cute")
# Back: big, mirrored so it reads correctly from underneath, in the open area under the DevKit
pixel_art(CUTE, 1.5, 15.5, 0.235, pcbnew.B_SilkS, mirror=True)
for s_, y_, sz in [("SESAME", 26.0, 2.2), ("DevKit carrier v1", 28.6, 1.2)]:
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s_)
    t.SetPosition(P(22.0, y_))
    t.SetLayer(pcbnew.B_SilkS)
    t.SetTextSize(VECTOR2I(FromMM(sz), FromMM(sz)))
    t.SetTextThickness(FromMM(sz * 0.15))
    t.SetMirrored(True)
    board.Add(t)
# Front: half resolution so every stroke stays above the 0.15 mm silkscreen minimum
pixel_art(halve(CUTE), 37.0, 6.0, 0.164, SILK)

# ---------------------------------------------------------------- zones
def zone(layer):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net("GND"))
    o = z.Outline()
    o.NewOutline()
    for x, y in [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]:
        o.Append(FromMM(x), FromMM(y))
    z.SetLocalClearance(FromMM(0.3))
    z.SetMinThickness(FromMM(0.25))
    z.SetThermalReliefGap(FromMM(0.4))
    z.SetThermalReliefSpokeWidth(FromMM(0.6))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    board.Add(z)
zone(F)
zone(B)

# Screw-head keep-outs: nothing but ground fill under a screw head (M2.5: 3.0 mm radius, M2: 2.4 mm)
for (hx, hy, kr) in HOLES + POLOLU_HOLES:
    ka = pcbnew.ZONE(board)
    ka.SetIsRuleArea(True)
    ka.SetLayerSet(pcbnew.LSET.AllCuMask())
    ka.SetDoNotAllowTracks(True)
    ka.SetDoNotAllowVias(True)
    ka.SetDoNotAllowZoneFills(False)
    ka.SetDoNotAllowPads(False)
    ka.SetDoNotAllowFootprints(False)
    ko = ka.Outline()
    ko.NewOutline()
    for i in range(32):
        a = 2 * math.pi * i / 32
        ko.Append(FromMM(hx + kr * math.cos(a)), FromMM(hy + kr * math.sin(a)))
    board.Add(ka)

# GND stitching vias in open areas
for xy in [(28.5, 33.0), (42.3, 28.0), (42.5, 33.0), (54.0, 31.0), (66.6, 30.0), (60.0, 18.0)]:
    via(xy, "GND")

# ---------------------------------------------------------------- design rules + fill
ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.2)
ds.m_MinClearance = FromMM(0.2)
ds.m_ViasMinSize = FromMM(0.6)
ds.m_MinThroughDrill = FromMM(0.3)
ds.m_CopperEdgeClearance = FromMM(0.3)

# PCBWay's legend minimum is 0.15 mm: lift every silkscreen line (KiCad footprints default to 0.12) to at least that
for item in list(board.GetDrawings()) + [g for fp in board.GetFootprints() for g in fp.GraphicalItems()]:
    if isinstance(item, pcbnew.PCB_SHAPE) and item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)             and not item.IsSolidFill() and item.GetWidth() < FromMM(0.15):
        item.SetWidth(FromMM(0.15))

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(OUT)
print("saved", OUT)
