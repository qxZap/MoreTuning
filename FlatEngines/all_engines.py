# Rebuild every engine-sim set: scripts (es_engines), rpm steps (es_steps), starter (es_starter). Engines run one after
# another (es_steps renders each engine's steps side by side); a failure is reported and the rest carry on.
#   python -I all_engines.py [name ...]
import os, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "recompose")]
import es_engines, es_steps, es_starter

names = sys.argv[1:] or list(es_engines.SPECS)
failed = []
for n in names:
    try:
        entry = es_engines.write(n)
        es_steps.main(n, entry)
        es_starter.main(n, entry, "truck" if es_engines.SPECS[n]["kind"] == "truck" else "car")
        print(f"=== {n} done", flush=True)
    except Exception:
        failed.append(n)
        print(f"=== {n} FAILED\n{traceback.format_exc()}", flush=True)
print("failed:", failed or "none")
