"""Swimming animations for the game's character skeleton (SK_MTCharacter, the Synty rig).

Loops (seamless: frame 0 == the last frame):
  Swim_Crawl    front crawl. Arms, torso and head retargeted from CMU mocap 125_06 (a swimmer doing free style
                prone "in the air"), legs a six-beat flutter kick (the performer's legs were on the support), and a
                breathing turn to the right once per cycle, i.e. every second stroke.
  Swim_Tread    treading water: eggbeater kick (hips flexed like sitting, knees wide, each lower leg circling,
                legs half a cycle apart) and sculling hands (in/out sweeps at chest depth, palms pitching).
  Swim_Dive     underwater breaststroke from CMU mocap 126_04, arms and frog kick, body flat, head down a little.
                Starts at the glide (arms furthest forward), which is where Swim_DiveIn ends and Swim_Surface begins.
One-shots (keyed poses, smooth through them; each starts and ends on a neighbouring pose):
  Swim_DiveIn   standing -> crouch, arms back -> launch, arms swing overhead -> head-first entry -> the dive glide.
  Swim_Surface  the dive glide -> big pull, body pitching up, head up -> treading.
  Swim_ClimbOut treading -> reach up -> press down on the edge, body rising -> knee up -> standing.

Procedural poses are rotations in the *standing* body frame of the mesh asset (X = the character's left, Y = forward,
Z = up; the character BP turns the mesh -90 yaw so asset +Y is actor +X): a bone's rotation is relative to its
parent's, about its own joint; a bone with none rides along with its parent. The pelvis carries the whole-body tilt T,
which is how a prone swimmer is laid flat without the plugin rotating the actor. Everything ends as UE local
transforms per frame (frames()), which ue_anims.py keys and preview.py renders.

    python swim_anim.py demo     # self-checks
    python swim_anim.py export D:/MT/SwimCook/keys.json   # what ue_anims.py keys
"""
import sys
from functools import lru_cache
import numpy as np
from fk import B, N, IDX, PARENT, REF_T, REF_S, REF_W, REF_P, qmul, qconj, qrot, qaxis, norm, world

FPS = 30
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
S, C, TAU = np.sin, np.cos, 2 * np.pi
ID = np.array([0, 0, 0, 1.0])

# pelvis heights in the mesh's space (actor Z = 0.9 * z - 85; the plugin floats the capsule centre 60 cm under the
# surface, so the surface is at mesh z ~161)
PEL_CRAWL = (0.0, -20.0, 150.0)
PEL_DIVE = (0.0, -20.0, 140.0)
PEL_TREAD_Z = 99.0         # head joint ~167, face above the surface
PEL_STAND = tuple(REF_P[IDX['Pelvis']])
CRAWL_HIP = 18.0  # legs_angle() ~ -3: legs trail a little under the body
DIVE_HIP = 5.0
BREATH = 70.0     # degrees the head rolls for a breath; + is to the right (face toward asset -X)


def rx(d): return qaxis(X, d)
def ry(d): return qaxis(Y, d)
def rz(d): return qaxis(Z, d)


def chain(*qs):
    r = ID
    for q in qs: r = qmul(r, q)
    return r


SIDE = {'L': 1, 'R': -1}       # left arm points +X in the T-pose
ARM = {'L': ('clavicle_l', 'UpperArm_L', 'lowerarm_l', 'Hand_L'), 'R': ('clavicle_r', 'UpperArm_R', 'lowerarm_r', 'Hand_R')}
LEG = {'L': ('Thigh_L', 'calf_l', 'Foot_L'), 'R': ('Thigh_R', 'calf_r', 'Foot_R')}


def overhead(s): return ry(-90 * s)          # T-pose arm -> straight up
def down(s): return ry(80 * s)               # T-pose arm -> hanging at the side
def elbow(s, deg): return rz(deg * s)        # forearm flexes toward the front (+Y in the T-pose)


# ---------------------------------------------------------------- pose plumbing
def pose(rel, pel):
    """standing-frame relative rotations + pelvis position -> world rot/pos per bone"""
    D = [None] * len(B); W = [None] * len(B); P = [None] * len(B)
    for i, par in enumerate(PARENT):
        r = rel.get(N[i], ID)
        D[i] = r if par < 0 else norm(qmul(D[par], r))
        W[i] = norm(qmul(D[i], REF_W[i]))
        if par < 0: P[i] = REF_P[i]
        elif N[i] == 'Pelvis': P[i] = np.asarray(pel, float)
        else: P[i] = P[par] + qrot(D[par], REF_P[i] - REF_P[par])
    return W, P


def to_local(W, P):
    """-> [(loc, rot)] in bone order"""
    out = []
    for i, par in enumerate(PARENT):
        if par < 0: out.append((REF_T[i], norm(B[i]['rot']))); continue
        inv = qconj(W[par])
        out.append((qrot(inv, P[i] - P[par]) if N[i] == 'Pelvis' else REF_T[i], norm(qmul(inv, W[i]))))
    return out


def rel_local(rel, pel): return to_local(*pose(rel, pel))


def slerp(a, b, t):
    a = norm(a); b = norm(b)
    if a @ b < 0: b = -b
    d = np.clip(a @ b, -1, 1)
    if d > 0.9995: return norm(a + t * (b - a))
    th = np.arccos(d); return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)


def keyed(keys, length):
    """one-shot from (time, local pose) keys: cubic Hermite per component through every key (C1; zero velocity at the
    two ends, so it starts and settles cleanly), quaternions kept on one hemisphere and renormalised"""
    ts = np.array([k[0] for k in keys]); poses = [k[1] for k in keys]
    nb = len(B); nf = int(round(length * FPS))
    out = []
    for k in range(nb):
        q = [poses[0][k][1]]
        for p in poses[1:]:
            q.append(p[k][1] if p[k][1] @ q[-1] >= 0 else -p[k][1])
        vals = np.array([np.concatenate([p[k][0], qq]) for p, qq in zip(poses, q)])
        tang = np.zeros_like(vals)
        for i in range(1, len(ts) - 1):
            tang[i] = (vals[i + 1] - vals[i - 1]) / (ts[i + 1] - ts[i - 1])
        col = []
        for f in range(nf + 1):
            t = f / FPS; i = min(np.searchsorted(ts, t, side='right') - 1, len(ts) - 2)
            h = ts[i + 1] - ts[i]; u = (t - ts[i]) / h
            h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
            v = h00 * vals[i] + h10 * h * tang[i] + h01 * vals[i + 1] + h11 * h * tang[i + 1]
            col.append((v[:3], norm(v[3:])))
        out.append(col)
    return [[out[k][f] for k in range(nb)] for f in range(nf + 1)]


def hip_flex(frames, deg):
    """flex both hips by deg about the body's lateral axis (mocap performers lay on a support with their hips bent;
    after the prone tilt, flexion lowers the legs)"""
    axis = qrot(qconj(REF_W[IDX['Pelvis']]), X)       # the lateral axis in the pelvis's local frame
    r = qaxis(axis, deg); ix = (IDX['Thigh_L'], IDX['Thigh_R'])
    return [[((l, norm(qmul(r, q))) if k in ix else (l, q)) for k, (l, q) in enumerate(f)] for f in frames]


def graft(frames, src, bones):
    """replace the local transforms of `bones` with those of src (same frame count)"""
    ix = [IDX[b] for b in bones]
    return [[(s[k] if k in ix else fr[k]) for k in range(len(B))] for fr, s in zip(frames, src)]


# ---------------------------------------------------------------- procedural cycles: p is the phase 0..1
def flutter(p):
    """six-beat flutter kick: three kicks per leg per stroke cycle, from the hip, knees loose, toes pointed"""
    rel = {}
    for side, ph in (('L', 0.0), ('R', 0.5)):
        th_, cf, ft = LEG[side]
        k = TAU * (3 * p + ph)
        rel[th_] = rx(13 * S(k) - 2)
        rel[cf] = rx(-(6 + 16 * (0.5 + 0.5 * S(k + 1.3))))   # the knee bends as the thigh starts down
        rel[ft] = rx(-60 - 8 * S(k + 2.0))                    # ankles floppy, toes pointed
    return rel


def tread(p):
    """eggbeater kick + sculling, 2 s: two leg circles and two sculls (out and in) per loop"""
    rel = {'Pelvis': rx(-6), 'spine_02': rx(-3), 'neck_01': rx(5), 'head': rx(3)}
    sc = TAU * 2 * p
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        # upper arm forward-out, a little under horizontal; sweeps out and in about the vertical
        rel[up] = chain(rz(18 * S(sc) * s), rz(48 * s), ry(18 * s))
        rel[low] = elbow(s, 55 - 12 * S(sc))                 # forearm across the front, opening on the outsweep
        rel[hand] = chain(qaxis(X, 32 * C(sc)), rz(-8 * s))  # palm pitches into each sweep
    for side, ph in (('L', 0.0), ('R', 0.5)):
        th_, cf, ft = LEG[side]; s = SIDE[side]
        k = TAU * (2 * p + ph)
        # thigh flexed like sitting on a chair, knees wide; the hip rotates about the thigh to swing the shin round
        rel[th_] = chain(rx(72 + 6 * S(k)), ry(-42 * s), rz(30 * s * S(k)))
        rel[cf] = rx(-(92 + 20 * C(k)))                        # with the knee opening a quarter cycle off: a circle
        rel[ft] = rx(18 + 10 * S(k + 1.0))                     # foot flexed (dorsi) to push water: the whip
    bob = 2.0 * S(TAU * 4 * p - 0.8)                           # each kick lifts a little
    return rel, (0.0, 4.0, PEL_TREAD_Z + bob)


def standing():
    """arms hanging, the pose the one-shots start or end in"""
    rel = {}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        rel[up] = down(s); rel[low] = elbow(s, 12)
    return rel, PEL_STAND


# ---------------------------------------------------------------- mocap loops
@lru_cache(None)
def mocap(take, period, length, pel, tilt=0.0):
    import retarget
    fr, info = retarget.cut(retarget.Take(take, tilt), period, length, pel)
    return fr, info


def crawl_frames(length=1.4):
    fr, info = mocap('125_06', 1.7, length, PEL_CRAWL, 6.0)
    n = len(fr) - 1
    legs = [rel_local(flutter(f / n), PEL_CRAWL) for f in range(n + 1)]
    fr = graft(fr, legs, ['Thigh_L', 'calf_l', 'Foot_L', 'Thigh_R', 'calf_r', 'Foot_R', 'ball_l', 'ball_r'])
    return breath(hip_flex(fr, CRAWL_HIP))


def breath(fr):
    """the breathing turn: the head rolls to the right about the body's long axis while the right arm finishes its
    push and recovers, ~40 % of the cycle, then back down as that arm enters. Added on top of the mocap's head."""
    n = len(fr) - 1
    hR = IDX['Hand_R']; sp = IDX['spine_03']
    # where in the cycle the right hand is furthest back (end of the push): the turn peaks a little after it
    back = []
    for f in range(n + 1):
        W, P = world([b[1] for b in fr[f]], [b[0] for b in fr[f]])
        back.append(P[hR][1] - P[sp][1])
    peak = (int(np.argmin(back)) / n + 0.08) % 1.0
    out = []
    for f in range(n + 1):
        p = f / n; d = (p - peak + 0.5) % 1.0 - 0.5                   # -0.5..0.5 around the peak
        w = 0.5 + 0.5 * C(np.pi * min(1.0, abs(d) / 0.2))               # 1 at the peak, 0 beyond +-0.2
        fr_f = list(fr[f])
        # roll about the neck's long axis (its local +X: the Synty spine and neck bones point along X); the head's
        # share is applied in the neck's frame too, so both turn about the same axis
        k = IDX['neck_01']; loc, q = fr_f[k]; fr_f[k] = (loc, norm(qmul(q, qaxis(X, BREATH * 0.45 * w))))
        k = IDX['head']; loc, q = fr_f[k]; fr_f[k] = (loc, norm(qmul(qaxis(X, BREATH * 0.55 * w), q)))
        out.append(fr_f)
    return out


def dive_frames(length=1.6):
    fr, info = mocap('126_04', 1.73, length, PEL_DIVE, -8.0)
    n = len(fr) - 1
    # start at the glide: hands furthest forward
    reach = []
    for f in range(n):
        W, P = world([b[1] for b in fr[f]], [b[0] for b in fr[f]])
        reach.append(P[IDX['Hand_L']][1] + P[IDX['Hand_R']][1])
    s = int(np.argmax(reach))
    return hip_flex(fr[s:n] + fr[:s] + [fr[s]], DIVE_HIP)


# ---------------------------------------------------------------- one-shots
def dive_in(length=1.0):
    st_rel, st_pel = standing()
    crouch = {'Pelvis': rx(-30), 'spine_02': rx(-8), 'neck_01': rx(10)}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        crouch[up] = chain(rx(40), down(s)); crouch[low] = elbow(s, 10)      # arms swung back
    for side in ('L', 'R'):
        th_, cf, ft = LEG[side]
        crouch[th_] = rx(75); crouch[cf] = rx(-95); crouch[ft] = rx(25)
    launch = {'Pelvis': rx(-72), 'neck_01': rx(-8), 'head': rx(-6)}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        launch[up] = chain(rx(-15), overhead(s), ry(8 * s)); launch[low] = elbow(s, 5)
    for side in ('L', 'R'):
        th_, cf, ft = LEG[side]
        launch[th_] = rx(-6); launch[cf] = rx(-8); launch[ft] = rx(-55)
    entry = {'Pelvis': rx(-112), 'neck_01': rx(-12), 'head': rx(-8)}         # head-first, ~20 deg under horizontal
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        entry[up] = chain(overhead(s), ry(4 * s)); entry[low] = elbow(s, 2)
    for side in ('L', 'R'):
        th_, cf, ft = LEG[side]
        entry[th_] = rx(8); entry[cf] = rx(-12); entry[ft] = rx(-68)
    glide = dive_frames()[0]
    keys = [(0.0, rel_local(st_rel, st_pel)), (0.28, rel_local(crouch, (0, 8, 64))),
            (0.52, rel_local(launch, (0, 12, 100))), (0.78, rel_local(entry, (0, 0, 128))), (length, glide)]
    return keyed(keys, length)


def surface(length=0.8):
    glide = dive_frames()[0]
    pull = {'Pelvis': rx(-48), 'spine_02': rx(6), 'neck_01': rx(22), 'head': rx(14)}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        pull[up] = chain(rx(-35), ry(55 * s)); pull[low] = elbow(s, 35)      # sweeping down and out
    for side, ph in (('L', 0), ('R', 1)):
        th_, cf, ft = LEG[side]
        pull[th_] = rx(35 + 15 * ph); pull[cf] = rx(-(70 - 20 * ph)); pull[ft] = rx(-20)
    keys = [(0.0, glide), (0.38, rel_local(pull, (0, -8, 118))), (length, rel_local(*tread(0.0)))]
    return keyed(keys, length)


def climb_out(length=0.8):
    rise = {'Pelvis': rx(-4), 'neck_01': rx(12)}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        rise[up] = chain(rx(-75), overhead(s), ry(10 * s)); rise[low] = elbow(s, 30)      # arms coming up in front
    for side in ('L', 'R'):
        th_, cf, ft = LEG[side]
        rise[th_] = rx(45); rise[cf] = rx(-80); rise[ft] = rx(-10)
    reach = {'Pelvis': rx(-4), 'neck_01': rx(10)}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        reach[up] = chain(rx(-25), overhead(s), ry(12 * s)); reach[low] = elbow(s, 20)   # up and forward, onto the edge
    for side in ('L', 'R'):
        th_, cf, ft = LEG[side]
        reach[th_] = rx(25); reach[cf] = rx(-60); reach[ft] = rx(-30)
    press = {'Pelvis': rx(-18), 'spine_02': rx(-6), 'neck_01': rx(8)}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        press[up] = chain(rx(30), down(s)); press[low] = elbow(s, 8)       # arms locked, pressing down by the hips
    for side in ('L', 'R'):
        th_, cf, ft = LEG[side]
        press[th_] = rx(5); press[cf] = rx(-15); press[ft] = rx(-50)       # legs driving down (the kick)
    knee = {'Pelvis': rx(-25), 'spine_02': rx(-6), 'neck_01': rx(10)}
    for side, s in SIDE.items():
        clav, up, low, hand = ARM[side]
        knee[up] = chain(rx(15), down(s)); knee[low] = elbow(s, 20)
    knee['Thigh_L'] = rx(95); knee['calf_l'] = rx(-110); knee['Foot_L'] = rx(15)     # left knee onto the edge
    knee['Thigh_R'] = rx(10); knee['calf_r'] = rx(-30); knee['Foot_R'] = rx(-35)
    st_rel, st_pel = standing()
    keys = [(0.0, rel_local(*tread(0.0))), (0.1, rel_local(rise, (0, 5, 100))), (0.22, rel_local(reach, (0, 6, 101))),
            (0.44, rel_local(press, (0, 4, 104))), (0.62, rel_local(knee, (0, 6, 92))), (length, rel_local(st_rel, st_pel))]
    return keyed(keys, length)


# ---------------------------------------------------------------- registry
def tread_frames(length=2.0):
    n = int(round(length * FPS)); return [rel_local(*tread(f / n)) for f in range(n + 1)]


ANIMS = {  # name: (builder, seconds, loops)
    'Swim_Crawl': (crawl_frames, 1.4, True),
    'Swim_Tread': (tread_frames, 2.0, True),
    'Swim_Dive': (dive_frames, 1.6, True),
    'Swim_DiveIn': (dive_in, 1.0, False),
    'Swim_Surface': (surface, 0.8, False),
    'Swim_ClimbOut': (climb_out, 0.8, False),
}


@lru_cache(None)
def _frames(name):
    fn, length, loops = ANIMS[name]
    fr = fn(length)
    assert len(fr) == int(round(length * FPS)) + 1, (name, len(fr))
    for k in range(len(B)):                    # one quaternion hemisphere per track
        for f in range(1, len(fr)):
            if fr[f][k][1] @ fr[f - 1][k][1] < 0: fr[f][k] = (fr[f][k][0], -fr[f][k][1])
    return fr


def frames(name):
    """-> ([{bone: (loc, rot, scale)}] per frame, seconds)"""
    fr = _frames(name)
    return [{N[k]: (f[k][0], f[k][1], REF_S[k]) for k in range(len(B))} for f in fr], ANIMS[name][1]


def world_frames(name):
    fr = _frames(name)
    return [world([b[1] for b in f], [b[0] for b in f])[1] for f in fr], ANIMS[name][1]


# ---------------------------------------------------------------- checks
def demo():
    W, P = pose({}, REF_P[IDX['Pelvis']])
    loc = to_local(W, P)
    for i, b in enumerate(N):
        assert np.allclose(loc[i][0], REF_T[i], atol=1e-6) and abs(abs(loc[i][1] @ norm(B[i]['rot'])) - 1) < 1e-6, b
    for name, (fn, L, loops) in ANIMS.items():
        fr = _frames(name)
        if loops:
            for k in range(len(B)):
                assert np.allclose(fr[0][k][0], fr[-1][k][0], atol=1e-4), (name, N[k])
                assert abs(abs(fr[0][k][1] @ fr[-1][k][1]) - 1) < 1e-6, (name, N[k])
        Pw, _ = world_frames(name)
        head = np.array([p[IDX['head']] for p in Pw]); pel = np.array([p[IDX['Pelvis']] for p in Pw])
        if name in ('Swim_Crawl', 'Swim_Dive'):      # flat: head ahead of the pelvis along +Y, at about its height
            assert (head[:, 1] - pel[:, 1]).min() > 45 and abs(head[:, 2] - pel[:, 2]).max() < 30, name
        if name == 'Swim_Tread':
            assert (head[:, 2] - pel[:, 2]).min() > 55, name
        # max per-frame joint speed: a pop in the data shows up here
        body = [k for k, b in enumerate(N) if not b.endswith('_end') and 'ik_' not in b]   # *_end sit far off in the rig
        sp = max(np.abs(np.array(Pw[f + 1])[body] - np.array(Pw[f])[body]).max() for f in range(len(Pw) - 1)) * FPS
        print('%-14s %4.1f s %s  max joint speed %4.0f cm/s' % (name, L, 'loop    ' if loops else 'one-shot', sp))
        assert sp < (1200 if loops else 1600), name
    # one-shots meet their neighbours
    same = lambda a, b: max(np.abs(np.array(x) - np.array(y)).max() for x, y in zip(a, b)) < 0.5
    assert same(world_frames('Swim_DiveIn')[0][-1], world_frames('Swim_Dive')[0][0])
    assert same(world_frames('Swim_Surface')[0][0], world_frames('Swim_Dive')[0][0])
    assert same(world_frames('Swim_Surface')[0][-1], world_frames('Swim_Tread')[0][0])
    assert same(world_frames('Swim_ClimbOut')[0][0], world_frames('Swim_Tread')[0][0])
    print('demo ok')


def legs_angle(name):
    """mean angle of pelvis->ankles under (-) or over (+) the horizontal"""
    Pw, _ = world_frames(name); a = []
    for p in Pw:
        v = (p[IDX['Foot_L']] + p[IDX['Foot_R']]) / 2 - p[IDX['Pelvis']]
        a.append(np.degrees(np.arctan2(v[2], -v[1])))
    return float(np.mean(a))


def export(path):
    """keys for ue_anims.py (UE's Python has no numpy): {anim: {length, frames, loop, bones: {bone: [[loc, rot, scale]...]}}}"""
    import json
    out = {}
    for name, (fn, L, loops) in ANIMS.items():
        fr, L = frames(name)
        out[name] = {'length': L, 'frames': len(fr) - 1, 'loop': loops,
                     'bones': {b: [[list(map(float, f[b][0])), list(map(float, f[b][1])), list(map(float, f[b][2]))] for f in fr] for b in N}}
    json.dump(out, open(path, 'w'))
    print('wrote', path)


if __name__ == '__main__':
    {'demo': demo, 'export': lambda: export(sys.argv[2])}[sys.argv[1]]()
