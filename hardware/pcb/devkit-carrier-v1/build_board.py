# Generates the Sesame DevKit Carrier PCB (KiCad 10) for a 30-pin, 1.0"-row ESP32 DevKit.
# Run with KiCad's bundled python:  "<KiCad>/bin/python.exe" build_board.py
#
# Layout (80 x 42 mm): DevKit lies along the board, USB flush with the left edge, antenna to the right.
# Servo headers sit in a row under the DevKit, each straight below the pin that drives it.
# Spare I/O + OLED headers run along the top edge; regulator, bulk cap, switch pads and XT30 fill the right end.
import os
import pcbnew
from pcbnew import VECTOR2I, FromMM

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sesame-devkit-carrier.kicad_pcb")
FPLIB = os.path.join(os.path.dirname(pcbnew.__file__), "..", "..", "share", "kicad", "footprints")
if not os.path.isdir(FPLIB):
    FPLIB = r"C:\Users\acehu\AppData\Local\Programs\KiCad\10.0\share\kicad\footprints"

W, H = 80.0, 42.0
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
def load(lib, name):
    fp = pcbnew.FootprintLoad(os.path.join(FPLIB, lib + ".pretty"), name)
    assert fp is not None, (lib, name)
    return fp

def place(ref, lib, name, pin1, pin2_dir=None, value="", pins=None, ref_off=None, show_ref=True):
    """Place a footprint so pad 1 lands on pin1 and pad 2 points along pin2_dir."""
    fp = load(lib, name)
    board.Add(fp)
    fp.SetReference(ref)
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
YT, YB = 4.8, 4.8 + 25.4          # DevKit socket rows: top (DevKit "left" row), bottom (DevKit "right" row)
X15 = 4.0                         # x of pin 15 (USB end); pin 1 is at the antenna end
DEV_X0, DEV_X1 = 0.0, 51.0        # DevKit board extent along x
DEV_Y0, DEV_Y1 = YT - 1.3, YB + 1.3
def kx(k):                        # x of DevKit pin k (1..15)
    return X15 + PITCH * (15 - k)

# DOIT ESP32 DevKit V1 (30-pin). Pin 1 = antenna end.
LEFT = ["EN", "VP36", "VN39", "BAT_SENSE", "D35", "D32", "D33", "D25", "D26", "D27",
        "D14", "D12", "D13", "GND", "+5V"]
RIGHT = ["D23", "SCL", "TX0", "RX0", "SDA", "D19", "D18", "D5", "D17", "D16",
         "D4", "D2", "D15", "GND", "+3V3"]
UNUSED = {"EN", "VP36", "VN39", "D35", "D12", "TX0", "RX0", "D5"}
place("J1", "Connector_PinSocket_2.54mm", "PinSocket_1x15_P2.54mm_Vertical", (kx(1), YT), (-1, 0),
      "DevKit L", {i + 1: (None if n in UNUSED else n) for i, n in enumerate(LEFT)}, show_ref=False)
place("J2", "Connector_PinSocket_2.54mm", "PinSocket_1x15_P2.54mm_Vertical", (kx(1), YB), (-1, 0),
      "DevKit R", {i + 1: (None if n in UNUSED else n) for i, n in enumerate(RIGHT)}, show_ref=False)

# Servo headers under the DevKit: S, +5V, GND from the DevKit outward
YS, Y5, YG = YB + 3.8, YB + 3.8 + PITCH, YB + 3.8 + 2 * PITCH
SERVOS = [("L1", "D23", 1), ("L2", "D19", 6), ("L4", "D18", 7), ("L3", "D17", 9),
          ("R3", "D16", 10), ("R4", "D4", 11), ("R2", "D2", 12), ("R1", "D15", 13)]
for i, (name, sig, k) in enumerate(SERVOS):
    place("S%d" % (i + 1), "Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical",
          (kx(k), YS), (0, 1), "Servo " + name, {1: sig, 2: "+5V", 3: "GND"}, show_ref=False)

# Top edge: spare I/O (each pin straight above its DevKit pin) and the OLED header
YTOP = 1.6
place("J4", "Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical", (kx(6), YTOP), (-1, 0),
      "IO", {1: "D32", 2: "D33", 3: "D25", 4: "D26", 5: "D27", 6: "D14"}, show_ref=False)
place("J5", "Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical", (kx(13), YTOP), (-1, 0),
      "IO2", {1: "D13", 2: "GND", 3: "+5V"}, show_ref=False)
# OLED pins sit between DevKit pins so their traces can pass between the socket pads
XO = [kx(3) + 1.27, kx(2) + 1.27, kx(1) + 1.27, kx(1) + 1.27 + PITCH]   # D C V G
place("J3", "Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical", (XO[0], YTOP), (1, 0),
      "OLED", {1: "SDA", 2: "SCL", 3: "+3V3", 4: "GND"}, show_ref=False)

# Pololu D24V50F5 on a 5-pin header: EN VIN GND GND OUT (EN unconnected, pulled up on the module)
XU, U_TOP = 60.5, 1.0
U_Y1 = U_TOP + 6.1
def uy(n):
    return U_Y1 + PITCH * (n - 1)
place("U1", "Connector_PinHeader_2.54mm", "PinHeader_1x05_P2.54mm_Vertical", (XU, U_Y1), (0, 1),
      "Pololu D24V50F5", {1: None, 2: "VBAT_SW", 3: "GND", 4: "GND", 5: "+5V"}, show_ref=False)

# Bulk capacitor on 5V
C1P = (62.25, 23.5)
place("C1", "Capacitor_THT", "CP_Radial_D8.0mm_P3.50mm", C1P, (1, 0),
      "470uF 16V", {1: "+5V", 2: "GND"}, ref_off=(64.0, 28.6))

# XT30 battery input, mating face at the right edge (footprint: pad 2 = +, pad 1 = -)
XT1 = (66.4, 37.5)
XT2 = (XT1[0], XT1[1] - 5.0)
place("J6", "Connector_AMASS", "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal", XT1, (0, -1),
      "XT30PW-M", {1: "GND", 2: "VBAT"}, show_ref=False)

# Power switch wire pads (bridge with a wire if no switch)
SW1, SW2 = (60.8, 37.5), (55.4, 37.5)
place("SW1", "Connector_Wire", "SolderWire-1sqmm_1x02_P5.4mm_D1.4mm_OD2.7mm", SW1, (-1, 0),
      "Switch", {1: "VBAT", 2: "VBAT_SW"}, show_ref=False)

# Battery sense divider under the DevKit: 100k / 22k -> GPIO34 (12.6 V -> 2.27 V, inside the ADC's accurate range), 100nF filter
R1T, R1B = (30.9, 15.5), (30.9, 15.5 + 10.16)
R2T, R2B = (34.0, 15.5), (34.0, 15.5 + 10.16)
C2T = (37.0, 18.0)
place("R1", "Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", R1B, (0, -1),
      "100k", {1: "VBAT_SW", 2: "BAT_SENSE"}, ref_off=(28.6, 20.6))
place("R2", "Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", R2T, (0, 1),
      "22k", {1: "BAT_SENSE", 2: "GND"}, ref_off=(34.0, 27.6))
place("C2", "Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P5.00mm", C2T, (0, 1),
      "100nF", {1: "BAT_SENSE", 2: "GND"}, ref_off=(39.0, 20.5))

# Mounting holes (M2.5)
for i, (x, y) in enumerate([(48.5, 2.3), (2.6, 39.4), (57.8, 22.0), (77.5, 23.5)]):
    fp = load("MountingHole", "MountingHole_2.7mm_M2.5")
    board.Add(fp)
    fp.SetReference("H%d" % (i + 1))
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

SIG_W, PWR_W = 0.3, 1.5

# Servo signals: straight down from the DevKit pin
for name, sig, k in SERVOS:
    track([(kx(k), YB), (kx(k), YS)], sig, SIG_W)
# +5V rail through the servo + pins, then up the left edge to DevKit VIN and the IO header
track([(kx(1), Y5), (kx(13), Y5)], "+5V", 2.0)
track([(kx(13), Y5), (1.5, Y5), (1.5, YT), (kx(15), YT)], "+5V", PWR_W)
# Regulator OUT -> servo rail on the bottom layer (crosses under the VIN feed), bulk cap on top
track([(XU, uy(5)), (52.8, uy(5)), (52.8, Y5), (kx(1), Y5)], "+5V", 2.0, B)
track([C1P, (C1P[0], uy(5)), (XU, uy(5))], "+5V", 1.2)

# Battery: XT30 + -> switch -> regulator VIN
track([XT2, (SW1[0], XT2[1]), SW1], "VBAT", 1.2)
track([SW2, (SW2[0], uy(2)), (XU, uy(2))], "VBAT_SW", 1.0)

# Battery sense: switched battery along the bottom edge (bottom layer) up to R1; divider node to GPIO34
XSN = kx(4) + 1.27
track([SW2, (SW2[0], 41.0), (XSN, 41.0), (XSN, 29.0), (R1B[0], 27.3), R1B], "VBAT_SW", 0.4, B)
track([R1T, (R1T[0], 6.4), (kx(4), YT)], "BAT_SENSE", SIG_W)
track([R1T, R2T, (C2T[0], R2T[1]), C2T], "BAT_SENSE", SIG_W)

# I2C to the OLED header: bottom layer under the DevKit, passing between the top-row socket pads
track([(kx(5), YB), (kx(5), 13.0), (XO[0], 13.0), (XO[0], YTOP)], "SDA", SIG_W, B)
track([(kx(2), YB), (kx(2), 28.0), (XO[1], 26.73), (XO[1], YTOP)], "SCL", SIG_W, B)
# 3V3 on top: from DevKit 3V3 along under the DevKit, up between pins to the OLED header
track([(kx(15), YB), (kx(15), 28.6), (XO[2], 28.6), (XO[2], YTOP)], "+3V3", SIG_W)

# Spare I/O straight up to the top header
for k in [6, 7, 8, 9, 10, 11, 13]:
    track([(kx(k), YT), (kx(k), YTOP)], LEFT[k - 1], SIG_W)
track([(kx(15), YT), (kx(15), YTOP)], "+5V", 0.8)

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

# DevKit outline, USB end and antenna end
rect(DEV_X0 + 0.15, DEV_Y0, DEV_X1, DEV_Y1, SILK, 0.15)
text("ESP32 DevKit (30-pin)", 20.0, 9.0, 1.2)
text("<- USB", 7.5, 17.5, 1.0)
text("SESAME CARRIER v1", 20.0, 22.0, 1.0)
text("ANT", 47.5, 17.5, 1.0, angle=90)
# Servo labels under each column, S/+/- legend at the left
for name, sig, k in SERVOS:
    text(name, kx(k), H - 0.9, 0.8)
for y, s in [(YS, "S"), (Y5, "+"), (YG, "-")]:
    text(s, kx(13) - 2.2, y, 0.8)
# Top-edge labels (just below the header pins)
for k in [6, 7, 8, 9, 10, 11, 13]:
    text(LEFT[k - 1][1:], kx(k), 3.2, 0.8)
text("G", kx(14), 3.2, 0.8)
text("5V", kx(15), 3.2, 0.8)
for x, s in zip(XO, ["D", "C", "V", "G"]):
    text(s, x, 3.2, 0.8)
text("OLED", XO[0] - 2.3, YTOP, 0.8, just="right")
# Regulator module outline + pin labels
rect(XU - 1.3, U_TOP, XU - 1.3 + 20.3, U_TOP + 17.8, SILK, 0.15)
text("Pololu D24V50F5", 70.6, 8.0, 0.9)
text("5V 5A", 70.6, 10.0, 0.9)
for n, s in enumerate(["EN", "VIN", "GND", "GND", "OUT"]):
    text(s, XU + 1.6, uy(n + 1), 0.8, just="left")
# Power
text("SWITCH", (SW1[0] + SW2[0]) / 2, 40.7, 0.8)
text("BATT 3S", 75.0, 27.6, 0.9)
text("BAT->IO34 x5.55", 18.0, 26.2, 0.8)

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

# No copper under the ESP32-WROOM antenna (DevKit's far end)
k = pcbnew.ZONE(board)
k.SetIsRuleArea(True)
k.SetLayerSet(pcbnew.LSET.AllCuMask())
k.SetDoNotAllowTracks(True)
k.SetDoNotAllowVias(True)
k.SetDoNotAllowZoneFills(True)
k.SetDoNotAllowPads(False)
k.SetDoNotAllowFootprints(False)
ko = k.Outline()
ko.NewOutline()
for x, y in [(43.0, DEV_Y0), (DEV_X1 + 0.5, DEV_Y0), (DEV_X1 + 0.5, DEV_Y1), (43.0, DEV_Y1)]:
    ko.Append(FromMM(x), FromMM(y))
board.Add(k)

# GND stitching vias in open areas
for xy in [(10.0, 10.0), (20.0, 14.0), (24.0, 25.0), (12.0, 25.0), (40.0, 9.0), (6.0, 33.5), (45.0, 39.0),
           (50.0, 34.0), (57.0, 30.0), (57.5, 12.0), (69.0, 22.0), (78.5, 3.0), (72.0, 41.0), (64.0, 30.5),
           (30.7, 39.3), (36.0, 38.5), (16.0, 6.5)]:
    via(xy, "GND")

# ---------------------------------------------------------------- design rules + fill
ds = board.GetDesignSettings()
ds.m_TrackMinWidth = FromMM(0.2)
ds.m_MinClearance = FromMM(0.2)
ds.m_ViasMinSize = FromMM(0.6)
ds.m_MinThroughDrill = FromMM(0.3)
ds.m_CopperEdgeClearance = FromMM(0.3)

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.Save(OUT)
print("saved", OUT)
