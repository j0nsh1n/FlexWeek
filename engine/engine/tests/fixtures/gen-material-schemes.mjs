// Writes material-schemes.json with @material/material-color-utilities 0.3.0: node gen-material-schemes.mjs OUT.json
import {Hct,SchemeTonalSpot,SchemeExpressive,SchemeVibrant,SchemeFidelity,SchemeNeutral,SchemeMonochrome,MaterialDynamicColors as D,argbFromHex,hexFromArgb} from '@material/material-color-utilities';
import fs from 'node:fs';
const styles={'Tonal Spot':SchemeTonalSpot,'Vibrant':SchemeVibrant,'Expressive':SchemeExpressive,'Fidelity':SchemeFidelity,'Neutral':SchemeNeutral,'Monochrome':SchemeMonochrome};
const seeds=['#0B62C4','#00797F','#3B7A4B','#8A6A00','#B4235A','#6D4BC3','#E91E63','#2E7D32','#000000','#FFFFFF'];
const contrasts=[['-1',-1],['-0.5',-0.5],['0',0],['0.75',0.75],['1',1]];
const roles=['primary','onPrimary','primaryContainer','onPrimaryContainer','secondary','onSecondary','secondaryContainer','onSecondaryContainer','tertiary','onTertiary','tertiaryContainer','onTertiaryContainer','error','onError','errorContainer','onErrorContainer','surface','onSurface','onSurfaceVariant','surfaceContainerLowest','surfaceContainerLow','surfaceContainer','surfaceContainerHigh','surfaceContainerHighest','surfaceVariant','outline','outlineVariant','inverseSurface','inverseOnSurface','inversePrimary'];
const out={};
for(const seed of seeds)for(const [sn,S] of Object.entries(styles))for(const dark of [false,true])for(const [cn,c] of contrasts){
 const s=new S(Hct.fromInt(argbFromHex(seed)),dark,c);const o={};for(const r of roles)o[r]=hexFromArgb(D[r].getArgb(s));
 out[`${seed}|${sn}|${dark?'dark':'light'}|${cn}`]=o;}
fs.writeFileSync(process.argv[2],JSON.stringify(out));console.log(Object.keys(out).length);
