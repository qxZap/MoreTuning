"""Quaternion FK on the game's SK_MTCharacter (bones.json: names, parents, local ref pose in UE units,
read off the cooked skeleton by parse_skel.py). Quaternions are (x, y, z, w) as UE stores them."""
import json, os
import numpy as np

B = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bones.json')))
N = [b['name'] for b in B]
IDX = {n: i for i, n in enumerate(N)}
PARENT = [b['parent'] for b in B]


def qmul(a, b):
    x1, y1, z1, w1 = a; x2, y2, z2, w2 = b
    return np.array([w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2,
                     w1*z2 + x1*y2 - y1*x2 + z1*w2, w1*w2 - x1*x2 - y1*y2 - z1*z2])


def qconj(q): return np.array([-q[0], -q[1], -q[2], q[3]])


def qrot(q, v): return qmul(qmul(q, [v[0], v[1], v[2], 0.0]), qconj(q))[:3]


def qaxis(axis, deg):
    a = np.asarray(axis, float); n = np.linalg.norm(a)
    if n < 1e-9 or abs(deg) < 1e-9: return np.array([0, 0, 0, 1.0])
    a = a / n; s = np.sin(np.radians(deg) / 2)
    return np.array([*(a * s), np.cos(np.radians(deg) / 2)])


def qarc(u, v):
    """shortest rotation taking direction u to direction v"""
    u = np.asarray(u, float) / np.linalg.norm(u); v = np.asarray(v, float) / np.linalg.norm(v)
    c = np.cross(u, v); return qaxis(c, np.degrees(np.arctan2(np.linalg.norm(c), u @ v)))


def norm(q): q = np.asarray(q, float); return q / np.linalg.norm(q)


REF_R = [norm(b["rot"]) for b in B]
REF_T = [np.array(b['loc'], float) for b in B]
REF_S = [np.array(b['scale'], float) for b in B]


def world(local_rot, local_loc):
    W = [None] * len(B); P = [None] * len(B)
    for i, p in enumerate(PARENT):
        if p < 0: W[i] = norm(local_rot[i]); P[i] = np.array(local_loc[i], float)
        else: W[i] = norm(qmul(W[p], local_rot[i])); P[i] = P[p] + qrot(W[p], local_loc[i])
    return W, P


REF_W, REF_P = world(REF_R, REF_T)
