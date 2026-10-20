"""Short-risk check for the carrier board. Plain Python (no KiCad): reads the .kicad_pcb as text, measures every
pair of different-net copper on each layer, ranks solder-bridge candidates by what a short would do, and fails if
the safety margins below are not met.

    python short_check.py sesame-devkit-carrier.kicad_pcb
"""
import sys, math, re, collections

src = open(sys.argv[1] if len(sys.argv) > 1 else "sesame-devkit-carrier.kicad_pcb", encoding="utf8").read()


def parse(s):
    toks = re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+', s)
    stack, cur = [], []
    for t in toks:
        if t == "(":
            stack.append(cur); cur = []
        elif t == ")":
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur[0]


def kids(n, name):
    return [c for c in n if isinstance(c, list) and c and c[0] == name]


def kid(n, name):
    k = kids(n, name)
    return k[0] if k else None


root = parse(src)
LAYERS = ("F.Cu", "B.Cu")


def rot(x, y, deg):
    a = math.radians(-deg)          # KiCad y-down, angles counter-clockwise on screen
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def circle_poly(cx, cy, r, n=48):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def segs_of(poly):
    return [(poly[k], poly[(k + 1) % len(poly)]) for k in range(len(poly))]


def capsule(a, b, w):
    # track as polygon: two half circles + sides
    r = w / 2
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    pts = []
    for k in range(25):
        t = ang + math.pi / 2 + math.pi * k / 24
        pts.append((b[0] + r * math.cos(t - math.pi), b[1] + r * math.sin(t - math.pi)))
    for k in range(25):
        t = ang + math.pi / 2 + math.pi * k / 24
        pts.append((a[0] + r * math.cos(t), a[1] + r * math.sin(t)))
    return pts


items = {l: [] for l in LAYERS}
fp_holes = []
for fp in kids(root, "footprint"):
    at = kid(fp, "at"); fx, fy = float(at[1]), float(at[2]); fr = float(at[3]) if len(at) > 3 else 0
    ref = next((p[2] for p in kids(fp, "property") if p[1] == "Reference"), "?")
    for pad in kids(fp, "pad"):
        num, typ, shape = pad[1], pad[2], pad[3]
        pat = kid(pad, "at"); px, py = float(pat[1]), float(pat[2]); pr = float(pat[3]) if len(pat) > 3 else 0
        dx, dy = rot(px, py, fr); cx, cy = fx + dx, fy + dy
        if typ == "np_thru_hole":
            fp_holes.append((ref, cx, cy)); continue
        w, h = float(kid(pad, "size")[1]), float(kid(pad, "size")[2])
        if shape == "circle":
            poly = circle_poly(cx, cy, w / 2)
        else:  # rect, roundrect (real corner radius), oval (radius = half the short side)
            if shape == "oval":
                r = min(w, h) / 2
            elif shape == "roundrect":
                r = float(kid(pad, "roundrect_rratio")[1]) * min(w, h)
            else:
                r = 0.0
            poly = []
            for (sx, sy, a0) in ((1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)):
                ccx, ccy = sx * (w / 2 - r), sy * (h / 2 - r)
                for k in range(13):
                    t = math.radians(a0 + 90 * k / 12)
                    ru, rv = rot(ccx + r * math.cos(t), ccy + r * math.sin(t), pr)
                    poly.append((cx + ru, cy + rv))
        net = kid(pad, "net")[1] if kid(pad, "net") else ""
        for l in LAYERS:
            items[l].append(dict(kind="pad", name=f"{ref}.{num}", net=net, segs=segs_of(poly), c=(cx, cy)))
for t in kids(root, "segment"):
    a = tuple(map(float, kid(t, "start")[1:3])); b = tuple(map(float, kid(t, "end")[1:3]))
    items[kid(t, "layer")[1]].append(dict(kind="track", name=f"track {kid(t,'width')[1]}", net=kid(t, "net")[1],
                                          segs=segs_of(capsule(a, b, float(kid(t, "width")[1])))))
for v in kids(root, "via"):
    x, y = map(float, kid(v, "at")[1:3])
    for l in LAYERS:
        items[l].append(dict(kind="via", name="via", net=kid(v, "net")[1], segs=segs_of(circle_poly(x, y, float(kid(v, "size")[1]) / 2))))
for z in kids(root, "zone"):
    if kid(z, "keepout") is not None or kid(z, "net") is None:
        continue
    for fpoly in kids(z, "filled_polygon"):
        pts = [(float(p[1]), float(p[2])) for p in kid(fpoly, "pts") if p[0] == "xy"]
        items[kid(fpoly, "layer")[1]].append(dict(kind="zone", name=f"{kid(z,'net')[1]} fill", net=kid(z, "net")[1], segs=segs_of(pts)))
for l in items:
    for it in items[l]:
        xs = [p[0] for s in it["segs"] for p in s]; ys = [p[1] for s in it["segs"] for p in s]
        it["bb"] = (min(xs), min(ys), max(xs), max(ys))


def pseg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def cr(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def segseg(a, b, c, d):
    if cr(a, b, c) * cr(a, b, d) < 0 and cr(c, d, a) * cr(c, d, b) < 0:
        return 0.0
    return min(pseg(a, c, d), pseg(b, c, d), pseg(c, a, b), pseg(d, a, b))


def dist(A, B, lim):
    best = 99
    bb = B["bb"]
    for s in A["segs"]:
        x0, x1 = sorted((s[0][0], s[1][0])); y0, y1 = sorted((s[0][1], s[1][1]))
        if x1 + lim < bb[0] or x0 - lim > bb[2] or y1 + lim < bb[1] or y0 - lim > bb[3]:
            continue
        for t in B["segs"]:
            if max(t[0][0], t[1][0]) < x0 - lim or min(t[0][0], t[1][0]) > x1 + lim or max(t[0][1], t[1][1]) < y0 - lim or min(t[0][1], t[1][1]) > y1 + lim:
                continue
            best = min(best, segseg(s[0], s[1], t[0], t[1]))
    return best


def unc(n):
    return n == "" or n.startswith("unconnected-")


def cls(n):
    return {"VBAT": "BATT", "VBAT_SW": "BATT", "+5V": "5V", "+3V3": "3V3", "GND": "GND"}.get(n, "NC" if unc(n) else "SIG")


def severity(a, b):
    c = {cls(a), cls(b)}
    if "NC" in c: return 0, "unused pin"
    if "BATT" in c: return 4, "battery dead short" if "GND" in c else "12.6 V into 5V/3.3V parts"
    if c == {"5V", "GND"}: return 3, "5V rail shorted to GND"
    if "5V" in c: return 3, "5V into an ESP32 3.3V pin"
    if c == {"3V3", "GND"}: return 2, "DevKit 3.3V shorted to GND"
    return 1, "signal fault"


LIM = 1.6
pairs = []
for l, its in items.items():
    for i, A in enumerate(its):
        for B in its[i + 1:]:
            if A["net"] == B["net"] or (unc(A["net"]) and unc(B["net"])):
                continue
            a, b = A["bb"], B["bb"]
            if a[0] - LIM > b[2] or b[0] - LIM > a[2] or a[1] - LIM > b[3] or b[1] - LIM > a[3]:
                continue
            if A["kind"] == "zone" and B["kind"] == "zone":
                continue
            d = dist(A, B, LIM)
            if d < LIM:
                pairs.append((d, l, A, B))

print(f"{sum(len(v) for v in items.values())} copper shapes, {len(pairs)} different-net pairs closer than {LIM} mm")
print("solder mask: 0 mm expansion (opening = pad), vias tented both sides -> only pads are exposed copper\n")

print("== 1. tightest copper-to-copper clearance by type ==")
cat = {}
for d, l, A, B in pairs:
    k = " / ".join(sorted((A["kind"], B["kind"])))
    if k not in cat or d < cat[k][0]:
        cat[k] = (d, l, A, B)
for k, (d, l, A, B) in sorted(cat.items(), key=lambda x: x[1][0]):
    print(f"  {k:14s} {d:.3f} mm  {l}  {A['name']} ({A['net']})  <->  {B['name']} ({B['net']})")

print("\n== 2. solder-bridge candidates: exposed pad <-> exposed pad ==")
pp = {}
for d, l, A, B in pairs:
    if A["kind"] == B["kind"] == "pad":
        k = tuple(sorted((A["name"], B["name"])))
        pp[k] = min(pp.get(k, (99,)), (d, A, B))
rows = sorted(((severity(A["net"], B["net"]), d, A, B) for d, A, B in pp.values()), key=lambda r: (-r[0][0], r[1]))
names = {4: "CRITICAL", 3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "NONE"}
hist = collections.Counter(r[0][0] for r in rows)
print("  pad pairs by what a bridge would do: " + ", ".join(f"{names[s]} {hist[s]}" for s in (4, 3, 2, 1, 0)))
for (sev, why), d, A, B in rows:
    if sev >= 2:
        print(f"  {names[sev]:8s} gap {d:.2f} mm  {A['name']:6s} ({A['net']}) <-> {B['name']:6s} ({B['net']})  {why}")
print(f"  narrowest gap between any two pads: {min(r[1] for r in rows):.2f} mm (= solder-mask dam width)")

print("\n== 3. closest masked copper (tracks / fill) to an exposed pad, HIGH/CRITICAL only ==")
tp = []
for d, l, A, B in pairs:
    if (A["kind"] == "pad") != (B["kind"] == "pad"):
        pad, oth = (A, B) if A["kind"] == "pad" else (B, A)
        sev, why = severity(pad["net"], oth["net"])
        if sev >= 3:
            tp.append((d, l, pad, oth, why))
seen = set()
for d, l, pad, oth, why in sorted(tp, key=lambda x: x[0]):
    k = (pad["name"], oth["name"], oth["net"])
    if k in seen: continue
    seen.add(k)
    if len(seen) > 10: break
    print(f"  {d:.3f} mm {l}  pad {pad['name']} ({pad['net']}) <-> {oth['name']} ({oth['net']})  {why}")

print("\n== 4. what sits under each screw head (socket head M2.5 r2.25 / M2 r1.9, +0.2 mm) ==")
for ref, cx, cy in fp_holes:
    rad = (1.9 if ref.startswith("HP") else 2.25) + 0.2
    found = set()
    for l, its in items.items():
        for it in its:
            if any(pseg((cx, cy), s[0], s[1]) < rad for s in it["segs"]):
                found.add(f"{l}:{it['net']}" + ("" if it["kind"] == "zone" else f" {it['kind']}"))
    print(f"  {ref:4s} ({cx:.2f},{cy:.2f}): {', '.join(sorted(found)) or 'bare board'}")

# ---------------------------------------------------------------- margins (fail the check if any is broken)
fails = []
for (sev, why), d, A, B in rows:
    if sev >= 4 and d < 0.84 - 1e-6:
        fails.append(f"battery pads {A['name']}/{B['name']} only {d:.2f} mm apart (need >= 0.84, a 2.54 mm-pitch pin gap)")
    if d < 0.8:
        fails.append(f"pads {A['name']}/{B['name']} only {d:.2f} mm apart (need >= 0.8)")
for d, l, A, B in pairs:
    k = {A["kind"], B["kind"]}
    if "zone" in k and d < 0.5 - 0.01:
        fails.append(f"ground fill {d:.2f} mm from {A['name'] if A['kind'] != 'zone' else B['name']} (need >= 0.5)")
    if k == {"track", "via"} and d < 0.5:
        fails.append(f"via {d:.2f} mm from a {A['net'] if A['kind'] == 'track' else B['net']} track (need >= 0.5)")
    if severity(A["net"], B["net"])[0] >= 3 and d < 0.4:
        fails.append(f"{A['name']} ({A['net']}) {d:.2f} mm from {B['name']} ({B['net']}) (need >= 0.4 between power nets)")
print()
print("\n".join("FAIL " + f for f in sorted(set(fails))) if fails else "SHORT CHECK PASSED")
sys.exit(1 if fails else 0)
