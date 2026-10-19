# Generates sesame-devkit-carrier.kicad_sch from the board, so ERC, schematic/PCB parity and schematic-based
# review tools can run. Parts, values, footprints and connections come from the .kicad_pcb (build_board.py is the
# source of truth); pin names and electrical types come from the DevKit's labels and Pololu's documentation.
# Run with KiCad's bundled python after build_board.py:  "<KiCad>/bin/python.exe" gen_schematic.py
import os
import re
import pcbnew
from sesame_ids import uid, symbol_uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "sesame-devkit-carrier.kicad_pcb")
OUT = os.path.join(HERE, "sesame-devkit-carrier.kicad_sch")
SYMLIB = os.path.join(os.path.dirname(pcbnew.__file__), "..", "..", "share", "kicad", "symbols")
if not os.path.isdir(SYMLIB):
    SYMLIB = r"C:\Users\acehu\AppData\Local\Programs\KiCad\10.0\share\kicad\symbols"
PROJECT = "sesame-devkit-carrier"
ROOT = uid("root-sheet")

# ---------------------------------------------------------------- tiny s-expression reader for .kicad_sym
def tokenize(text):
    for m in re.finditer(r'\s*(\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+)', text):
        yield m.group(1)

def parse(text):
    stack = [[]]
    for tok in tokenize(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    return stack[0][0]

def dump(node, indent=1):
    if not isinstance(node, list):
        return node
    if all(not isinstance(n, list) for n in node):
        return "(" + " ".join(node) + ")"
    pad = "\t" * indent
    head = [n for n in node if not isinstance(n, list)]
    body = [n for n in node if isinstance(n, list)]
    return "(" + " ".join(head) + "".join("\n" + pad + dump(n, indent + 1) for n in body) + "\n" + "\t" * (indent - 1) + ")"

_libs = {}
def lib_symbol(lib_id):
    lib, name = lib_id.split(":")
    if lib not in _libs:
        _libs[lib] = parse(open(os.path.join(SYMLIB, lib + ".kicad_sym"), encoding="utf8").read())
    for n in _libs[lib]:
        if isinstance(n, list) and n[:2] == ["symbol", '"%s"' % name]:
            sym = [x for x in n]
            sym[1] = '"%s"' % lib_id
            return sym
    raise KeyError(lib_id)

# ---------------------------------------------------------------- custom symbols (DevKit rows, Pololu module)
def row_symbol(lib_id, title, pins):
    """Single-row module header: pins on the right, numbered top to bottom. pins = [(name, etype), ...]"""
    n = len(pins)
    bottom = -2.54 * n
    body = (f'(symbol "{lib_id.split(":")[1]}_0_1" (rectangle (start -7.62 2.54) (end 7.62 {bottom:.2f}) '
            f'(stroke (width 0.254) (type default)) (fill (type background))))')
    pin_s = "".join(
        f'(pin {etype} line (at 10.16 {-2.54 * i:.2f} 180) (length 2.54) '
        f'(name "{name}" (effects (font (size 1.27 1.27)))) (number "{i + 1}" (effects (font (size 1.27 1.27)))))'
        for i, (name, etype) in enumerate(pins))
    text = (f'(symbol "{lib_id}" (pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes) '
            f'(property "Reference" "J" (at 0 5.08 0) (effects (font (size 1.27 1.27)))) '
            f'(property "Value" "{title}" (at 0 3.556 0) (effects (font (size 1.27 1.27)))) '
            f'(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'(property "Description" "{title}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes))) '
            f'{body} (symbol "{lib_id.split(":")[1]}_1_1" {pin_s}))')
    return parse(text)

GPIO = "bidirectional"
DEVKIT_L = [("EN", "input"), ("VP", "input"), ("VN", "input"), ("D34", "input"), ("D35", "input"),
            ("D32", GPIO), ("D33", GPIO), ("D25", GPIO), ("D26", GPIO), ("D27", GPIO), ("D14", GPIO),
            ("D12", GPIO), ("D13", GPIO), ("GND", "power_in"), ("VIN", "power_in")]
DEVKIT_R = [("D23", GPIO), ("D22", GPIO), ("TX0", "output"), ("RX0", "input"), ("D21", GPIO), ("D19", GPIO),
            ("D18", GPIO), ("D5", GPIO), ("TX2", GPIO), ("RX2", GPIO), ("D4", GPIO), ("D2", GPIO), ("D15", GPIO),
            ("GND", "power_in"), ("3V3", "power_out")]
POLOLU = [("EN", "input"), ("VIN", "power_in"), ("GND", "power_in"), ("GND", "power_in"), ("VOUT", "power_out")]
CUSTOM = {
    "Sesame:ESP32_DevKit_Row_L": row_symbol("Sesame:ESP32_DevKit_Row_L", "ESP32 DevKit 30-pin, EN..VIN row", DEVKIT_L),
    "Sesame:ESP32_DevKit_Row_R": row_symbol("Sesame:ESP32_DevKit_Row_R", "ESP32 DevKit 30-pin, D23..3V3 row", DEVKIT_R),
    "Sesame:Pololu_D24V50F5": row_symbol("Sesame:Pololu_D24V50F5", "Pololu D24V50F5 5V 5A step-down", POLOLU),
}

def symbol_def(lib_id):
    return CUSTOM[lib_id] if lib_id in CUSTOM else lib_symbol(lib_id)

def pins_of(sym):
    """{number: (x, y, angle, name)} in symbol coordinates (y up)."""
    out = {}
    def walk(n):
        if isinstance(n, list):
            if n and n[0] == "pin":
                at = next(c for c in n if isinstance(c, list) and c[0] == "at")
                num = next(c for c in n if isinstance(c, list) and c[0] == "number")[1].strip('"')
                name = next(c for c in n if isinstance(c, list) and c[0] == "name")[1].strip('"')
                out[num] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, name)
            for c in n:
                walk(c)
    walk(sym)
    return out

# ---------------------------------------------------------------- what goes on the sheet
board = pcbnew.LoadBoard(PCB)
fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

def lib_for(ref):
    if ref == "J1": return "Sesame:ESP32_DevKit_Row_L"
    if ref == "J2": return "Sesame:ESP32_DevKit_Row_R"
    if ref == "U1": return "Sesame:Pololu_D24V50F5"
    if ref in ("R1", "R2"): return "Device:R"
    if ref in ("C1", "C3"): return "Device:C_Polarized"
    if ref == "C2": return "Device:C"
    if ref.startswith("H"): return "Mechanical:MountingHole"
    n = len([p for p in fps[ref].Pads() if p.GetNumber()])
    return "Connector_Generic:Conn_01x%02d" % n

# sheet placement (mm, on the 2.54 grid): (x, y)
PLACE = {"J2": (45.72, 40.64), "J1": (45.72, 109.22),
         "U1": (281.94, 45.72), "J6": (288.29, 99.06), "SW1": (288.29, 121.92),
         "C1": (342.9, 109.22), "C3": (373.38, 109.22),
         "R1": (134.62, 124.46), "R2": (162.56, 124.46), "C2": (190.5, 124.46),
         "J3": (134.62, 182.88), "J4": (190.5, 182.88), "J5": (246.38, 182.88)}
for i, s in enumerate(["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]):
    PLACE[s] = (139.7 + (i % 4) * 30.48, 35.56 + (i // 4) * 35.56)
holes = sorted(r for r in fps if r.startswith("H"))
for i, h in enumerate(holes):
    PLACE[h] = (40.64 + i * 15.24, 241.3)
FLAG_SPOTS = {"GND": (342.9, 177.8), "VBAT_SW": (342.9, 30.48)}

POWER = {"GND": "power:GND", "+5V": "power:+5V", "+3V3": "power:+3V3"}
FLAGGED = {"GND", "VBAT_SW"}       # nets driven from off-sheet sources (battery, ground return)

items, used_libs = [], set()
counters = {"#PWR": 0, "#FLG": 0}

def eff(size=1.27, hide=False, justify=None):
    j = f" (justify {justify})" if justify else ""
    h = " (hide yes)" if hide else ""
    return f"(effects (font (size {size} {size})){j}{h})"

def place_symbol(lib_id, ref, value, footprint, x, y, angle=0, pin_nums=(), suid=None, in_bom=True,
                 value_at=None, hide_value=False, value_angle=0):
    used_libs.add(lib_id)
    suid = suid or uid("sym", ref, x, y)
    pins = "".join(f'(pin "{n}" (uuid "{uid(suid, "pin", n)}"))' for n in pin_nums)
    hide_ref = ref.startswith("#")
    return (f'(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} {angle}) (unit 1) (exclude_from_sim no) '
            f'(in_bom {"yes" if in_bom else "no"}) (on_board {"no" if ref.startswith("#") else "yes"}) (dnp no) '
            f'(uuid "{suid}") '
            f'(property "Reference" "{ref}" (at {x:.2f} {y - 5.08:.2f} 0) {eff(hide=hide_ref)}) '
            f'(property "Value" "{value}" (at {(value_at or (x, y - 3.3))[0]:.2f} {(value_at or (x, y - 3.3))[1]:.2f} {value_angle}) {eff(hide=hide_value)}) '
            f'(property "Footprint" "{footprint}" (at {x:.2f} {y:.2f} 0) {eff(hide=True)}) '
            f'(property "Datasheet" "" (at {x:.2f} {y:.2f} 0) {eff(hide=True)}) '
            f'(property "Description" "" (at {x:.2f} {y:.2f} 0) {eff(hide=True)}) '
            f'{pins} (instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1)))))')

# power symbols point away from the pin: GND's body is "down" in symbol space, +5V/+3V3 bodies are "up"
GND_ROT = {(1, 0): 90, (-1, 0): 270, (0, 1): 0, (0, -1): 180}
SUPPLY_ROT = {(1, 0): 270, (-1, 0): 90, (0, 1): 180, (0, -1): 0}

def power_at(net, x, y, outward=(0, 1)):
    counters["#PWR"] += 1
    ref = "#PWR%02d" % counters["#PWR"]
    rot = (GND_ROT if net == "GND" else SUPPLY_ROT)[outward]
    vx, vy = x + outward[0] * 7.0, y + outward[1] * 6.0
    return place_symbol(POWER[net], ref, net, "", x, y, rot, ["1"], suid=uid("pwr", ref), in_bom=False,
                        value_at=(vx, vy), value_angle=rot)   # field angle adds to the symbol's, so this reads level

def flag_at(x, y):
    counters["#FLG"] += 1
    ref = "#FLG%02d" % counters["#FLG"]
    return place_symbol("power:PWR_FLAG", ref, "PWR_FLAG", "", x, y, 0, ["1"], suid=uid("flg", ref), in_bom=False)

def label_at(net, x, y, outward):
    angle = {(1, 0): 0, (-1, 0): 180, (0, 1): 270, (0, -1): 90}[outward]
    just = "left" if angle in (0, 90) else "right"
    return (f'(global_label "{net}" (shape passive) (at {x:.2f} {y:.2f} {angle}) (fields_autoplaced yes) '
            f'{eff(justify=just)} (uuid "{uid("lbl", net, x, y)}") '
            f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x:.2f} {y:.2f} 0) {eff(justify=just, hide=True)}))')

def wire(a, b):
    return (f'(wire (pts (xy {a[0]:.2f} {a[1]:.2f}) (xy {b[0]:.2f} {b[1]:.2f})) (stroke (width 0) (type default)) '
            f'(uuid "{uid("wire", a, b)}"))')

flags_done = set()
for ref, fp in sorted(fps.items()):
    lid = lib_for(ref)
    sdef = symbol_def(lid)
    pins = pins_of(sdef)
    x, y = PLACE[ref]
    pads = {p.GetNumber(): p.GetNetname() for p in fp.Pads() if p.GetNumber()}
    items.append(place_symbol(lid, ref, fp.GetValue(), fp.GetFPIDAsString(), x, y, 0, sorted(pins), suid=symbol_uuid(ref),
                              in_bom=not fp.IsExcludedFromBOM(), hide_value=ref.startswith("H")))
    for num, (px, py, pang, pname) in pins.items():
        net = pads.get(num, "")
        cx, cy = x + px, y - py                                   # symbol y-up -> sheet y-down
        out = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(pang) % 360]
        if not net or net.startswith("unconnected-"):
            items.append(f'(no_connect (at {cx:.2f} {cy:.2f}) (uuid "{uid("nc", ref, num)}"))')
            continue
        ex, ey = cx + out[0] * 5.08, cy + out[1] * 5.08
        items.append(wire((cx, cy), (ex, ey)))
        if net in POWER:
            items.append(power_at(net, ex, ey, out))
        else:
            items.append(label_at(net, ex, ey, out))

# Power flags for nets fed from off the sheet (battery, ground return), each in its own spot
for net, (fx, fy) in FLAG_SPOTS.items():
    items.append(flag_at(fx, fy))
    items.append(wire((fx, fy), (fx, fy + 5.08)))
    if net in POWER:
        items.append(power_at(net, fx, fy + 5.08, (0, 1)))
    else:
        items.append(label_at(net, fx, fy + 5.08, (0, 1)))

used_libs |= {"power:PWR_FLAG"}
lib_text = "\n\t\t".join(dump(symbol_def(l), 3) for l in sorted(used_libs))
sheet = f'''(kicad_sch
\t(version 20250610)
\t(generator "sesame_gen_schematic")
\t(generator_version "1.0")
\t(uuid "{ROOT}")
\t(paper "A3")
\t(title_block (title "Sesame DevKit Carrier v1") (comment 1 "Generated from the PCB by gen_schematic.py; build_board.py is the source of truth"))
\t(lib_symbols
\t\t{lib_text}
\t)
\t''' + "\n\t".join(items) + f'''
\t(sheet_instances (path "/" (page "1")))
\t(embedded_fonts no)
)
'''
open(OUT, "w", encoding="utf8").write(sheet)

# Project library tables (self-contained, so ERC/parity work without global KiCad setup) + the custom symbols
def renamed(sym):
    out = list(sym)
    out[1] = '"%s"' % sym[1].strip('"').split(":")[1]
    return out

custom = "\n\t".join(dump(renamed(sym), 2) for sym in CUSTOM.values())
open(os.path.join(HERE, "Sesame.kicad_sym"), "w", encoding="utf8").write(
    '(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "sesame_gen_schematic")\n\t' + custom + "\n)\n")

def sym_uri(lib):
    return "${KIPRJMOD}/Sesame.kicad_sym" if lib == "Sesame" else "${KICAD10_SYMBOL_DIR}/%s.kicad_sym" % lib

sym_libs = sorted({l.split(":")[0] for l in used_libs})
open(os.path.join(HERE, "sym-lib-table"), "w", encoding="utf8").write(
    "(sym_lib_table\n\t(version 7)\n"
    + "".join('\t(lib (name "%s") (type "KiCad") (uri "%s") (options "") (descr ""))\n' % (l, sym_uri(l)) for l in sym_libs)
    + ")\n")
fp_libs = sorted({str(fp.GetFPID().GetLibNickname()) for fp in fps.values()})
open(os.path.join(HERE, "fp-lib-table"), "w", encoding="utf8").write(
    "(fp_lib_table\n\t(version 7)\n"
    + "".join('\t(lib (name "%s") (type "KiCad") (uri "%s") (options "") (descr ""))\n'
              % (l, "${KIPRJMOD}/Sesame.pretty" if l == "Sesame" else "${KICAD10_FOOTPRINT_DIR}/%s.pretty" % l)
              for l in fp_libs)
    + ")\n")
print("saved", OUT, "-", len(fps), "symbols")
