"""Procedural swimming cycles for the game's character skeleton (SK_MTCharacter, the Synty rig).

Each pose is written as rotations in the *standing* body frame of the mesh asset (X = the character's left,
Y = forward, Z = up; the character BP turns the mesh -90 yaw so asset +Y is actor +X): a bone's rotation is
relative to its parent's, applied about its own joint, and a bone with none rides along with its parent. The pelvis
carries the whole-body tilt T, which is how a prone swimmer is laid flat without the plugin rotating the actor.
That is turned into UE local transforms per frame (frames() -> {bone: (loc, rot, scale)}), which ue_anims.py keys and
preview.py renders. Every curve is periodic over the cycle, so frame 0 == the last frame and the loop is seamless.

    python swim_anim.py demo     # self-checks
    python swim_anim.py dump     # key positions per anim, for eyeballing
    python swim_anim.py export D:/MT/SwimCook/keys.json   # what ue_anims.py keys
"""
import sys
import numpy as np
from fk import B, N, IDX, PARENT, REF_R, REF_T, REF_S, REF_W, REF_P, qmul, qconj, qrot, qaxis, norm

FPS = 30
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
S, C, TAU = np.sin, np.cos, 2 * np.pi


def rx(d): return qaxis(X, d)
def ry(d): return qaxis(Y, d)
def rz(d): return qaxis(Z, d)


def chain(*qs):
    r = np.array([0, 0, 0, 1.0])
    for q in qs: r = qmul(r, q)
    return r


def periodic(keys, p):
    """Catmull-Rom through (phase, value...) keys on a closed loop; keys[0] at phase 0, wraps at 1."""
    ph = np.array([k[0] for k in keys]); v = np.array([k[1:] for k in keys], float)
    n = len(ph); i = np.searchsorted(ph, p % 1.0, side='right') - 1
    p0, p1 = ph[i], (ph[(i + 1) % n] if i + 1 < n else 1.0)
    u = ((p % 1.0) - p0) / (p1 - p0)
    a, b, c, d = v[(i - 1) % n], v[i], v[(i + 1) % n], v[(i + 2) % n]
    return 0.5 * (2 * b + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u + (-a + 3 * b - 3 * c + d) * u ** 3)


SIDE = {'L': 1, 'R': -1}       # left arm points +X in the T-pose
ARM = {'L': ('clavicle_l', 'UpperArm_L', 'lowerarm_l', 'Hand_L'), 'R': ('clavicle_r', 'UpperArm_R', 'lowerarm_r', 'Hand_R')}
LEG = {'L': ('Thigh_L', 'calf_l', 'Foot_L'), 'R': ('Thigh_R', 'calf_r', 'Foot_R')}


def overhead(s):
    """T-pose arm -> straight up (arm along +Z)"""
    return ry(-90 * s)


def elbow(s, deg):
    """forearm flexes toward the front (+Y in the T-pose)"""
    return rz(deg * s)


# ---------------------------------------------------------------- the cycles: p is the phase 0..1
def crawl(p):
    """front crawl, 1.2 s: body prone, arms windmill half a cycle apart, six-beat flutter kick"""
    rel = {}; T = rx(-83)          # prone, head a few degrees up
    roll = 32 * S(TAU * p)         # rolls toward the arm that is pulling
    rel['Pelvis'] = chain(T, rz(0.35 * roll))
    rel['spine_01'] = rz(0.2 * roll); rel['spine_02'] = rz(0.2 * roll); rel['spine_03'] = rz(0.25 * roll)
    rel['neck_01'] = chain(rz(-0.6 * roll), rx(14)); rel['head'] = rx(16)     # face forward-down, steady
    for side, s in SIDE.items():
        th = 360 * ((p + (0.0 if side == 'L' else 0.5)) % 1.0)   # 0 overhead (reach), 90 under chest, 180 at hip
        clav, up, low, hand = ARM[side]
        swing = rx(-th)                                          # through the front (under the body) on the pull
        d = qrot(chain(swing, overhead(s)), (s, 0, 0))
        rec = max(0.0, S(np.radians(th - 180)))                  # 0..1 over the recovery (above the back)
        out = np.cross(d, (s, 0, 0)); abd = 62 * rec               # recovery swings wide
        rel[up] = chain(qaxis(out, abd) if np.linalg.norm(out) > 1e-6 else rx(0), swing, overhead(s))
        bend = 20 + (75 * S(np.radians(th)) if th < 180 else 95 * rec)
        rel[low] = elbow(s, bend)
        rel[clav] = rz(-8 * s * C(np.radians(th)))             # shoulder reaches on the catch
    for side, ph in (('L', 0.0), ('R', 0.5)):
        th_, cf, ft = LEG[side]
        k = TAU * (3 * p + ph)                                   # three kicks per leg per stroke cycle
        rel[th_] = rx(12 * S(k))                                 # hip flexes forward (+Y), extends back
        rel[cf] = rx(-(8 + 14 * (0.5 + 0.5 * S(k + 1.2))))       # knee bends on the down-kick
        rel[ft] = rx(-62)                                        # toes pointed
    pel = np.array([0.0, -20.0, 150.0 + 1.5 * S(2 * TAU * p)])
    return rel, pel


def tread(p):
    """treading water, 2 s: upright, sculling arms, eggbeater legs"""
    rel = {}; T = rx(-8)            # slight forward lean
    rel['Pelvis'] = T
    rel['spine_02'] = rx(-4); rel['neck_01'] = rx(6); rel['head'] = rx(6)
    sc = S(2 * TAU * p)            # two sculls per cycle
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        yaw = 22 * sc * s           # sweep out (+) and in (-)
        aim = chain(rz(yaw), rz(55 * s), qaxis((0, 1, 0), 30 * s))  # out to the side-front, 30 deg under horizontal
        rel[up] = aim
        rel[low] = elbow(s, 45 + 10 * sc)
        rel[hand] = chain(qaxis(X, 28 * C(2 * TAU * p)), rz(-10 * s))   # palms pitch with the sweep
    for side, ph in (('L', 0.0), ('R', 0.5)):
        th_, cf, ft = LEG[side]; s = SIDE[side]
        k = TAU * (p + ph)
        rel[th_] = chain(rx(62 + 6 * S(k)), ry(-30 * s), rz(24 * s * S(k)))   # flexed, knees wide, circling
        rel[cf] = rx(-(88 + 18 * C(k)))
        rel[ft] = rx(12 * S(k + 1.0))
    pel = np.array([0.0, 4.0, 86.0 + 2.5 * S(2 * TAU * p - 0.8)])
    return rel, pel


DIVE_ARMS = [  # phase, abduction from overhead, flex toward the front (under the body), elbow
    (0.00, 4, 0, 4), (0.26, 4, 0, 4), (0.40, 50, 16, 25), (0.54, 62, 70, 95),
    (0.66, 18, 112, 140), (0.78, 4, 50, 100), (0.90, 4, 8, 20)]


def dive(p):
    """underwater breaststroke pull with a dolphin kick, 1.4 s: body horizontal, head down a little"""
    rel = {}; T = rx(-90)
    w = TAU * 2 * p                 # two kicks per stroke
    rel['Pelvis'] = chain(T, rx(5 * S(w)))
    rel['spine_01'] = rx(-5 * S(w - 0.6)); rel['spine_02'] = rx(-4 * S(w - 1.2)); rel['spine_03'] = rx(-3 * S(w - 1.8))
    rel['neck_01'] = rx(-6); rel['head'] = rx(-6)
    a, f, e = periodic(DIVE_ARMS, p)
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        rel[up] = chain(rx(-f), ry(a * s), overhead(s))
        rel[low] = elbow(s, e)
        rel[hand] = rx(-10 if 0.4 < p < 0.66 else 0)
    for side in ('L', 'R'):
        th_, cf, ft = LEG[side]; s = SIDE[side]
        rel[th_] = chain(rx(12 * S(w - 2.4) + 8), ry(-3 * s))
        rel[cf] = rx(-(5 + 22 * (0.5 + 0.5 * S(w - 1.4))))
        rel[ft] = rx(-68)
    pel = np.array([0.0, -20.0, 140.0 + 2.0 * S(w - 2.0)])
    return rel, pel


ANIMS = {'Swim_Crawl': (crawl, 1.2), 'Swim_Tread': (tread, 2.0), 'Swim_Dive': (dive, 1.4)}


# ---------------------------------------------------------------- pose -> UE local transforms
def pose(rel, pel):
    """standing-frame relative rotations + pelvis position (component space) -> world rot/pos per bone"""
    D = [None] * len(B); W = [None] * len(B); P = [None] * len(B)
    for i, par in enumerate(PARENT):
        r = rel.get(N[i], np.array([0, 0, 0, 1.0]))
        D[i] = r if par < 0 else norm(qmul(D[par], r))
        W[i] = norm(qmul(D[i], REF_W[i]))
        if par < 0: P[i] = REF_P[i]
        elif N[i] == 'Pelvis': P[i] = np.asarray(pel, float)
        else: P[i] = P[par] + qrot(D[par], REF_P[i] - REF_P[par])
    return W, P


def to_local(W, P):
    out = {}
    for i, par in enumerate(PARENT):
        if par < 0: out[N[i]] = (REF_T[i], REF_R[i], REF_S[i]); continue
        inv = qconj(W[par])
        loc = qrot(inv, P[i] - P[par]) if N[i] == 'Pelvis' else REF_T[i]
        out[N[i]] = (loc, norm(qmul(inv, W[i])), REF_S[i])
    return out


def frames(name):
    fn, length = ANIMS[name]
    n = int(round(length * FPS))
    res = []
    for f in range(n + 1):                      # n intervals, n + 1 keys; the last equals the first
        res.append(to_local(*pose(*fn(f / n))))
    for b in N:                                 # keep each track on one quaternion hemisphere
        for f in range(1, len(res)):
            l, q, s = res[f][b]
            if q @ res[f - 1][b][1] < 0: res[f][b] = (l, -q, s)
    return res, length


def world_frames(name):
    fn, length = ANIMS[name]; n = int(round(length * FPS))
    return [pose(*fn(f / n))[1] for f in range(n + 1)], length


# ---------------------------------------------------------------- checks
def demo():
    W, P = pose({}, REF_P[IDX['Pelvis']])
    loc = to_local(W, P)
    for i, b in enumerate(N):
        assert np.allclose(loc[b][0], REF_T[i], atol=1e-6) and abs(abs(loc[b][1] @ norm(REF_R[i])) - 1) < 1e-6, b
    for name in ANIMS:
        fr, L = frames(name)
        for b in N:
            assert np.allclose(fr[0][b][0], fr[-1][b][0], atol=1e-6), (name, b)
            assert abs(abs(fr[0][b][1] @ fr[-1][b][1]) - 1) < 1e-9, (name, b)
        Pw, _ = world_frames(name)
        head = np.array([p[IDX['head']] for p in Pw]); pel = np.array([p[IDX['Pelvis']] for p in Pw])
        toes = np.array([p[IDX['toes_l']] for p in Pw])
        if name != 'Swim_Tread':     # flat: head ahead of the pelvis along +Y, at about its height
            assert (head[:, 1] - pel[:, 1]).min() > 50 and abs(head[:, 2] - pel[:, 2]).max() < 25, name
            assert (toes[:, 1] < pel[:, 1] - 60).all(), name
        else:                        # upright: head above the pelvis
            assert (head[:, 2] - pel[:, 2]).min() > 55, name
    # the crawl's pull passes under the body, its recovery over it
    Pw, _ = world_frames('Swim_Crawl'); n = len(Pw) - 1
    hand = lambda f: Pw[f][IDX['Hand_L']] - Pw[f][IDX['spine_03']]
    assert hand(n // 4)[2] < -20 and hand(3 * n // 4)[2] > 0, (hand(n // 4), hand(3 * n // 4))
    assert hand(0)[1] > 40, hand(0)                # reach ahead at the catch
    print('demo ok')


def dump():
    for name in ANIMS:
        Pw, L = world_frames(name); n = len(Pw) - 1
        print(name, L, 's')
        for f in (0, n // 4, n // 2, 3 * n // 4):
            print('  f%-3d' % f, '  '.join('%s %s' % (b, np.round(Pw[f][IDX[b]]).astype(int).tolist())
                                         for b in ('Pelvis', 'head', 'Hand_L', 'Hand_R', 'Foot_L')))


def export(path):
    """keys for ue_anims.py (UE's Python has no numpy): {anim: {length, frames, bones: {bone: [[loc, rot, scale]...]}}}"""
    import json
    out = {}
    for name in ANIMS:
        fr, L = frames(name)
        out[name] = {'length': L, 'frames': len(fr) - 1,
                     'bones': {b: [[list(map(float, f[b][0])), list(map(float, f[b][1])), list(map(float, f[b][2]))] for f in fr] for b in N}}
    json.dump(out, open(path, 'w'))
    print('wrote', path)


if __name__ == '__main__':
    {'demo': demo, 'dump': dump, 'export': lambda: export(sys.argv[2])}[sys.argv[1]]()
