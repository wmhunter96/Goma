# Generates the Sesame DevKit Carrier v1 PCB (KiCad 10) for a 30-pin, 1.0"-row ESP32 DevKit.
# Run with KiCad's bundled python:  "<KiCad>/bin/python.exe" build_board.py
import os
import pcbnew
from pcbnew import VECTOR2I, FromMM

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sesame-devkit-carrier.kicad_pcb")
FPLIB = os.path.join(os.path.dirname(pcbnew.__file__), "..", "..", "share", "kicad", "footprints")
if not os.path.isdir(FPLIB):
    FPLIB = r"C:\Users\acehu\AppData\Local\Programs\KiCad\10.0\share\kicad\footprints"

W, H = 70.0, 58.0
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

def place(ref, lib, name, pin1, pin2_dir=None, value="", pins=None, ref_off=None):
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
            sx = (d[0] > 0) - (d[0] < 0)
            sy = (d[1] > 0) - (d[1] < 0)
            if (sx, sy) == pin2_dir:
                break
        else:
            raise RuntimeError("no orientation for " + ref)
    off = fp.FindPadByNumber("1").GetPosition() - fp.GetPosition()
    fp.SetPosition(P(*pin1) - off)
    if pins:
        for num, nname in pins.items():
            if nname:
                for pad in fp.Pads():
                    if pad.GetNumber() == str(num):
                        pad.SetNet(net(nname))
    if ref_off is not None:
        fp.Reference().SetPosition(P(*ref_off))
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
    fp.Reference().SetTextThickness(FromMM(0.12))
    return fp

PITCH = 2.54
ROW0 = 13.0                       # y of DevKit pin 1 (antenna end)
XL, XR = 7.62, 7.62 + 25.4        # DevKit left / right socket rows
def ky(k):                        # y of DevKit pin k (1..15)
    return ROW0 + PITCH * (k - 1)

# DOIT ESP32 DevKit V1 (30-pin), top view, antenna up, USB down
LEFT = ["EN", "VP36", "VN39", "BAT_SENSE", "D35", "D32", "D33", "D25", "D26", "D27",
        "D14", "D12", "D13", "GND", "+5V"]
RIGHT = ["D23", "SCL", "TX0", "RX0", "SDA", "D19", "D18", "D5", "D17", "D16",
         "D4", "D2", "D15", "GND", "+3V3"]
UNUSED = {"EN", "VP36", "VN39", "D35", "D12", "TX0", "RX0", "D5"}
place("J1", "Connector_PinSocket_2.54mm", "PinSocket_1x15_P2.54mm_Vertical", (XL, ky(1)), (0, 1),
      "DevKit L", {i + 1: (None if n in UNUSED else n) for i, n in enumerate(LEFT)}, ref_off=(XL, ROW0 - 2.2))
place("J2", "Connector_PinSocket_2.54mm", "PinSocket_1x15_P2.54mm_Vertical", (XR, ky(1)), (0, 1),
      "DevKit R", {i + 1: (None if n in UNUSED else n) for i, n in enumerate(RIGHT)}, ref_off=(XR, ROW0 - 2.2))

# Servo headers: each row level with the DevKit pin that drives it.  S, +5V, GND left->right.
XS, X5, XG = 38.1, 40.64, 43.18
SERVOS = [("L1", "D23", 1), ("L2", "D19", 6), ("L4", "D18", 7), ("L3", "D17", 9),
          ("R3", "D16", 10), ("R4", "D4", 11), ("R2", "D2", 12), ("R1", "D15", 13)]
for i, (name, sig, k) in enumerate(SERVOS):
    fp = place("S%d" % (i + 1), "Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical",
               (XS, ky(k)), (1, 0), "Servo " + name, {1: sig, 2: "+5V", 3: "GND"})
    fp.Reference().SetVisible(False)

# OLED header, pin order matches common SSD1306 modules: GND VCC SCL SDA
OLED_Y = 6.35
place("J3", "Connector_PinHeader_2.54mm", "PinHeader_1x04_P2.54mm_Vertical", (35.56, OLED_Y), (1, 0),
      "OLED", {1: "GND", 2: "+3V3", 3: "SCL", 4: "SDA"}, ref_off=(33.2, OLED_Y))

# Spare I/O, each pin level with its DevKit pin
place("J4", "Connector_PinHeader_2.54mm", "PinHeader_1x06_P2.54mm_Vertical", (2.54, ky(6)), (0, 1),
      "IO", {1: "D32", 2: "D33", 3: "D25", 4: "D26", 5: "D27", 6: "D14"}, ref_off=(2.54, ky(6) - 2.2))
place("J5", "Connector_PinHeader_2.54mm", "PinHeader_1x03_P2.54mm_Vertical", (2.54, ky(13)), (0, 1),
      "IO2", {1: "D13", 2: "GND", 3: "+5V"}, ref_off=(2.54, ky(13) - 2.0))

# Pololu D24V50F5 plugs in on a 5-pin header: EN VIN GND GND OUT (EN left unconnected, pulled up on module)
XU = 48.26
U_TOP = 6.0
U_Y1 = U_TOP + 6.1
place("U1", "Connector_PinHeader_2.54mm", "PinHeader_1x05_P2.54mm_Vertical", (XU, U_Y1), (0, 1),
      "Pololu D24V50F5", {1: None, 2: "VBAT_SW", 3: "GND", 4: "GND", 5: "+5V"}, ref_off=(57.0, 21.5))
def uy(n):
    return U_Y1 + PITCH * (n - 1)

# Bulk capacitor on 5V
place("C1", "Capacitor_THT", "CP_Radial_D8.0mm_P3.50mm", (54.0, 30.0), (1, 0),
      "470uF 16V", {1: "+5V", 2: "GND"}, ref_off=(55.75, 35.2))

# Power switch wire pads (bridge with a wire if no switch)
SW1, SW2 = (50.0, 45.4), (50.0, 40.0)
place("SW1", "Connector_Wire", "SolderWire-1sqmm_1x02_P5.4mm_D1.4mm_OD2.7mm", SW1, (0, -1),
      "Switch", {1: "VBAT", 2: "VBAT_SW"}).Reference().SetVisible(False)

# XT30 battery input, mating face toward the right edge (footprint: pad 2 = +, pad 1 = -)
XT1 = (56.6, 49.0)
place("J6", "Connector_AMASS", "AMASS_XT30PW-M_1x02_P2.50mm_Horizontal", XT1, (0, -1),
      "XT30PW-M", {1: "GND", 2: "VBAT"}, ref_off=(63.0, 56.6))

# Battery sense divider under the DevKit: 100k / 27k -> GPIO34, 100nF filter
RX1, RX2 = 12.7, 22.86
place("R1", "Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", (RX1, 44.0), (1, 0),
      "100k", {1: "BAT_SENSE", 2: "VBAT_SW"}, ref_off=(17.8, 44.0))
place("R2", "Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P10.16mm_Horizontal", (RX1, 40.0), (1, 0),
      "27k", {1: "BAT_SENSE", 2: "GND"}, ref_off=(17.8, 40.0))
place("C2", "Capacitor_THT", "C_Disc_D5.0mm_W2.5mm_P5.00mm", (RX1, 36.0), (1, 0),
      "100nF", {1: "BAT_SENSE", 2: "GND"}, ref_off=(20.2, 36.0))

# Mounting holes (M2.5)
for i, (x, y) in enumerate([(3, 3), (67, 3), (3, 55), (67, 30)]):
    fp = load("MountingHole", "MountingHole_2.7mm_M2.5")
    board.Add(fp)
    fp.SetReference("H%d" % (i + 1))
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    fp.SetPosition(P(x, y))

# ---------------------------------------------------------------- tracks
def track(pts, netname, w, layer=pcbnew.F_Cu):
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

F, B = pcbnew.F_Cu, pcbnew.B_Cu
SIG_W, PWR_W = 0.3, 1.5

# Servo signals: straight across on top
for name, sig, k in SERVOS:
    track([(XR, ky(k)), (XS, ky(k))], sig, SIG_W)

# +5V: regulator OUT -> servo +5V column -> down and across to DevKit VIN, plus IO header
track([(XU, uy(5)), (X5, uy(5))], "+5V", PWR_W)
track([(X5, ky(1)), (X5, ky(13))], "+5V", 1.2)
track([(X5, ky(13)), (X5, 50.8), (XL, 50.8), (XL, ky(15))], "+5V", PWR_W)
track([(XL, ky(15)), (2.54, ky(15))], "+5V", 1.0)
# +5V to bulk cap on the bottom layer (passes between GND pads)
track([(54.0, 30.0), (X5, 30.0), (X5, ky(7))], "+5V", 1.0, B)

# Battery: XT30 + -> switch -> regulator VIN
track([(XT1[0], XT1[1] - 5.0), (52.0, XT1[1] - 5.0), SW1], "VBAT", 1.2)
track([SW2, (SW2[0], uy(2)), (XU, uy(2))], "VBAT_SW", 1.0)

# Battery sense: switched battery -> R1, divider node -> GPIO34
track([SW2, (46.0, SW2[1]), (46.0, 52.5), (RX2, 52.5), (RX2, 44.0)], "VBAT_SW", 0.5, B)
track([(RX1, 44.0), (RX1, ky(4)), (XL, ky(4))], "BAT_SENSE", 0.3, B)

# I2C + 3V3 up the corridor between the DevKit and servo headers (bottom), then over to the OLED header (top)
XSCL, XSDA, XVCC = 34.6, 35.4, 36.2
YSCL, YSDA, YVCC = 9.4, 10.4, 8.4
track([(XR, ky(2)), (XSCL, ky(2)), (XSCL, YSCL)], "SCL", SIG_W, B)
track([(XR, ky(5)), (XSDA, ky(5)), (XSDA, YSDA)], "SDA", SIG_W, B)
track([(XR, ky(15)), (XVCC, ky(15)), (XVCC, YVCC)], "+3V3", 0.4, B)
via((XSCL, YSCL), "SCL")
via((XSDA, YSDA), "SDA")
via((XVCC, YVCC), "+3V3")
track([(XVCC, YVCC), (38.1, YVCC), (38.1, OLED_Y)], "+3V3", 0.4)
track([(XSCL, YSCL), (40.64, YSCL), (40.64, OLED_Y)], "SCL", SIG_W)
track([(XSDA, YSDA), (43.18, YSDA), (43.18, OLED_Y)], "SDA", SIG_W)

# Spare I/O straight across on top
for j, k in enumerate([6, 7, 8, 9, 10, 11, 13]):
    track([(XL, ky(k)), (2.54, ky(k))], LEFT[k - 1], SIG_W)

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
def text(s, x, y, size=1.0, layer=pcbnew.F_SilkS, angle=0, just=None):
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

SILK = pcbnew.F_SilkS
# DevKit outline (28 x 51 mm) and USB marker
rect(XL - 1.3, ROW0 - 11.0, XR + 1.3, ROW0 - 11.0 + 51.0, SILK, 0.15)
text("ESP32 DevKit (30-pin)", (XL + XR) / 2, 27.5, 1.2)
text("ANTENNA - keep clear", (XL + XR) / 2, 5.0, 0.9)
text("USB", (XL + XR) / 2, ROW0 + 37.4, 1.0)
# Servo labels and column header
for name, sig, k in SERVOS:
    text(name, XG + 1.8, ky(k), 0.9, just="left")
text("S", XS, ky(1) - 1.9, 0.9)
text("+", X5, ky(1) - 1.9, 0.9)
text("-", XG, ky(1) - 1.9, 0.9)
text("S  +  -", X5, ky(13) + 2.2, 0.8)
# OLED
for x, s in [(35.56, "G"), (38.1, "V"), (40.64, "C"), (43.18, "D")]:
    text(s, x, OLED_Y - 2.0, 0.8)
text("OLED", 39.37, 2.2, 0.9)
# Spare IO
for k in [6, 7, 8, 9, 10, 11, 13]:
    text(LEFT[k - 1][1:], 4.1, ky(k), 0.8, just="left")
for k, s in [(14, "G"), (15, "5V")]:
    text(s, 4.1, ky(k), 0.8, just="left")
# Regulator module outline + pin labels
rect(XU - 1.3, U_TOP, XU - 1.3 + 20.3, U_TOP + 17.8, SILK, 0.15)
text("Pololu D24V50F5", 58.2, 12.0, 1.0)
text("5V 5A", 58.2, 14.0, 1.0)
for n, s in enumerate(["EN", "VIN", "GND", "GND", "OUT"]):
    text(s, XU + 1.6, uy(n + 1), 0.8, just="left")
# Power
text("SWITCH", 47.9, 42.7, 0.8, angle=90)
text("BATT 3S", 63.0, 38.5, 1.0)
text("BAT -> GPIO34 (x4.70)", 17.8, 47.2, 0.8)
text("SESAME DEVKIT CARRIER v1", 35.0, H - 1.6, 1.1)

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

# No copper under the ESP32-WROOM antenna
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
for x, y in [(9.0, 0.3), (32.0, 0.3), (32.0, 10.5), (9.0, 10.5)]:
    ko.Append(FromMM(x), FromMM(y))
board.Add(k)

# GND stitching vias in open areas
for xy in [(20.3, 13.0), (20.3, 30.0), (27.0, 36.0), (27.0, 20.0), (14.0, 26.0), (45.0, 27.0), (45.0, 37.0),
           (62.0, 26.0), (62.0, 33.0), (52.0, 54.5), (30.0, 55.5), (12.0, 55.5), (44.5, 3.0), (5.0, 22.0),
           (5.0, 12.0), (55.0, 37.0), (60.0, 42.0)]:
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
