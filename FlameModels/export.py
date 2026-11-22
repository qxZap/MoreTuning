# The 3D flame tongues for ECU Tuning, as meshes the game can draw.
# blender -b -P export.py -- <out.fbx>
# Each SM_QX_Tongue_<n> is laid out as the engine's /Engine/BasicShapes/Cone, which it stands in for in the Classic
# flame: pivot at its middle, base at z -50 cm (the pipe), tip at +50 cm, about 90 cm across at its widest. UV v runs 0 at the pipe to 1 at the tip: the material's colour
# ramp and fade follow it. Six variants: the plugin swaps between them so the shape flickers.
import bpy, bmesh, math, random, sys

OUT = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)

VARIANTS = [  # curl, twist, taper, wobble
    (0.10, 1.5, 0.8, 0.18), (0.16, 2.2, 0.75, 0.22), (0.22, 3.0, 0.7, 0.26),
    (0.08, 1.0, 1.0, 0.10), (0.30, 3.5, 0.65, 0.30), (0.14, 2.6, 0.85, 0.2),
]


def tongue(name, seed, curl, twist, taper, wob, rings=28, segs=14, radius=0.45, part=None):
    rnd = random.Random(seed)
    ph = [rnd.random() * 6.28 for _ in range(6)]
    me = bpy.data.meshes.new(name); bm = bmesh.new(); uvl = bm.loops.layers.uv.new()
    grid = []
    for i in range(rings + 1):
        t = i / rings
        r = radius * (math.sin(math.pi * min(1, t * 1.6 + 0.08)) ** 0.6 if t < 0.3 else 1) * (1 - t) ** taper
        r = max(r, 0.0005)
        cz = t - 0.5
        cx = curl * t * t * math.sin(ph[0] + t * 5.0)
        cy = curl * t * t * math.cos(ph[1] + t * 4.0) * 0.7
        row = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            ripple = 1 + wob * math.sin(3 * a + twist * t * 6.28 + ph[2]) + 0.5 * wob * math.sin(5 * a - twist * t * 9 + ph[3])
            ripple *= 1 + 0.25 * wob * math.sin(t * 22 + ph[4] + a)
            row.append(bm.verts.new((cx + r * ripple * math.cos(a), cy + r * ripple * math.sin(a), cz)))
        grid.append(row)
    lo, hi = part or (0, rings)  # a section: rings lo..hi of the same tongue, in place, so the three fit back together
    for i in range(lo, hi):
        for j in range(segs):
            f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][(j + 1) % segs], grid[i][(j + 1) % segs]))
            for lp, (u, v) in zip(f.loops, ((j / segs, i / rings), (j / segs, (i + 1) / rings), ((j + 1) / segs, (i + 1) / rings), ((j + 1) / segs, i / rings))):
                lp[uvl].uv = (u, 1 - v)  # UE flips V on import: 1 - v here is v = 0 at the pipe there
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")  # rings outside the section
    bm.normal_update(); bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    return ob


# Sections (11-22, the user: a flame starts one colour and ends another, by its heat): each tongue again in three
# pieces along its length -- the pipe end, the body and the tip -- SM_QX_Tongue_<n>_<k>, each coloured on its own.
SECTIONS = [(0, 8), (8, 18), (18, 28)]  # ring ranges: t 0-0.29, 0.29-0.64, 0.64-1

for n, (curl, twist, taper, wob) in enumerate(VARIANTS):
    tongue(f"SM_QX_Tongue_{n}", 100 + n, curl, twist, taper, wob)
    for k, part in enumerate(SECTIONS):
        tongue(f"SM_QX_Tongue_{n}_{k}", 100 + n, curl, twist, taper, wob, part=part)

bpy.ops.export_scene.fbx(filepath=OUT, use_selection=False, object_types={"MESH"}, apply_unit_scale=True,
                         axis_forward="-Y", axis_up="Z", mesh_smooth_type="FACE", add_leaf_bones=False)
print("exported", len(VARIANTS), "tongues and", len(VARIANTS) * len(SECTIONS), "sections to", OUT)
