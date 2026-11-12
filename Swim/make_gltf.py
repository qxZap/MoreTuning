"""Writes a glTF stand-in of the game's SK_MTCharacter (bones.json: names, parents, ref pose read off the
cooked skeleton) for the cook project to import. `upto` limits the bone count: the game's bone order is not
depth-first (Jaw and the *_end bones came later), so the skeleton is built by importing 63, 64, then 78 bones.
conv() maps a UE local transform to glTF; see the probe in ue_build.py."""
import json, base64, struct, sys, os
import numpy as np
B = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bones.json')))

def conv(t, q):
    # UE (cm, left-handed Z-up) -> glTF (m, right-handed Y-up), the inverse of Interchange's (x,y,z)->(x? ) mapping;
    # set by the identity probe (MODE env), see ue_build.py
    mode = os.environ.get('GLTF_MODE', 'ue')
    if mode == 'identity':
        return [c / 100 for c in t], list(q)
    # Interchange imports glTF (x, y, z) as UE (x, z, y) * 100 (probe 2026-11-12), a mirror, so the quaternion's
    # vector part swaps the same way and w flips sign; the mapping is its own inverse
    return [t[0] / 100, t[2] / 100, t[1] / 100], [q[0], q[2], q[1], -q[3]]

def write(path, upto, mode=None):
    if mode: os.environ['GLTF_MODE'] = mode
    bones = B[:upto]
    nodes = []
    for i, b in enumerate(bones):
        t, q = conv(b['loc'], b['rot'])
        n = {'name': b['name'], 'translation': t, 'rotation': q}
        kids = [j for j, c in enumerate(bones) if c['parent'] == i]
        if kids: n['children'] = kids
        nodes.append(n)
    # world matrices (glTF space) for inverse bind matrices
    def mat(t, q):
        x, y, z, w = q
        R = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                      [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                      [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        M = np.eye(4); M[:3, :3] = R; M[:3, 3] = t; return M
    W = []
    for i, n in enumerate(nodes):
        L = mat(n['translation'], n['rotation']); p = bones[i]['parent']
        W.append(L if p < 0 else W[p] @ L)
    ibm = b''.join(struct.pack('<16f', *np.linalg.inv(M).T.flatten()) for M in W)
    # one small triangle per bone, fully weighted to it, at the bone's world position
    pos = b''; jnt = b''; wgt = b''; idx = b''
    for i, M in enumerate(W):
        o = M[:3, 3]
        for d in ([0.01, 0, 0], [0, 0.01, 0], [0, 0, 0.01]):
            pos += struct.pack('<3f', *(o + d)); jnt += struct.pack('<4H', i, 0, 0, 0); wgt += struct.pack('<4f', 1, 0, 0, 0)
        idx += struct.pack('<3I', 3*i, 3*i+1, 3*i+2)
    nv = 3 * len(W)
    allpos = np.frombuffer(pos, dtype='<f4').reshape(-1, 3)
    blob = pos + jnt + wgt + idx + ibm
    offs = np.cumsum([0, len(pos), len(jnt), len(wgt), len(idx)])
    mesh_node = len(nodes)
    nodes.append({'name': 'SwimStandIn', 'mesh': 0, 'skin': 0})
    g = {
        'asset': {'version': '2.0'},
        'scene': 0, 'scenes': [{'nodes': [0, mesh_node]}],
        'nodes': nodes,
        'meshes': [{'name': 'SwimStandIn', 'primitives': [{'attributes': {'POSITION': 0, 'JOINTS_0': 1, 'WEIGHTS_0': 2}, 'indices': 3}]}],
        'skins': [{'joints': list(range(len(bones))), 'inverseBindMatrices': 4, 'skeleton': 0}],
        'buffers': [{'byteLength': len(blob), 'uri': 'data:application/octet-stream;base64,' + base64.b64encode(blob).decode()}],
        'bufferViews': [
            {'buffer': 0, 'byteOffset': int(offs[0]), 'byteLength': len(pos)},
            {'buffer': 0, 'byteOffset': int(offs[1]), 'byteLength': len(jnt)},
            {'buffer': 0, 'byteOffset': int(offs[2]), 'byteLength': len(wgt)},
            {'buffer': 0, 'byteOffset': int(offs[3]), 'byteLength': len(idx)},
            {'buffer': 0, 'byteOffset': int(offs[4]), 'byteLength': len(ibm)}],
        'accessors': [
            {'bufferView': 0, 'componentType': 5126, 'count': nv, 'type': 'VEC3', 'min': allpos.min(0).tolist(), 'max': allpos.max(0).tolist()},
            {'bufferView': 1, 'componentType': 5123, 'count': nv, 'type': 'VEC4'},
            {'bufferView': 2, 'componentType': 5126, 'count': nv, 'type': 'VEC4'},
            {'bufferView': 3, 'componentType': 5125, 'count': 3 * len(W), 'type': 'SCALAR'},
            {'bufferView': 4, 'componentType': 5126, 'count': len(W), 'type': 'MAT4'}],
    }
    json.dump(g, open(path, 'w'))

if __name__ == '__main__':
    write(sys.argv[1], int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None)
