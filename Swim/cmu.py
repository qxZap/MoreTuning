"""CMU Graphics Lab motion capture (mocap.cs.cmu.edu, free for any use) -- ASF/AMC reader and FK.

    python cmu.py fetch                       # the swimming takes -> D:/MT/SwimCook/cmu/
    python cmu.py info 126_10                 # performer orientation and arm-cycle period of a take

Standard Acclaim FK: bone local = C * M(dofs) * C^-1 with C from the ASF `axis`, M = Rz Ry Rx in the dof order
listed; a joint sits at its parent's end plus world_rot * direction * length. CMU is Y-up. Units do not matter:
only segment directions are retargeted (retarget.py).
"""
import os, sys, urllib.request
import numpy as np

DIR = "D:/MT/SwimCook/cmu"
TAKES = {  # subject 125 "Swimming", 126 "Swimming 2", all performed standing in the air
    "125": ["125_01", "125_06"], "126": ["126_03", "126_04", "126_05", "126_06", "126_10", "126_11", "126_12"]}


def fetch():
    os.makedirs(DIR, exist_ok=True)
    for subj, takes in TAKES.items():
        for name in [subj] + takes:
            ext = ".asf" if name == subj else ".amc"
            p = os.path.join(DIR, name + ext)
            if not os.path.exists(p):
                urllib.request.urlretrieve("http://mocap.cs.cmu.edu/subjects/%s/%s%s" % (subj, name, ext), p)
            print(p)


def rot(axis, deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    return {"x": np.array([[1, 0, 0], [0, c, -s], [0, s, c]]),
            "y": np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]),
            "z": np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])}[axis]


def euler_xyz(v): return rot("z", v[2]) @ rot("y", v[1]) @ rot("x", v[0])


class Skeleton:
    def __init__(self, path):
        self.bones = {"root": {"dir": np.zeros(3), "len": 0.0, "C": np.eye(3), "dof": ["tx", "ty", "tz", "rx", "ry", "rz"]}}
        self.children = {}; self.order = ["root"]
        lines = [l.strip() for l in open(path)]; i = 0; sec = None; cur = None
        while i < len(lines):
            l = lines[i]
            if l.startswith(":"): sec = l.split()[0]
            elif sec == ":bonedata":
                t = l.split()
                if t and t[0] == "begin": cur = {"dof": []}
                elif t and t[0] == "name": cur["name"] = t[1]
                elif t and t[0] == "direction": cur["dir"] = np.array(list(map(float, t[1:4])))
                elif t and t[0] == "length": cur["len"] = float(t[1])
                elif t and t[0] == "axis": cur["C"] = euler_xyz(list(map(float, t[1:4])))
                elif t and t[0] == "dof": cur["dof"] = t[1:]
                elif t and t[0] == "end": self.bones[cur["name"]] = cur
            elif sec == ":hierarchy":
                t = l.split()
                if t and t[0] not in ("begin", "end"):
                    self.children[t[0]] = t[1:]
            i += 1
        self.parent = {}
        stack = ["root"]; self.order = []
        while stack:
            b = stack.pop(0); self.order.append(b)
            for c in self.children.get(b, []): self.parent[c] = b; stack.append(c)


def read_amc(path):
    frames = []; cur = None
    for l in open(path):
        t = l.split()
        if not t or l.startswith(("#", ":")): continue
        if len(t) == 1 and t[0].isdigit(): cur = {}; frames.append(cur); continue
        cur[t[0]] = list(map(float, t[1:]))
    return frames


def fk(sk, fr):
    """-> {bone: (world rotation 3x3, start position, end position)}"""
    out = {}
    for b in sk.order:
        bd = sk.bones[b]; vals = fr.get(b, []); M = np.eye(3); t = np.zeros(3)
        for d, v in zip(bd["dof"], vals):
            if d[0] == "r": M = rot(d[1], v) @ M
            else: t["xyz".index(d[1])] = v
        L = bd["C"] @ M @ bd["C"].T
        if b == "root":
            R = L; start = t
        else:
            pR, _, pend = out[sk.parent[b]]; R = pR @ L; start = pend
        out[b] = (R, start, start + R @ bd["dir"] * bd["len"])
    return out


def load(take):
    subj = take.split("_")[0]
    sk = Skeleton(os.path.join(DIR, subj + ".asf"))
    return sk, read_amc(os.path.join(DIR, take + ".amc"))


def info(take):
    sk, frs = load(take)
    print(take, len(frs), "frames at 120 fps =", round(len(frs) / 120, 1), "s")
    P = [fk(sk, f) for f in frs[::4]]
    up = np.array([p["thorax"][2] - p["root"][2] for p in P]); up /= np.linalg.norm(up, axis=1)[:, None]
    print("  torso up (Y-up) mean", up.mean(0).round(2), "min y", up[:, 1].min().round(2))
    lh = np.array([p["lhand"][2] - p["lhumerus"][1] for p in P])
    y = lh[:, 1] - lh[:, 1].mean()
    f = np.abs(np.fft.rfft(y)); k = f[2:].argmax() + 2
    print("  left hand height: dominant period %.2f s" % (len(y) * 4 / 120 / k))


if __name__ == "__main__":
    if sys.argv[1] == "fetch": fetch()
    else: info(sys.argv[2])
