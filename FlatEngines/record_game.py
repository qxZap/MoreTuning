# Records what the PC plays (WASAPI loopback of the default output) to a wav, for hearing the game's own mix of an
# engine sound set: python record_game.py <out.wav> <seconds>
import sys, wave, pyaudiowpatch as pa
p = pa.PyAudio()
dev = p.get_default_wasapi_loopback()
sr, ch = int(dev["defaultSampleRate"]), dev["maxInputChannels"]
s = p.open(format=pa.paInt16, channels=ch, rate=sr, input=True, input_device_index=dev["index"], frames_per_buffer=1024)
w = wave.open(sys.argv[1], "wb"); w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr)
for _ in range(int(sr * float(sys.argv[2]) / 1024)):
    w.writeframes(s.read(1024, exception_on_overflow=False))
w.close(); s.close(); p.terminate()
print(f"{dev['name']}: {sr} Hz x{ch} -> {sys.argv[1]}")
