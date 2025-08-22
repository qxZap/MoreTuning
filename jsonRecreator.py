import json

h1 = 'harley_120HP'
h2 = 'harley'

map = [
    (h1, 'cbr600rr120HP', h2, 'cbr600rr'),
    (h1, 'cbr600rrtuned160HP', h2, 'cbr600rr'),
    (h1, 'r750140HP', h2, 'r750'),
    (h1, 'r750tuned190HP', h2, 'r750'),
    (h1, 'sv65070HP', h2, 'sv650'),
    (h1, 'sv650tuned95HP', h2, 'sv650'),
    (h1, 'panigale1199170HP', h2, 'panigale1199'),
    (h1, 'panigale1199tuned230HP', h2, 'panigale1199'),
    (h1, 'bandit1250145HP', h2, 'bandit1250'),
    (h1, 'bandit1250tuned200HP', h2, 'bandit1250'),
    (h1, 'zzr1400200HP', h2, h2),
    (h1, 'zzr1400tuned270HP', h2, h2)
]

content = None

with open(h1+'.json', 'r') as f:
    content = f.read()

if content:
    for entry in map:
        first_match,first_replace,second_match,second_replace = entry

        with open(first_replace+'.json', 'w+') as f:
            f.write(content.replace(first_match,first_replace).replace(second_match, second_replace))