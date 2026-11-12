"""bones.json from the game skeleton: UAssetGUI tojson SK_MTCharacter.uasset skel.json (VER_UE5_4 MotorTown20261112),
then run here. Reads the cooked FReferenceSkeleton (name, parent; then FTransform as 10 doubles) after the properties."""
import json,base64,struct,sys
d=json.load(open('skel.json'));nm=d['NameMap']
for e in d['Exports']:
    if e['ObjectName']=='SK_MTCharacter': break
b=base64.b64decode(e['Extras']); print(len(b), b[:16].hex())
def find():
    for off in range(0,64):
        n=struct.unpack_from('<i',b,off)[0]
        if 50<n<200:
            ok=True
            for i in range(n):
                idx,num,par=struct.unpack_from('<iii',b,off+4+12*i)
                if not(0<=idx<len(nm)) or par<-1 or par>=i: ok=False;break
            if ok: return off,n
o,n=find(); print('off',o,'bones',n)
bones=[]
for i in range(n):
    idx,num,par=struct.unpack_from('<iii',b,o+4+12*i); bones.append((nm[idx]+(f'_{num-1}' if num else ''),par))
p=o+4+12*n; m=struct.unpack_from('<i',b,p)[0]; p+=4; assert m==n,m
poses=[]
for i in range(n):
    v=struct.unpack_from('<10d',b,p); p+=80; poses.append(v)
out=[dict(name=bn,parent=pa,rot=list(v[0:4]),loc=list(v[4:7]),scale=list(v[7:10])) for (bn,pa),v in zip(bones,poses)]
json.dump(out,open('bones.json','w'),indent=1)
for i,x in enumerate(out): print(i,x['name'],x['parent'],[round(c,3) for c in x['loc']],[round(c,3) for c in x['rot']],[round(c,2) for c in x['scale']])
print('rest',len(b)-p)
