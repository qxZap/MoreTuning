"""Compares the cook project's stand-in skeleton (standin_pose.json, written by ue_skeleton.py) with the game's."""
import json, numpy as np
o = json.load(open('D:/MT/SwimCook/gltf/standin_pose.json')); B = json.load(open('D:/MT/MoreTuning/Swim/bones.json'))
assert [x[0] for x in o] == [b['name'] for b in B], 'bone order differs'
worst = 0
for x, b in zip(o, B):
    dt = np.abs(np.array(x[1]) - b['loc']).max()
    q1, q2 = np.array(x[2]), np.array(b['rot']); dq = 1 - abs(q1 @ q2) / np.linalg.norm(q1) / np.linalg.norm(q2)
    if dt > 0.01 or dq > 1e-5: print('DIFF', b['name'], dt, dq)
    worst = max(worst, dt)
print('order ok, 78 bones, worst translation diff %.4f cm' % worst)
