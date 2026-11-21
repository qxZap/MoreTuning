import unreal
for n in range(6):
    m = unreal.EditorAssetLibrary.load_asset(f"/Game/ECUTuning/Flames/SM_QX_Tongue_{n}")
    b = m.get_bounding_box()
    unreal.log_warning(f"QXB {n} min {b.min.x:.1f} {b.min.y:.1f} {b.min.z:.1f} max {b.max.x:.1f} {b.max.y:.1f} {b.max.z:.1f} mat {m.get_material(0).get_name()}")
