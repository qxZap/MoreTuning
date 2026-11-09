"""FMOD banks out of SCS HashFS v2 archives without parsing the file table: every 16-byte-aligned zlib header whose
stream starts with RIFF....FEV is decompressed whole and saved; raw (stored) FSB5 banks are cut by their header.
  python -I scs_banks.py <out dir> <archive.scs>...   -> <out>/<archive>/<n>.bank|.fsb"""
import sys, os, mmap, zlib, struct, numpy as np
out = sys.argv[1]
for a in sys.argv[2:]:
    name = os.path.basename(a)[:-4]
    d = os.path.join(out, name); os.makedirs(d, exist_ok=True)
    f = open(a, "rb"); m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    arr = np.frombuffer(m, np.uint8)
    n, CH = 0, 1 << 28
    for base in range(0, len(arr), CH):
        seg = arr[base:base + CH + 2]
        a0 = seg[0:-2:16]; a1 = seg[1:-1:16]
        hits = np.nonzero((a0 == 0x78) & np.isin(a1, (0x01, 0x5E, 0x9C, 0xDA)))[0] * 16 + base
        for i in hits:
            try:
                head = zlib.decompressobj().decompress(m[i:i + 512], 64)
            except zlib.error:
                continue
            if head[:4] != b"RIFF" or b"FEV" not in head[:16]:
                continue
            do, buf, j = zlib.decompressobj(), [], i
            while not do.eof and j < len(m):
                buf.append(do.decompress(m[j:j + (1 << 22)])); j += 1 << 22
            open(os.path.join(d, f"{n}.bank"), "wb").write(b"".join(buf)); n += 1
    i = m.find(b"FSB5")
    while i != -1:
        ver, ns, sh, nt, ds = struct.unpack("<5I", m[i + 4:i + 24])
        size = (60 if ver == 1 else 64) + sh + nt + ds
        if 0 < size <= len(m) - i:
            open(os.path.join(d, f"{n}.fsb"), "wb").write(m[i:i + size]); n += 1
        i = m.find(b"FSB5", i + 4)
    print(name, n, "banks", flush=True)
