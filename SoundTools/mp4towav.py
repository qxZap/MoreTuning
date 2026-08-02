"""Pull the audio out of video clips as WAV, ready for import as engine sounds.

    python mp4towav.py                  # everything in in/ -> out/
    python mp4towav.py "clip.mp4" ...   # these files (or folders) -> out/
    python mp4towav.py demo             # self-check

Defaults to 16-bit PCM mono at the source sample rate, because Unreal only
spatialises mono sound waves -- import a stereo one as an engine sound and it
plays flat, at full volume, everywhere. Pass --stereo if you actually want two
channels, and --rate 48000 to resample.

Needs ffmpeg on PATH. `in/` and `out/` are gitignored; only this script is
tracked.
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(HERE, "in")
OUT_DIR = os.path.join(HERE, "out")

VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".m4a", ".avi", ".mp3", ".aac", ".ogg")


def ffmpeg_args(src, dst, mono=True, rate=None):
    args = ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
            "-vn",                    # drop the video stream
            "-acodec", "pcm_s16le"]   # what Unreal imports
    if mono:
        args += ["-ac", "1"]
    if rate:
        args += ["-ar", str(rate)]
    return args + [dst]


def sources(paths):
    """Expand files and folders into a flat list of convertible inputs."""
    found = []
    for path in paths:
        if os.path.isdir(path):
            for entry in sorted(glob.glob(os.path.join(path, "*"))):
                if entry.lower().endswith(VIDEO_EXTS):
                    found.append(entry)
        elif os.path.isfile(path):
            found.append(path)
        else:
            sys.exit(f"not found: {path}")
    return found


def convert(src, mono=True, rate=None):
    name = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(OUT_DIR, name + ".wav")
    os.makedirs(OUT_DIR, exist_ok=True)
    result = subprocess.run(ffmpeg_args(src, dst, mono, rate), capture_output=True, text=True)
    if result.returncode or not os.path.exists(dst):
        sys.exit(f"ffmpeg failed on {src}\n{result.stderr.strip()}")
    return dst


def main(argv):
    mono, rate = True, None
    if "--stereo" in argv:
        argv.remove("--stereo")
        mono = False
    if "--rate" in argv:
        i = argv.index("--rate")
        rate = argv[i + 1]
        del argv[i:i + 2]

    paths = argv or [IN_DIR]
    if paths == [IN_DIR] and not os.path.isdir(IN_DIR):
        os.makedirs(IN_DIR, exist_ok=True)
        sys.exit(f"nothing to do -- put clips in {IN_DIR}")

    files = sources(paths)
    if not files:
        sys.exit(f"no audio or video files in {', '.join(paths)}")

    for src in files:
        dst = convert(src, mono, rate)
        print(f"  {os.path.basename(src)}  ->  {os.path.basename(dst)}"
              f"  ({os.path.getsize(dst) / 1e6:.1f} MB)")
    print(f"\n{len(files)} converted into {OUT_DIR}")


def demo():
    # A real end-to-end run: make a tone, convert it, read back what came out.
    import shutil
    import tempfile
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        sys.exit("ffmpeg/ffprobe not on PATH")

    assert ffmpeg_args("a.mp4", "a.wav")[-4:] == ["pcm_s16le", "-ac", "1", "a.wav"]
    assert "-ac" not in ffmpeg_args("a.mp4", "a.wav", mono=False)
    assert ffmpeg_args("a.mp4", "a.wav", rate=48000)[-3:] == ["-ar", "48000", "a.wav"]

    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "tone.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=0.2:sample_rate=44100",
                    "-ac", "2", "-c:a", "aac", src], check=True)

    global OUT_DIR
    OUT_DIR = os.path.join(tmp, "out")
    dst = convert(src)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=codec_name,channels,sample_rate",
                            "-of", "default=noprint_wrappers=1:nokey=1", dst],
                           capture_output=True, text=True).stdout.split()
    assert probe[0] == "pcm_s16le", probe
    assert probe[1] == "44100", probe            # source rate kept
    assert probe[2] == "1", probe                # downmixed to mono
    shutil.rmtree(tmp, ignore_errors=True)
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "demo":
        demo()
    else:
        main(sys.argv[1:])
