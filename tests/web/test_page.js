// SPDX-License-Identifier: GPL-3.0-or-later
// Prueba de la interfaz de index.html con jsdom (opcional): npm install jsdom
// uso: node test_page.js INDEX.html BMP_32BITS CARPETA_SALIDA
const {JSDOM}=require('jsdom'); const fs=require('fs'); const assert=require('assert');
const page=process.argv[2], bmpPath=process.argv[3], outdir=process.argv[4];
const html=fs.readFileSync(page,'utf8');
const dom=new JSDOM(html,{runScripts:'dangerously',url:'file:///tmp/x/index.html',pretendToBeVisual:true,
 beforeParse(w){
  w.createImageBitmap=async(f)=>({width:10,height:10});
  w.HTMLCanvasElement.prototype.getContext=function(){return {drawImage(){},putImageData(){}}};
  w.ImageData=class{constructor(d,wd,h){this.data=d;this.width=wd;this.height=h}};
  w.__blobs=[]; w.URL.createObjectURL=(b)=>{w.__blobs.push(b);return 'blob:x'+w.__blobs.length};
  w.URL.revokeObjectURL=()=>{}; w.HTMLAnchorElement.prototype.click=function(){w.__dl=this.download};
  w.confirm=()=>true;
 }});
const w=dom.window,d=w.document; const $=s=>d.querySelector(s);
const tick=()=>new Promise(r=>setTimeout(r,30));
const dropFiles=(target,files)=>{const e=new w.Event('drop',{bubbles:true,cancelable:true});e.dataTransfer={files,types:['Files']};target.dispatchEvent(e)};
(async()=>{
 await tick();
 const cards=d.querySelectorAll('.card'); console.log('tarjetas:',cards.length); assert(cards.length===338);
 const btn=[...d.querySelectorAll('#filters button')].map(b=>b.textContent); console.log('filtros:',btn.join(' | '));
 const cnt=s=>[...d.querySelectorAll('#filters button')].find(b=>b.textContent.startsWith(s))?.textContent;
 console.log('inicial:',cnt('Pendiente'),'|',cnt('A decidir'),'|',cnt('Sin clasificar'));
 assert(/\(29\)/.test(cnt('Pendiente'))&&/\(26\)/.test(cnt('A decidir'))&&/\(254\)/.test(cnt('Sin clasificar')));
 // 1) cambiar estado y nota desde la tarjeta
 const c=$('#c_SGMsgWnd000003'); assert(c.querySelector('.st').value==='sin_clasificar');
 c.querySelector('.st').value='decidir'; c.querySelector('.st').dispatchEvent(new w.Event('change'));
 c.querySelector('.note').value='probablemente dejar'; c.querySelector('.note').dispatchEvent(new w.Event('input'));
 assert(/\(27\)/.test(cnt('A decidir'))&&/\(253\)/.test(cnt('Sin clasificar')),'tras cambio manual');
 // 2) cargar un TSV soltándolo en la página (patrones con * ? [])
 const tsv='# c\nSGMsgWnd00000[0-2]\tpendiente\tprueba\n';
 dropFiles(w,[new w.File([tsv],'ui_status.tsv')]); await tick(); await tick();
 console.log('tras TSV:',cnt('Pendiente'),'|',cnt('A decidir'),'|',cnt('Sin clasificar'));
 assert(/\(32\)/.test(cnt('Pendiente'))&&/\(250\)/.test(cnt('Sin clasificar')),'tras TSV');
 // el TSV cargado reemplaza lo anterior: SGMsgWnd000003 no estaba en el patrón, así que sigue 'decidir'
 assert($('#c_SGMsgWnd000003').querySelector('.st').value==='decidir');
 // 3) soltar una imagen por nombre (PNG falso) y un BMP real sobre su tarjeta
 const bmp=fs.readFileSync(bmpPath); const f1=new w.File([bmp],'SGMenu000000.bmp');
 // la tarjeta SGMenu000000 está traducida en el original: probar con una no traducida
 const f2=new w.File([new Uint8Array([137,80,78,71])],'SGCnfgWnd000000.png');
 dropFiles(w,[f2,new w.File([1],'NoExiste.png')]); await tick(); await tick();
 const c2=$('#c_SGCnfgWnd000000'); console.log('estado tras soltar:',c2.querySelector('.tag').textContent,'| aviso:',c2.querySelector('.warn').textContent);
 assert(/sin guardar/.test(c2.querySelector('.tag').textContent)); assert(/≠ original/.test(c2.querySelector('.warn').textContent)); // 10x10 vs 456x30
 console.log('log:',$('#log').textContent.replace(/\n/g,' / '));
 // 4) BMP de 32 bits real sobre una tarjeta (cualquiera): comprobar alfa decodificado
 const m=w.eval('decodeBmp'); const dec=m(new Uint8Array(bmp)); console.log('BMP decodificado:',dec.w+'x'+dec.h,'alfa mín/máx:',Math.min(...dec.rgba.filter((v,i)=>i%4==3)),Math.max(...dec.rgba.filter((v,i)=>i%4==3)));
 const c3=$('#c_SGKeyCnfg000500'); dropFiles(c3,[new w.File([bmp],'lo_que_sea.bmp')]); await tick(); await tick();
 console.log('drop directo en tarjeta:',c3.querySelector('.tag').textContent,'|',c3.querySelector('.warn').textContent||'tamaño ok');
 // 5) guardar TSV
 $('#savetsv').click(); const tsvBlob=w.__blobs.pop(); const txt=await tsvBlob.text?.() ?? '';
 fs.writeFileSync(outdir+'/ui_status.tsv',txt); console.log('descarga:',w.__dl,'| líneas:',txt.split('\n').filter(l=>l&&!l.startsWith('#')).length);
 assert(txt.includes('SGMsgWnd000003\tdecidir\tprobablemente dejar')); assert(txt.includes('SGMsgWnd000001\tpendiente\tprueba')); assert(!txt.includes('SGMenu000000'));
 assert(!txt.includes('SGCnfgWnd000000'),'la soltada no va al TSV'); 
 // 6) guardar imágenes -> zip (sin showDirectoryPicker en jsdom)
 $('#saveimgs').click(); await tick(); await tick();
 const zipBlob=w.__blobs.pop(); const buf=Buffer.from(await zipBlob.arrayBuffer()); fs.writeFileSync(outdir+'/imgs.zip',buf); console.log('descarga:',w.__dl,'| bytes:',buf.length);
 // persistencia
 console.log('localStorage:',Object.keys(JSON.parse(w.localStorage.getItem([...Object.keys(w.localStorage)][0]))).length,'entradas');
 console.log('TODO OK');
})().catch(e=>{console.error('FALLO',e);process.exit(1)});
