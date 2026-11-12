"""CMU swimming mocap -> SK_MTCharacter poses, by world-space rotation deltas.

An ASF bone's world rotation at zero dofs is the identity, so a CMU bone's world rotation *is* its rotation away from
the CMU T-pose. SK_MTCharacter's reference pose is a T-pose too, so a mapped bone gets
    W'(bone) = A G R_cmu A^T * Q(bone) * W_ref(bone)
A: CMU axes (Y-up, facing +Z, left +X) -> the mesh asset's (Z-up, facing +Y, left +X).
G: per take, turns the performer (who lay prone on a support "swimming in the air") so the torso runs along
   forward and the chest faces down -- the same lie as the procedural crawl.
Q: the small rest-pose difference per bone (CMU's thighs splay 20 deg in rest, the Synty ones hang straight).
Unmapped bones (fingers, IK, ends) ride along with their parent. The pelvis position is not taken from the mocap:
the caller places it (the plugin owns the actor's height).

Cycles: cut() finds the stretch of a take one period long whose ends match best, resamples it to 30 fps at the
wanted length, and spreads the remaining end-to-start difference over the clip so frame 0 == the last frame.
"""
import numpy as np
import cmu
from fk import B, N, IDX, PARENT, REF_W, REF_P, REF_T, qmul, qconj, qrot, qarc, norm

A = np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]], float)   # CMU (x, y, z) -> asset (x, z, y)

MAP = {'Pelvis': 'root', 'spine_01': 'lowerback', 'spine_02': 'upperback', 'spine_03': 'thorax',
       'neck_01': 'lowerneck', 'head': 'head',
       'clavicle_l': 'lclavicle', 'UpperArm_L': 'lhumerus', 'lowerarm_l': 'lradius', 'Hand_L': 'lhand',
       'clavicle_r': 'rclavicle', 'UpperArm_R': 'rhumerus', 'lowerarm_r': 'rradius', 'Hand_R': 'rhand',
       'Thigh_L': 'lfemur', 'calf_l': 'ltibia', 'Foot_L': 'lfoot', 'ball_l': 'ltoes',
       'Thigh_R': 'rfemur', 'calf_r': 'rtibia', 'Foot_R': 'rfoot', 'ball_r': 'rtoes'}
# a bone's direction: towards this child (the next joint along the limb)
CHILD = {'Pelvis': 'spine_01', 'spine_01': 'spine_02', 'spine_02': 'spine_03', 'spine_03': 'neck_01', 'neck_01': 'head',
         'clavicle_l': 'UpperArm_L', 'UpperArm_L': 'lowerarm_l', 'lowerarm_l': 'Hand_L', 'Hand_L': 'finger_01_l',
         'clavicle_r': 'UpperArm_R', 'UpperArm_R': 'lowerarm_r', 'lowerarm_r': 'Hand_R', 'Hand_R': 'finger_01_r',
         'Thigh_L': 'calf_l', 'calf_l': 'Foot_L', 'Foot_L': 'ball_l', 'Thigh_R': 'calf_r', 'calf_r': 'Foot_R', 'Foot_R': 'ball_r'}


def mat2q(M):
    t = np.trace(M)
    if t > 0:
        s = np.sqrt(t + 1) * 2; return norm([(M[2, 1] - M[1, 2]) / s, (M[0, 2] - M[2, 0]) / s, (M[1, 0] - M[0, 1]) / s, s / 4])
    i = int(np.argmax(np.diag(M)))
    if i == 0:
        s = np.sqrt(1 + M[0, 0] - M[1, 1] - M[2, 2]) * 2
        return norm([s / 4, (M[0, 1] + M[1, 0]) / s, (M[0, 2] + M[2, 0]) / s, (M[2, 1] - M[1, 2]) / s])
    if i == 1:
        s = np.sqrt(1 + M[1, 1] - M[0, 0] - M[2, 2]) * 2
        return norm([(M[0, 1] + M[1, 0]) / s, s / 4, (M[1, 2] + M[2, 1]) / s, (M[0, 2] - M[2, 0]) / s])
    s = np.sqrt(1 + M[2, 2] - M[0, 0] - M[1, 1]) * 2
    return norm([(M[0, 2] + M[2, 0]) / s, (M[1, 2] + M[2, 1]) / s, s / 4, (M[1, 0] - M[0, 1]) / s])


def slerp(a, b, t):
    a = norm(a); b = norm(b)
    if a @ b < 0: b = -b
    d = np.clip(a @ b, -1, 1)
    if d > 0.9995: return norm(a + t * (b - a))
    th = np.arccos(d); return (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)


class Take:
    def __init__(self, name, tilt=0.0):
        self.sk, frs = cmu.load(name)
        self.rots = [{b: f[b][0] for b in set(MAP.values())} for f in (cmu.fk(self.sk, fr) for fr in frs)]
        F = [cmu.fk(self.sk, fr) for fr in frs[::10]]
        up = np.mean([f['thorax'][2] - f['root'][2] for f in F], 0); up /= np.linalg.norm(up)
        chest = np.mean([f['root'][0] @ [0, 0, 1] for f in F], 0)          # the pelvis's facing
        chest -= up * (chest @ up); chest /= np.linalg.norm(chest)
        # performer frame (up, chest, side) -> CMU target frame: body axis along +z (asset forward), chest to -y (down)
        src = np.stack([up, chest, np.cross(up, chest)], 1)
        tz, ty = np.array([0, 0, 1.0]), np.array([0, -1.0, 0])
        dst = np.stack([tz, ty, np.cross(tz, ty)], 1)
        self.G = dst @ src.T
        if tilt: self.G = cmu.rot('x', -tilt) @ self.G                      # + lifts the head end
        # Q: CMU rest direction (asset space) vs Synty rest direction, per mapped bone
        self.Q = {}
        for b, c in MAP.items():
            mine = REF_P[IDX[CHILD[b]]] - REF_P[IDX[b]] if b in CHILD else None
            theirs = A @ self.sk.bones[c]['dir'] if c != 'root' else None
            self.Q[b] = qarc(mine, theirs) if mine is not None and theirs is not None and np.linalg.norm(theirs) > 0 else np.array([0, 0, 0, 1.0])
        self.Q['Pelvis'] = np.array([0, 0, 0, 1.0])

    def world(self, i, pel):
        R = self.rots[i]; W = [None] * len(B); P = [None] * len(B); D = [None] * len(B)
        for k, par in enumerate(PARENT):
            b = N[k]
            if b in MAP:
                D[k] = qmul(mat2q(A @ self.G @ R[MAP[b]] @ A.T), self.Q[b])
            else:
                D[k] = D[par] if par >= 0 else np.array([0, 0, 0, 1.0])
            if par < 0: D[k] = np.array([0, 0, 0, 1.0])
            W[k] = norm(qmul(D[k], REF_W[k]))
            if par < 0: P[k] = REF_P[k]
            elif b == 'Pelvis': P[k] = np.asarray(pel, float)
            else: P[k] = P[par] + qrot(W[par], REF_T[k])
        return W, P


def local(W, P):
    out = []
    for k, par in enumerate(PARENT):
        if par < 0: out.append((REF_T[k], norm(B[k]['rot']))); continue
        inv = qconj(W[par])
        out.append((qrot(inv, P[k] - P[par]) if N[k] == 'Pelvis' else REF_T[k], norm(qmul(inv, W[k]))))
    return out


ARMS = [IDX[b] for b in ('UpperArm_L', 'lowerarm_l', 'UpperArm_R', 'lowerarm_r', 'spine_03', 'Thigh_L', 'Thigh_R', 'calf_l', 'calf_r')]


def cut(take, period, length, pel, start=None, fps=30):
    """loop of `length` seconds from a stretch about `period` seconds long; returns [local pose per frame]"""
    n = len(take.rots); P = int(period * 120)
    loc = lambda i: local(*take.world(i, pel))
    cache = {}
    def L(i):
        if i not in cache: cache[i] = loc(i)
        return cache[i]
    def dist(i, j):
        a, b = L(i), L(j); return sum(1 - abs(a[k][1] @ b[k][1]) for k in ARMS)
    starts = [start] if start is not None else range(int(0.15 * n), int(0.85 * n) - P, 12)
    best = min(((dist(s, e), s, e) for s in starts for e in range(s + int(0.85 * P), min(n - 1, s + int(1.15 * P)), 3)))
    _, s, e = best
    nf = int(round(length * fps))
    frames = []
    for f in range(nf + 1):
        x = s + (e - s) * f / nf; i = int(x); u = x - i
        a, b = L(i), L(min(i + 1, n - 1))
        frames.append([(a[k][0] * (1 - u) + b[k][0] * u, slerp(a[k][1], b[k][1], u)) for k in range(len(B))])
    # close the loop: spread the end->start difference over the clip
    for k in range(len(B)):
        c = qmul(frames[0][k][1], qconj(frames[-1][k][1]))
        dl = frames[0][k][0] - frames[-1][k][0]
        for f in range(nf + 1):
            t = f / nf
            frames[f][k] = (frames[f][k][0] + dl * t, norm(qmul(slerp([0, 0, 0, 1.0], c, t), frames[f][k][1])))
    return frames, (s, e, best[0])
