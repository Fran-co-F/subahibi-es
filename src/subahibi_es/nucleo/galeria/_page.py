# SPDX-License-Identifier: GPL-3.0-or-later
"""Plantilla de index.html: galería editable (estado por imagen, arrastrar imágenes, guardar TSV e imágenes).

La página es autónoma (sin servidor ni librerías).  No puede escribir archivos por sí sola:
  - «Guardar ui_status.tsv» descarga el TSV de decisiones manuales (el que lee --estado);
  - «Guardar imágenes…» escribe las imágenes soltadas en una carpeta (Chromium, File System Access API)
    o, si el navegador no lo permite, descarga un .zip (sin compresión) listo para `images import`.
"""
import json

TEMPLATE = r"""<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Interfaz: original y español</title>
<style>
:root{--bg:#1b1d24;--fg:#e8e8ee;--mut:#9aa0ad;--card:#252833;--line:#343848;--img:#555a70}
:root.light{--bg:#f3f4f7;--fg:#1a1c22;--mut:#5b6170;--card:#fff;--line:#d9dce5}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
.top{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
button,select,input{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:5px 9px;font:inherit}
button{cursor:pointer} button.on{outline:2px solid #6aa8ff} button.acc{background:#2e6fbd;border-color:#2e6fbd;color:#fff}
main{padding:16px;max-width:2300px;margin:auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;margin:0 0 14px;padding:10px 12px}
.card.hi{outline:2px solid #6aa8ff}
.card header{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.sz,.mut{color:var(--mut)} .note{flex:1;min-width:220px}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:12px;margin-top:8px}
figure{margin:0;background:var(--img);border-radius:6px;padding:8px;overflow:auto;position:relative}
figure img,figure canvas{max-width:100%;display:block}
figcaption{color:#d8dbe6;font-size:12px;margin-top:4px}
.nochange{color:#cfd3e0;padding:30px 0;text-align:center;font-style:italic}
.tag{font-size:12px;padding:1px 8px;border-radius:10px;color:#fff}
.warn{color:#ff8a80;font-size:12px}
.x{position:absolute;top:6px;right:6px;padding:0 7px}
#drop{position:fixed;inset:0;background:rgba(20,40,80,.82);color:#fff;display:none;align-items:center;justify-content:center;font-size:22px;z-index:20;text-align:center}
#log{position:fixed;right:12px;bottom:12px;max-width:420px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;display:none;z-index:15;white-space:pre-wrap}
</style>
<div class="top"><b>Interfaz: original y español</b><span id="filters"></span><span style="flex:1"></span>
<button id="loadtsv">Cargar TSV…</button><button id="savetsv" class="acc">Guardar ui_status.tsv</button>
<button id="saveimgs" class="acc">Guardar imágenes…</button><button id="bg">Fondo: gris</button><button id="th">Claro/oscuro</button>
<input id="file" type="file" multiple hidden></div>
<div id="drop">Soltá las imágenes traducidas (PNG o BMP) o un archivo .tsv<br><small>Se asignan por nombre; si las soltás sobre una tarjeta, van a esa tarjeta.</small></div>
<div id="log"></div>
<main><p class="mut" id="intro"></p><div id="list"></div></main>
<script>
const DATA = /*__DATA__*/;
// ---------- funciones puras (se prueban con Node) ----------
function globToRegex(g){let r='';for(let i=0;i<g.length;i++){const c=g[i];
  if(c==='*')r+='.*';else if(c==='?')r+='.';
  else if(c==='['){const j=g.indexOf(']',i+1);if(j>i){r+='['+g.slice(i+1,j).replace(/^!/,'^')+']';i=j}else r+='\\[';}
  else r+=c.replace(/[.+^${}()|\\\]]/g,'\\$&');}
  return new RegExp('^'+r+'$');}
function parseTsv(text,estados){const rules=[];
  for(const line of text.split(/\r?\n/)){if(!line.trim()||line.startsWith('#'))continue;
    const p=line.split('\t');if(p.length>=2&&estados.includes(p[1]))rules.push({re:globToRegex(p[0]),st:p[1],note:p[2]||''});}
  return rules;}
function buildTsv(items){ // items: [{n,st,note}]
  const head=['# Decisiones manuales sobre cada imagen de interfaz (generado por index.html).',
   '# patrón<TAB>estado<TAB>nota.  Estados: pendiente, decidir, revisar, sin_japones.  Gana la primera regla que coincida.'];
  return head.concat(items.map(i=>i.n+'\t'+i.st+'\t'+(i.note||'').replace(/[\t\r\n]+/g,' '))).join('\n')+'\n';}
function crc32(u8){let c,crc=-1;if(!crc32.t){crc32.t=[];for(let n=0;n<256;n++){c=n;for(let k=0;k<8;k++)c=c&1?0xEDB88320^(c>>>1):c>>>1;crc32.t[n]=c>>>0}}
  for(let i=0;i<u8.length;i++)crc=crc32.t[(crc^u8[i])&255]^(crc>>>8);return (crc^-1)>>>0;}
function makeZip(files){ // files: [{name, data:Uint8Array}] -> Uint8Array (almacenado, sin compresión)
  const enc=new TextEncoder(),parts=[],central=[];let off=0;
  for(const f of files){const name=enc.encode(f.name),crc=crc32(f.data),sz=f.data.length;
    const lh=new DataView(new ArrayBuffer(30));lh.setUint32(0,0x04034b50,true);lh.setUint16(4,20,true);lh.setUint16(6,0x0800,true);
    lh.setUint32(14,crc,true);lh.setUint32(18,sz,true);lh.setUint32(22,sz,true);lh.setUint16(26,name.length,true);
    parts.push(new Uint8Array(lh.buffer),name,f.data);
    const ch=new DataView(new ArrayBuffer(46));ch.setUint32(0,0x02014b50,true);ch.setUint16(4,20,true);ch.setUint16(6,20,true);ch.setUint16(8,0x0800,true);
    ch.setUint32(16,crc,true);ch.setUint32(20,sz,true);ch.setUint32(24,sz,true);ch.setUint16(28,name.length,true);ch.setUint32(42,off,true);
    central.push(new Uint8Array(ch.buffer),name);off+=30+name.length+sz;}
  let csz=0;for(const c of central)csz+=c.length;
  const end=new DataView(new ArrayBuffer(22));end.setUint32(0,0x06054b50,true);end.setUint16(8,files.length,true);end.setUint16(10,files.length,true);
  end.setUint32(12,csz,true);end.setUint32(16,off,true);
  const all=parts.concat(central,[new Uint8Array(end.buffer)]);let n=0;for(const p of all)n+=p.length;
  const out=new Uint8Array(n);let o=0;for(const p of all){out.set(p,o);o+=p.length}return out;}
function decodeBmp(u8){ // BMP de 32 bits sin compresión (con alfa) -> {w,h,rgba:Uint8ClampedArray} o null
  const v=new DataView(u8.buffer,u8.byteOffset,u8.byteLength);if(u8.length<54||v.getUint16(0,false)!==0x424D)return null;
  const off=v.getUint32(10,true),hdr=v.getUint32(14,true),w=v.getInt32(18,true);let h=v.getInt32(22,true);
  const bpp=v.getUint16(28,true),comp=v.getUint32(30,true);
  if(hdr<40||bpp!==32||(comp!==0&&comp!==3))return null;const top=h<0;h=Math.abs(h);
  const rgba=new Uint8ClampedArray(w*h*4);
  for(let y=0;y<h;y++){const sy=top?y:h-1-y;for(let x=0;x<w;x++){const s=off+(sy*w+x)*4,d=(y*w+x)*4;
    rgba[d]=u8[s+2];rgba[d+1]=u8[s+1];rgba[d+2]=u8[s];rgba[d+3]=u8[s+3];}}
  return {w,h,rgba};}
function stemOf(name){return name.replace(/\.[^.]*$/,'');}
if(typeof module!=='undefined')module.exports={globToRegex,parseTsv,buildTsv,makeZip,crc32,decodeBmp,stemOf};
// ---------- interfaz ----------
if(typeof document!=='undefined')(function(){
const ESTADOS=Object.keys(DATA.etq),EDIT=ESTADOS.filter(k=>k!=='traducida');
const KEY='subahibi-es-index:'+location.pathname;
const S={},dropped={};let cur='*';
const $=s=>document.querySelector(s);
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
try{const saved=JSON.parse(localStorage.getItem(KEY)||'{}');for(const r of DATA.rows){S[r.n]={st:r.st,note:r.note||''};if(saved[r.n]&&!r.tr)Object.assign(S[r.n],saved[r.n])}}
catch(e){for(const r of DATA.rows)S[r.n]={st:r.st,note:r.note||''}}
function persist(){try{const o={};for(const r of DATA.rows)if(!r.tr&&(S[r.n].st!==r.st||S[r.n].note!==(r.note||'')))o[r.n]=S[r.n];localStorage.setItem(KEY,JSON.stringify(o))}catch(e){}}
function eff(n){return dropped[n]?'traducida':S[n].st}
function log(msg,ms){const l=$('#log');l.textContent=msg;l.style.display='block';clearTimeout(log.t);log.t=setTimeout(()=>l.style.display='none',ms||6000)}
const bgs=[['gris','#555a70'],['negro','#000'],['blanco','#fff'],['damero','repeating-conic-gradient(#888 0 25%,#bbb 0 50%) 0 0/16px 16px']];let bi=0;
function build(){
  const L=$('#list');L.innerHTML='';
  for(const r of DATA.rows){
    const c=document.createElement('section');c.className='card';c.id='c_'+r.n;c.dataset.n=r.n;
    c.innerHTML=`<header><b>${r.n}</b><span class="sz">${r.w}×${r.h}</span><select class="st"></select><span class="tag"></span>
      <input class="note" placeholder="nota"><span class="warn"></span></header>
      <div class="pair"><figure><img loading="lazy" src="img/jp/${r.n}.webp"><figcaption>Original</figcaption></figure>
      <figure class="es"></figure></div>`;
    const sel=c.querySelector('.st');
    sel.innerHTML=ESTADOS.map(k=>`<option value="${k}"${k==='traducida'?' disabled':''}>${DATA.etq[k]}</option>`).join('');
    sel.onchange=()=>{S[r.n].st=sel.value;persist();refresh(r.n)};
    const note=c.querySelector('.note');note.value=S[r.n].note;note.oninput=()=>{S[r.n].note=note.value;persist()};
    c.addEventListener('dragover',e=>{e.preventDefault();c.classList.add('hi')});
    c.addEventListener('dragleave',()=>c.classList.remove('hi'));
    c.addEventListener('drop',e=>{e.preventDefault();e.stopPropagation();c.classList.remove('hi');$('#drop').style.display='none';
      const fs=[...e.dataTransfer.files].filter(f=>/\.(png|bmp|webp|jpe?g)$/i.test(f.name));
      if(fs.length)assign(r.n,fs[0]);else handleFiles([...e.dataTransfer.files])});
    L.appendChild(c);refresh(r.n,true);
  }
  filters();
}
function refresh(n,noFilter){
  const r=DATA.rows.find(x=>x.n===n),c=$('#c_'+n),st=eff(n);
  c.querySelector('.st').value=st==='traducida'?'traducida':S[n].st;
  c.querySelector('.st').disabled=!!(r.tr||dropped[n]);
  const tag=c.querySelector('.tag');tag.textContent=DATA.etq[st]+(dropped[n]?' (sin guardar)':'');tag.style.background=DATA.col[st];
  const es=c.querySelector('.es');es.innerHTML='';
  if(dropped[n]){es.appendChild(dropped[n].view);
    const x=document.createElement('button');x.className='x';x.textContent='✕';x.title='quitar';x.onclick=()=>{delete dropped[n];refresh(n)};es.appendChild(x);
    es.insertAdjacentHTML('beforeend',`<figcaption>Español: ${esc(dropped[n].file.name)} (${dropped[n].w}×${dropped[n].h})</figcaption>`);
    c.querySelector('.warn').textContent=(dropped[n].w!==r.w||dropped[n].h!==r.h)?`⚠ tamaño ${dropped[n].w}×${dropped[n].h} ≠ original ${r.w}×${r.h}`:'';
  }else{c.querySelector('.warn').textContent='';
    es.innerHTML=r.tr?`<img loading="lazy" src="img/es/${r.n}.webp"><figcaption>Español</figcaption>`
      :'<div class="nochange">sin cambios — arrastrá acá la imagen traducida</div><figcaption>Español</figcaption>';}
  if(!noFilter)filters();
}
function filters(){
  const cnt={};for(const r of DATA.rows)cnt[eff(r.n)]=(cnt[eff(r.n)]||0)+1;
  const F=$('#filters');F.innerHTML='';
  const mk=(k,t)=>{const b=document.createElement('button');b.textContent=t;b.className=cur===k?'on':'';b.onclick=()=>{cur=k;filters()};F.appendChild(b)};
  mk('*','Todas ('+DATA.rows.length+')');for(const k of ESTADOS)if(cnt[k])mk(k,DATA.etq[k]+' ('+cnt[k]+')');
  document.querySelectorAll('.card').forEach(c=>c.style.display=(cur==='*'||eff(c.dataset.n)===cur)?'':'none');
  const nd=Object.keys(dropped).length;$('#intro').textContent=DATA.rows.length+' imágenes.'+(nd?' '+nd+' imagen(es) soltada(s) sin guardar: usá «Guardar imágenes…».':'');
}
async function viewOf(file){ // -> {w,h,view}
  const u8=new Uint8Array(await file.arrayBuffer());const bmp=decodeBmp(u8);
  const cv=document.createElement('canvas');
  if(bmp){cv.width=bmp.w;cv.height=bmp.h;cv.getContext('2d').putImageData(new ImageData(bmp.rgba,bmp.w,bmp.h),0,0);return {w:bmp.w,h:bmp.h,view:cv,data:u8}}
  const bm=await createImageBitmap(file);cv.width=bm.width;cv.height=bm.height;cv.getContext('2d').drawImage(bm,0,0);
  return {w:bm.width,h:bm.height,view:cv,data:u8};
}
async function assign(n,file){
  try{const v=await viewOf(file);dropped[n]={file,w:v.w,h:v.h,view:v.view,data:v.data};refresh(n)}
  catch(e){log('No se pudo leer '+file.name+': '+e.message)}
}
async function handleFiles(files){
  const miss=[],ok=[];
  for(const f of files){
    if(/\.tsv$/i.test(f.name)){applyTsv(await f.text());continue}
    const n=stemOf(f.name),r=DATA.rows.find(x=>x.n.toLowerCase()===n.toLowerCase());
    if(!r){miss.push(f.name);continue}
    await assign(r.n,f);ok.push(r.n)}
  if(ok.length)log(ok.length+' imagen(es) asignada(s)'+(miss.length?'\nSin tarjeta con ese nombre: '+miss.join(', '):''));
  else if(miss.length)log('Sin tarjeta con ese nombre: '+miss.join(', '));
}
function applyTsv(text){
  const rules=parseTsv(text,EDIT);let n=0;
  for(const r of DATA.rows){if(r.tr)continue;const m=rules.find(x=>x.re.test(r.n));if(m){S[r.n].st=m.st;S[r.n].note=m.note;n++}}
  persist();build();log('TSV cargado: '+n+' imágenes con decisión manual');
}
function download(name,blob){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();setTimeout(()=>{URL.revokeObjectURL(a.href);a.remove()},1000)}
$('#savetsv').onclick=()=>{
  const items=DATA.rows.filter(r=>!r.tr&&!dropped[r.n]&&S[r.n].st!=='sin_clasificar'&&S[r.n].st!=='traducida').map(r=>({n:r.n,st:S[r.n].st,note:S[r.n].note}));
  download('ui_status.tsv',new Blob([buildTsv(items)],{type:'text/tab-separated-values'}));log(items.length+' decisiones guardadas en ui_status.tsv');};
$('#saveimgs').onclick=async()=>{
  const ns=Object.keys(dropped);if(!ns.length){log('No hay imágenes soltadas todavía.');return}
  const bad=ns.filter(n=>{const r=DATA.rows.find(x=>x.n===n);return dropped[n].w!==r.w||dropped[n].h!==r.h});
  if(bad.length&&!confirm('Hay imágenes con tamaño distinto del original ('+bad.join(', ')+'). El importador las rechazará. ¿Guardar igual?'))return;
  const files=ns.map(n=>({name:n+(dropped[n].file.name.match(/\.[^.]*$/)||['.png'])[0].toLowerCase(),data:dropped[n].data}));
  if(window.showDirectoryPicker){try{const d=await showDirectoryPicker({mode:'readwrite'});
      for(const f of files){const h=await d.getFileHandle(f.name,{create:true});const w=await h.createWritable();await w.write(f.data);await w.close()}
      log(files.length+' imagen(es) escritas en la carpeta elegida');return}catch(e){if(e.name==='AbortError')return}}
  download('imagenes_traducidas.zip',new Blob([makeZip(files)],{type:'application/zip'}));log(files.length+' imagen(es) en imagenes_traducidas.zip');};
$('#loadtsv').onclick=()=>{const f=$('#file');f.accept='.tsv,.txt';f.onchange=async()=>{for(const x of f.files)applyTsv(await x.text());f.value=''};f.click()};
$('#bg').onclick=e=>{bi=(bi+1)%bgs.length;document.documentElement.style.setProperty('--img',bgs[bi][1]);e.target.textContent='Fondo: '+bgs[bi][0]};
$('#th').onclick=()=>document.documentElement.classList.toggle('light');
let dc=0;
addEventListener('dragenter',e=>{if([...(e.dataTransfer?.types||[])].includes('Files')){dc++;$('#drop').style.display='flex'}});
addEventListener('dragleave',()=>{dc=Math.max(0,dc-1);if(!dc)$('#drop').style.display='none'});
addEventListener('dragover',e=>e.preventDefault());
addEventListener('drop',e=>{e.preventDefault();dc=0;$('#drop').style.display='none';handleFiles([...e.dataTransfer.files])});
build();
})();
</script></html>"""


def render(rows, etiquetas, colores):
    """rows: lista de dicts {n,g,w,h,st,note,tr}.  Devuelve el HTML completo."""
    data = {"rows": [{"n": r["n"], "g": r["g"], "w": r["w"], "h": r["h"], "st": r["st"],
                      "note": r["note"], "tr": r["tr"]} for r in rows],
            "etq": etiquetas, "col": colores}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("/*__DATA__*/", blob, 1)
