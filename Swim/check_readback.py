"""Compares the pose UE evaluates from the keyed anims (readback.json, ue_anims.py) with swim_anim's FK at a quarter
cycle: proves the keys landed on the right bones in the right space."""
import json, numpy as np, swim_anim as sa
rb = json.load(open('D:/MT/SwimCook/readback.json'))
for name, bones in rb.items():
    Pw, L = sa.world_frames(name); f = (len(Pw) - 1) // 4
    err = max(np.abs(np.array(v) - Pw[f][sa.IDX[b]]).max() for b, v in bones.items())
    print(name, 'max diff %.3f cm' % err); assert err < 0.5, name
print('readback ok')
