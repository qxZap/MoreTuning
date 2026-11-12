"""Previews of the swim cycles: python preview.py <out dir>
Dumps joint positions per frame (from swim_anim, the same data ue_anims.py keys), renders a stick figure of the
character in headless Blender at a few frames per anim from the side and three-quarter, and tiles them into
<out dir>/<anim>.png (top row from the side, bottom row three-quarter front). Asset space is mirrored on X for Blender (UE is left-handed), so left stays left."""
import json, os, subprocess, sys

BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = ('ik_', '_ik_', 'eyes', 'eyebrows')


def dump(out):
    sys.path.insert(0, HERE)
    import swim_anim as sa
    segs = [(i, p) for i, p in enumerate(sa.PARENT) if p > 0 and not sa.N[i].startswith(SKIP) and not sa.N[i].endswith('_end')]
    data = {'segs': segs, 'names': sa.N, 'anims': {}}
    for name in (sys.argv[2:] or sa.ANIMS):
        Pw, L = sa.world_frames(name); n = len(Pw) - 1
        picks = [0, n // 4, n // 2, 3 * n // 4] if sa.ANIMS[name][2] else [round(n * i / 5) for i in range(6)]
        data['anims'][name] = {'frames': picks, 'pos': [[[-p[0] / 100, p[1] / 100, p[2] / 100] for p in Pw[f]] for f in picks]}
    path = os.path.join(out, 'poses.json'); json.dump(data, open(path, 'w')); return path


BLENDER_SCRIPT = r'''
import bpy, json, sys, math
from mathutils import Vector
data = json.load(open(sys.argv[-2])); out = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
try: sc.render.engine = 'BLENDER_WORKBENCH'
except TypeError: pass
sc.render.resolution_x = 480; sc.render.resolution_y = 400
sc.display.shading.light = 'STUDIO'; sc.display.shading.color_type = 'OBJECT'
sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.75, 0.82, 0.9)
def mat(c): return c
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 0)); bpy.context.object.color = (0.5, 0.5, 0.5, 1)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.6
def place(view, ctr):
    d = Vector(view).normalized(); cam.location = ctr + d * 6
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
for name, a in data['anims'].items():
    for fi, (f, pos) in enumerate(zip(a['frames'], a['pos'])):
        objs = []
        for i, p in data['segs']:
            n = data['names'][i]; A, B = Vector(pos[p]), Vector(pos[i]); L = (B - A).length
            if L < 1e-4: continue
            r = 0.045 if n.startswith(('spine', 'neck', 'Pelvis')) else 0.012 if 'inger' in n or 'thumb' in n else 0.03
            bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=L, location=(A + B) / 2, vertices=10)
            o = bpy.context.object; o.rotation_euler = (B - A).to_track_quat('Z', 'Y').to_euler()
            o.color = (0.9, 0.3, 0.2, 1) if n.endswith(('_L', '_l')) else (0.2, 0.7, 0.3, 1) if n.endswith(('_R', '_r')) else (0.95, 0.85, 0.6, 1)
            objs.append(o)
        hi = data['names'].index('head')
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.11, location=Vector(pos[hi]) + (Vector(pos[hi]) - Vector(pos[hi - 1])).normalized() * 0.1)
        bpy.context.object.color = (0.95, 0.85, 0.6, 1); objs.append(bpy.context.object)
        # nose: where the face points (head's forward is asset +Y in the ref pose, carried by the head bone)
        ctr = Vector((0, 0, 1.15))
        for vi, view in enumerate(((1, 0, 0.15), (0.7, 0.75, 0.45))):     # side (from the left), three-quarter front
            place(view, ctr)
            sc.render.filepath = '%s/%s_%d_%d.png' % (out, name, fi, vi)
            bpy.ops.render.render(write_still=True)
        for o in objs: bpy.data.objects.remove(o, do_unlink=True)
'''


def main(out):
    os.makedirs(out, exist_ok=True)
    poses = dump(out)
    script = os.path.join(out, '_render.py'); open(script, 'w').write(BLENDER_SCRIPT)
    subprocess.run([BLENDER, '-b', '--factory-startup', '-P', script, '--', poses, out], check=True, capture_output=True)
    from PIL import Image, ImageDraw
    data = json.load(open(poses))
    for name, a in data['anims'].items():
        tiles = [[Image.open('%s/%s_%d_%d.png' % (out, name, fi, vi)) for fi in range(len(a['frames']))] for vi in range(2)]
        w, h = tiles[0][0].size
        sheet = Image.new('RGB', (w * len(tiles[0]), h * 2), 'white')
        for vi, row in enumerate(tiles):
            for fi, im in enumerate(row):
                sheet.paste(im, (fi * w, vi * h))
                ImageDraw.Draw(sheet).text((fi * w + 8, vi * h + 6), '%s f%d %s' % (name, a['frames'][fi], ('side', '3/4 front')[vi]), fill='black')
        sheet.save(os.path.join(out, name + '.png'))
        for vi, row in enumerate(tiles):
            for fi, _ in enumerate(row): os.remove('%s/%s_%d_%d.png' % (out, name, fi, vi))
        print(os.path.join(out, name + '.png'))


if __name__ == '__main__':
    main(sys.argv[1])
