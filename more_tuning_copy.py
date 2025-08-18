import os
import shutil

src_root = r"C:\Users\Milea\Documents\Unreal Projects\sunete\Saved\Cooked\Windows\sunete\Content\Cars\Parts\Engine\Sound"
dst_root = r"D:\MT\MoreTuning\qxZap_MoreTuning_P\MotorTown\Content\Cars\Parts\Engine\Sound"

for dirpath, _, filenames in os.walk(src_root):
    for filename in filenames:
        src_file = os.path.join(dirpath, filename)
        rel_path = os.path.relpath(src_file, src_root)
        dst_file = os.path.join(dst_root, rel_path)

        # Create destination subfolder if it doesn't exist
        dst_folder = os.path.dirname(dst_file)
        os.makedirs(dst_folder, exist_ok=True)

        # Copy (replace if exists, create if not)
        shutil.copy2(src_file, dst_file)
        print(f"✔ Copied: {rel_path}")

print("✅ All files copied and updated.")

# /Game/Cars/Parts/Engine/Sound/rb26/SC_V8Engine
