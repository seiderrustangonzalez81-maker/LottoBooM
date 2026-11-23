const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const textValidator=require('../../static/js/apostar_text_validator.js');
const {validate}=textValidator;

const template=fs.readFileSync('jugadas/templates/jugadas/apostar.html','utf8');
const start=template.indexOf('function _procNormalizarTexto(texto){');
const end=template.indexOf('function _procValidarTexto(texto){',start);
assert.ok(start>=0&&end>start,'parser helpers must be present in apostar.html');
const sandbox={window:{ApostarTextValidator:textValidator}};
vm.runInNewContext(template.slice(start,end)+';this.helpers={normalize:_procNormalizarTexto,parseAmounts:_procParsearMontos,detectInstruction:_procDetectarInstruccionPos,parseText:_procParsearTexto,expandNumbers:_procExpandirNumeros};',sandbox);
const h=sandbox.helpers;
function run(text){return validate(text,h);}

const tripleta=require('../../static/js/apostar_tripleta.js');
function candadoErrors(forms,montoPar,montoCand,nPlays){
  const template=fs.readFileSync('jugadas/templates/jugadas/apostar.html','utf8');
  const a=template.indexOf('function _validarCandadoApuesta(){');
  const b=template.indexOf('function enviarApuesta(dryRun){',a);
  const sandbox={ordenSorteos:[1],sorteosActivos:{'1':{nombre:'Test',tablasActivas:{'tabla-tradicional':{forms:forms,rows:[{num:'12 34',montos:{parlet:montoPar,candado:montoCand},numPlays:nPlays}]}}}},TABLE_DEFS:{'tabla-tradicional':{kind:'multi',numDigits:2}},contarParletsDeFila:(row)=>row.numPlays};
  vm.runInNewContext(template.slice(a,b)+';this.check=_validarCandadoApuesta;',sandbox);
  return sandbox.check();
}

function extractFunction(name){
  const start=template.indexOf('function '+name+'(');
  const end=template.indexOf('\nfunction ',start+10);
  assert.ok(start>=0&&end>start,'function '+name+' must be present');
  return template.slice(start,end);
}
function tableHarness(){
  const source=['numerosEnFila','expandirToken','expandirGrupoVS','calcRowTotal','recolectarItemsDeSorteo'].map(extractFunction).join('\n');
  const sandbox={TABLE_DEFS:{},sorteosActivos:{},window:{ApostarTripleta:tripleta,ApostarTextValidator:textValidator}};
  vm.runInNewContext(source+';this.calc=calcRowTotal;this.collect=recolectarItemsDeSorteo;',sandbox);
  return sandbox;
}
function compareRowTotal(def,forms,row){
  const h=tableHarness(),sid=1,tk='table';
  h.TABLE_DEFS[tk]=def;
  h.sorteosActivos[sid]={tablasActivas:{[tk]:{forms:forms,rows:[row]}}};
  const calc=h.calc(row,forms,def.numDigits,def.kind,def.maxNums);
  const items=h.collect(sid);
  const actual=items.reduce((sum,it)=>sum+Number(it.monto),0);
  assert.equal(actual,calc,def.label+': item sum should equal displayed row total');
}
function destinationRowHarness(){
  const start=template.indexOf('function newRow(forms, kind){');
  const end=template.indexOf('function numerosEnFila(row, numDigits, maxNums){',start);
  assert.ok(start>=0&&end>start,'newRow and destination mapper must exist');
  const sandbox={};
  vm.runInNewContext(template.slice(start,end)+';this.create=_procCrearFilaDestino;',sandbox);
  return sandbox;
}
function processHarness(text,drawIds,draws,confirmAnswer){
  const textarea={value:text||'',scrollTop:0,selectionStart:0,selectionEnd:0,style:{}};
  const errorBox={style:{},innerHTML:''};
  const chk={checked:true};
  const doc={getElementById:id=>({procesarText:textarea,procErrores:errorBox,chkProcesar:chk}[id]||null),querySelector:()=>null};
  const helperStart=template.indexOf('function _procNormalizarTexto(texto){');
  const helperEnd=template.indexOf('function _procValidarTexto(texto){',helperStart);
  const wrapperEnd=template.indexOf('function _procProcesarTexto(){',helperEnd);
  const processEnd=template.indexOf('function _procValidarDestinos(filas){',wrapperEnd);
  const destEnd=template.indexOf('function _procRenderErrores',processEnd);
  const rowStart=template.indexOf('function newRow(forms, kind){');
  const rowEnd=template.indexOf('function numerosEnFila(row, numDigits, maxNums){',rowStart);
  assert.ok(helperStart>=0&&helperEnd>helperStart&&wrapperEnd>helperEnd&&processEnd>wrapperEnd&&destEnd>processEnd&&rowStart>=0&&rowEnd>rowStart);
  const source=template.slice(helperStart,helperEnd)+template.slice(helperEnd,wrapperEnd)+template.slice(rowStart,rowEnd)+template.slice(wrapperEnd,processEnd)+template.slice(processEnd,destEnd)+';function _procActualizarUI(){};this.process=_procProcesarTexto;';
  const defs={'tabla-tradicional':{kind:'multi',numDigits:2,forms:['pick2','pf','fijo','corridos','parlet','candado'],aliases:{}}};
  let confirms=0,status='';
  const sandbox={document:doc,window:{ApostarTextValidator:textValidator,ApostarTableValidator:{validateRows:()=>[]},confirm:()=>{confirms++;return !!confirmAnswer;}},TABLE_DEFS:defs,ordenSorteos:drawIds,sorteosActivos:draws,resolverForma:(f,d)=>d&&d.aliases&&d.aliases[f]||f,expandirToken:(t)=>[String(t)],numerosEnFila:(row)=>({numeros:String(row.num||'').trim().split(/\s+/).filter(Boolean),paresExplicitos:[]}),contarParletsDeFila:()=>1,_procRenderErrores(){},_procActualizarEstado:(msg)=>{status=msg;},renderTabsSorteo(){},renderMiniResumenSorteo(){},recalcGlobal(){},toast(){},setTimeout:()=>1,clearTimeout(){},console:{error(){},warn(){},log(){}}};
  vm.runInNewContext(source,sandbox);
  return {process:sandbox.process,draws,textarea,chk,sandbox,confirmCount:()=>confirms,status:()=>status};
}
test('parsed data maps into multi, positions and VS table row structures',()=>{
  const h=destinationRowHarness();
  const multi=h.create({num:'12 34',montos:{fijo:'2'}},{forms:['fijo']},'multi');
  assert.equal(multi.num,'12 34');
  assert.equal(multi.montos.fijo,'2');
  const positions=h.create({posicion:'3',num:'12 34',monto:'5'},{forms:['posicion']},'posiciones');
  assert.equal(positions.posicion,'3');
  assert.equal(positions.num,'12 34');
  assert.equal(positions.monto,'5');
  const vs=h.create({numA:'12 34',numB:'56 78',monto:'4'},{forms:['vs']},'vs_groups');
  assert.equal(vs.numA,'12 34');
  assert.equal(vs.numB,'56 78');
  assert.equal(vs.monto,'4');
});

test('table row totals match collected item sums across forms',()=>{
  compareRowTotal({label:'Trad',kind:'multi',numDigits:2,forms:['fijo','parlet','candado']},['fijo','parlet','candado'],{num:'12 34 56',montos:{fijo:'2',parlet:'3',candado:'18'}});
  compareRowTotal({label:'Parlet explicit',kind:'multi',numDigits:2,forms:['parlet']},['parlet'],{num:'12 34 12x34',montos:{parlet:'2'}});
  compareRowTotal({label:'VS',kind:'vs_groups',numDigits:2,forms:['vs']},['vs'],{numA:'12 34',numB:'56 78',monto:'3'});
  compareRowTotal({label:'VS100',kind:'single',numDigits:2,forms:['vs100']},['vs100'],{num:'12 34',montos:{vs100:'1.5'}});
  compareRowTotal({label:'Pos',kind:'posiciones',numDigits:2,forms:['posicion']},['posicion'],{num:'12 34 56',monto:'2',posicion:'2'});
  compareRowTotal({label:'Tripleta',kind:'single',numDigits:2,maxNums:3,forms:['tripleta']},['tripleta'],{num:'12 34 56',montos:{tripleta:'5'}});
  compareRowTotal({label:'Pick4',kind:'single',numDigits:4,forms:['pick4']},['pick4'],{num:'1234 5678',montos:{pick4:'2'}});
  compareRowTotal({label:'Centenas',kind:'multi',numDigits:3,forms:['centenas corridas']},['centenas corridas'],{num:'123 456',montos:{'centenas corridas':'4'}});
});

function uiHarness(text,drawIds,checked,overrides){
  const textarea={value:text||'',scrollTop:0};
  const button={disabled:false,style:{},attributes:{},setAttribute(name,value){this.attributes[name]=String(value);},getAttribute(name){return this.attributes[name]??null;}};
  const checkbox={checked:!!checked};
  const errorBox={style:{},innerHTML:''};
  const doc={getElementById:(id)=>({procesarText:textarea,btnProcAhora:button,chkProcesar:checkbox,procErrores:errorBox}[id]||null)};
  const helperStart=template.indexOf('function _procNormalizarTexto(texto){');
  const helperEnd=template.indexOf('function _procValidarTexto(texto){',helperStart);
  const destStart=template.indexOf('function _procValidarDestinos(filas){');
  const uiStart=template.indexOf('function _procRenderErrores');
  const uiEnd=template.indexOf('  (function _bindProcesarText',uiStart);
  const rowStart=template.indexOf('function newRow(forms, kind){');
  const rowEnd=template.indexOf('function numerosEnFila(row, numDigits, maxNums){',rowStart);
  assert.ok(uiStart>=0&&uiEnd>uiStart,'live UI helpers must be present');
  assert.ok(rowStart>=0&&rowEnd>rowStart,'destination row mapper must be present');
  const wrapperStart=template.indexOf('function _procValidarTexto(texto){');
  const wrapperEnd=template.indexOf('function _procProcesarTexto(){',wrapperStart);
  assert.ok(wrapperStart>=0&&wrapperEnd>wrapperStart,'validation wrapper must be present');
  const source=template.slice(helperStart,helperEnd)+template.slice(wrapperStart,wrapperEnd)+template.slice(rowStart,rowEnd)+template.slice(destStart,uiStart)+template.slice(uiStart,uiEnd)+';this.update=_procActualizarUI;';
  const ids=drawIds||[];
  const sorteos={};
  ids.forEach(id=>{
    sorteos[String(id)]=(overrides&&overrides[id])||{nombre:'Test '+id,cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo','corridos','parlet','candado'],rows:[]},'tabla-pick3':{forms:['pick3'],rows:[]}}};
  });
  const helpers=tableRowHarness();
  const defs={'tabla-tradicional':{kind:'multi',numDigits:2,forms:['pick2','pf','fijo','corridos','parlet','candado'],aliases:{corrido1:'corridos',corrido2:'corridos'}},'tabla-pick3':{kind:'single',numDigits:3,forms:['pick3']}};
  const sandbox={document:doc,window:{ApostarTextValidator:textValidator,ApostarTableValidator:tableValidator},TABLE_DEFS:defs,ordenSorteos:ids,sorteosActivos:sorteos,resolverForma:(f,d)=>d&&d.aliases&&d.aliases[f]||f,expandirToken:helpers.expandToken,numerosEnFila:helpers.numerosEnFila,contarParletsDeFila:helpers.contarParletsDeFila,_procActualizarEstado:function(){},};
  vm.runInNewContext(source,sandbox);
  const updateResult=sandbox.update();
  return {button,checkbox,errorBox,textarea,updateResult};
}

const tableValidator=require('../../static/js/apostar_table_validation.js');
function tableRowHarness(){
  function expandToken(t,d){return [String(t)];}
  function numbersInRow(row,d,max){
    const nums=[],pairs=[],counts={};
    String(row.num||'').trim().split(/\s+/).filter(Boolean).forEach(t=>{
      const m=t.match(/^(\d{2})[xX](\d{2})$/);if(m){pairs.push(m[1]+'x'+m[2]);return;}
      expandToken(t,d).forEach(n=>{counts[n]=(counts[n]||0);if(counts[n]<2){nums.push(n);counts[n]++;}});
    });
    return {numeros:max?nums.slice(0,max):nums,paresExplicitos:pairs};
  }
  function countPairs(row){const n=numbersInRow(row,2).numeros.length;return n*(n-1)/2+numbersInRow(row,2).paresExplicitos.length;}
  return {expandToken,numerosEnFila:numbersInRow,contarParletsDeFila:countPairs};
}
function validateRows(rows,def,forms){return tableValidator.validateRows(rows,def,forms,tableRowHarness());}
test('validates table row amounts and prevents missing data from being silently skipped',()=>{
  assert.equal(validateRows([{num:'12 34',montos:{fijo:'2'}}],{kind:'multi',numDigits:2,forms:['fijo']},['fijo']).length,0);
  assert.ok(validateRows([{num:'',montos:{fijo:'2'}}],{kind:'multi',numDigits:2,forms:['fijo']},['fijo']).length>0);
  assert.ok(validateRows([{num:'12 34',montos:{fijo:''}}],{kind:'multi',numDigits:2,forms:['fijo']},['fijo']).length>0);
  assert.ok(validateRows([{num:'123',montos:{fijo:'2'}}],{kind:'multi',numDigits:2,forms:['fijo']},['fijo']).length>0);
  assert.ok(validateRows([{num:'12 12 12',montos:{fijo:'2'}}],{kind:'multi',numDigits:2,forms:['fijo']},['fijo']).length>0);
});
test('validates parlet combinations and explicit pairs',()=>{
  assert.equal(validateRows([{num:'12 34 12x34',montos:{parlet:'2'}}],{kind:'multi',numDigits:2,forms:['parlet']},['parlet']).length,0);
  assert.ok(validateRows([{num:'12',montos:{parlet:'2'}}],{kind:'multi',numDigits:2,forms:['parlet']},['parlet']).length>0);
  assert.ok(validateRows([{num:'12x34',montos:{fijo:'2'}}],{kind:'multi',numDigits:2,forms:['fijo']},['fijo']).length>0);
});
test('validates tripleta row count, VS groups, positions and Pick4 digits',()=>{
  assert.equal(validateRows([{num:'12 34 56',montos:{tripleta:'5'}}],{kind:'single',numDigits:2,maxNums:3,forms:['tripleta']},['tripleta']).length,0);
  assert.ok(validateRows([{num:'12 34 56 78',montos:{tripleta:'5'}}],{kind:'single',numDigits:2,maxNums:3,forms:['tripleta']},['tripleta']).length>0);
  assert.equal(validateRows([{numA:'12 34',numB:'56',monto:'3'}],{kind:'vs_groups',numDigits:2,forms:['vs']},['vs']).length,0);
  assert.ok(validateRows([{numA:'12 34',numB:'',monto:'3'}],{kind:'vs_groups',numDigits:2,forms:['vs']},['vs']).length>0);
  assert.equal(validateRows([{num:'12 34',monto:'2',posicion:'2'}],{kind:'posiciones',numDigits:2,forms:['posicion']},['posicion']).length,0);
  assert.ok(validateRows([{num:'12 34',monto:'2',posicion:'4'}],{kind:'posiciones',numDigits:2,forms:['posicion']},['posicion']).length>0);
  assert.equal(validateRows([{num:'1234',montos:{pick4:'1'}}],{kind:'single',numDigits:4,forms:['pick4']},['pick4']).length,0);
  assert.ok(validateRows([{num:'123',montos:{pick4:'1'}}],{kind:'single',numDigits:4,forms:['pick4']},['pick4']).length>0);
});
test('live processor uses aria-disabled while remaining tappable for feedback',()=>{
  const valid=uiHarness('12 34 con 5',[1],true);assert.equal(valid.updateResult.ok,true,JSON.stringify(valid.updateResult));assert.equal(valid.button.disabled,false);assert.equal(valid.button.getAttribute('aria-disabled'),'false');
  for(const h of [uiHarness('12 34 con 5 bad',[1],true),uiHarness('12 34 con 5',[],true),uiHarness('12 34 con 5',[1],false)]){assert.equal(h.button.disabled,false);assert.equal(h.button.getAttribute('aria-disabled'),'true');}
});
test('replicate and process checkboxes stay mutually exclusive',()=>{
  const chkRep={checked:false,disabled:false,dataset:{},handlers:{},addEventListener(type,fn){this.handlers[type]=fn;}};
  const chkProc={checked:false,disabled:false,dataset:{},handlers:{},addEventListener(type,fn){this.handlers[type]=fn;}};
  const wrap={style:{display:'none'}};
  const doc={readyState:'complete',getElementById:id=>({chkReplicar:chkRep,chkProcesar:chkProc,procesarTextWrap:wrap}[id]||null),addEventListener(){}};
  let replicateMode=true;
  const start=template.indexOf('(function initProcesar(){');
  const end=template.indexOf('})();',start)+4;
  assert.ok(start>=0&&end>start);
  vm.runInNewContext(template.slice(start,end),{document:doc,setTimeout(fn){fn();},activarModoReplicar(on){replicateMode=on;}});
  chkProc.checked=true;chkProc.handlers.change.call(chkProc);
  assert.equal(chkRep.checked,false);assert.equal(chkRep.disabled,true);assert.equal(wrap.style.display,'block');assert.equal(replicateMode,false);
  chkProc.checked=false;chkProc.handlers.change.call(chkProc);
  assert.equal(chkRep.disabled,false);assert.equal(wrap.style.display,'none');
  chkRep.checked=true;chkRep.handlers.change.call(chkRep);
  assert.equal(chkProc.checked,false);assert.equal(chkProc.disabled,true);assert.equal(wrap.style.display,'none');
});
test('live processor stays amber and aria-disabled until process mode is active',()=>{
  const h=uiHarness('12 34 con 5',[1],false);
  assert.equal(h.button.disabled,false);assert.equal(h.button.getAttribute('aria-disabled'),'true');
  assert.match(h.button.style.background,/f59e0b/);
  assert.match(h.button.innerHTML,/Activa Procesar/);
});
test('live processor marks error when any selected draw lacks its target tab',()=>{
  const h=uiHarness('pick3 123 con 5',[1,2],true,{'2':{nombre:'Second',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:[]}}}});
  assert.equal(h.button.disabled,false);assert.equal(h.button.getAttribute('aria-disabled'),'true');
  assert.match(h.errorBox.innerHTML,/Second.*no tiene la pestaña/);
});
test('processing mode is enforced by the apply function',()=>{
  const draws={'1':{nombre:'D1',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:[]}}}};
  const h=processHarness('12 34 con 5',[1],draws,false);
  h.chk.checked=false;
  h.process();
  assert.deepEqual(draws['1'].tablasActivas['tabla-tradicional'].rows,[]);
});
test('pre-mapping failure in a later draw leaves every earlier table untouched',()=>{
  const old=[{num:'99',montos:{fijo:'7'}}];
  const secondRows=[];
  const draws={'1':{nombre:'D1',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:old}}},'2':{nombre:'D2',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:secondRows}}}};
  const h=processHarness('12 34 con 5',[1,2],draws,true);
  h.sandbox._procValidarDestinos=()=>({errors:[],filasExistentes:0});
  const realMapper=h.sandbox._procCrearFilaDestino;
  h.sandbox._procCrearFilaDestino=function(row,st,kind,tk){if(st===draws['2'].tablasActivas['tabla-tradicional'])throw new Error('simulated mapper failure');return realMapper(row,st,kind,tk);};
  h.process();
  assert.deepEqual(draws['1'].tablasActivas['tabla-tradicional'].rows,old);
  assert.deepEqual(draws['2'].tablasActivas['tabla-tradicional'].rows,secondRows);
  assert.equal(h.confirmCount(),0);
});
test('valid text is staged and applied to every loaded selected draw with independent row objects',()=>{
  const draws={'1':{nombre:'D1',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:[]}}},'2':{nombre:'D2',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:[]}}}};
  const h=processHarness('12 34 con 5',[1,2],draws,true);
  h.process();
  const r1=draws['1'].tablasActivas['tabla-tradicional'].rows,r2=draws['2'].tablasActivas['tabla-tradicional'].rows;
  assert.equal(r1.length,1);assert.equal(r2.length,1);
  assert.equal(JSON.stringify(r1[0]),JSON.stringify(r2[0]));assert.notEqual(r1[0],r2[0]);
});
test('existing rows are preserved when replacement confirmation is cancelled',()=>{
  const existing=[{num:'99',montos:{fijo:'7'}}];
  const draws={'1':{nombre:'D1',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:existing}}}};
  const h=processHarness('12 34 con 5',[1],draws,false);
  h.process();
  assert.deepEqual(draws['1'].tablasActivas['tabla-tradicional'].rows,existing);
  assert.equal(h.confirmCount(),1);
});
test('live UI renders line diagnostics for invalid pasted text',()=>{
  const h=uiHarness('12 34 bad con 5',[1],true);
  assert.equal(h.errorBox.style.display,'block');
  assert.match(h.errorBox.innerHTML,/Línea/);
});
test('table totals cover Pick2, PF, Fijo, Corridos, Pick3, Pick5 and VS variants',()=>{
  compareRowTotal({label:'Trad all',kind:'multi',numDigits:2,forms:['pick2','pf','fijo','corridos','parlet']},['pick2','pf','fijo','corridos','parlet'],{num:'12 34',montos:{pick2:'1',pf:'2',fijo:'3',corridos:'4',parlet:'5'}});
  compareRowTotal({label:'Pick3',kind:'single',numDigits:3,forms:['pick3']},['pick3'],{num:'123 456',montos:{pick3:'4'}});
  compareRowTotal({label:'Pick5',kind:'single',numDigits:5,forms:['pick5']},['pick5'],{num:'12345 67890',montos:{pick5:'1.5'}});
  compareRowTotal({label:'VS PF',kind:'vs_groups',numDigits:2,forms:['vspf']},['vspf'],{numA:'12 34',numB:'56',monto:'2'});
  compareRowTotal({label:'VS Pick2',kind:'vs_groups',numDigits:2,forms:['vspick2']},['vspick2'],{numA:'12',numB:'56 78',monto:'2'});
  compareRowTotal({label:'Pick2 vs PF',kind:'vs_groups',numDigits:2,forms:['pick2vspf']},['pick2vspf'],{numA:'12 34',numB:'56 78',monto:'1'});
  compareRowTotal({label:'Solo Parlet',kind:'solo_parlet',numDigits:2,forms:['parlet']},['parlet'],{num:'12 34 56',montos:{parlet:'3'}});
});
test('blocks candado when Parlet is not active',()=>{assert.ok(candadoErrors(['candado'],0,5,1).length>0);});
test('blocks linked candado amounts that do not match Parlet combinations',()=>{assert.ok(candadoErrors(['parlet','candado'],2,5,3).length>0);});
test('allows candado amount matching Parlet times combinations',()=>{assert.equal(candadoErrors(['parlet','candado'],2,6,3).length,0);});
test('tripleta table row becomes one grouped item with one amount',()=>{const a=tripleta.itemForRow(['12','34','56'],5,9);assert.equal(a.length,1);assert.equal(a[0].numero,'12 34 56');assert.equal(a[0].monto,5);});
test('tripleta row validation requires exactly three numbers and positive amount',()=>{assert.equal(tripleta.validateRow('12 34 56',['12','34','56'],7),null);assert.match(tripleta.validateRow('12 34 56 78',['12','34','56','78'],7),/exactamente tres/);assert.match(tripleta.validateRow('12 34 56',['12','34','56'],0),/monto/);});
test('tripleta helper refuses incomplete rows',()=>{assert.deepEqual(tripleta.itemForRow(['12','34'],5,9),[]);assert.deepEqual(tripleta.itemForRow(['12','34','ab'],5,9),[]);});
test('accepts T/D shorthand with a following amount',()=>{const a=run('T 7 con 25');assert.equal(a.ok,true,JSON.stringify(a.errors));const b=run('D 8 1 5 con 50');assert.equal(b.ok,true,JSON.stringify(b.errors));});
test('accepts inline traditional numbers and fixed amount',()=>{const r=run('12 34 con 5');assert.equal(r.ok,true);assert.equal(r.errors.length,0);assert.ok(r.rows.length>0);});
test('routes Pick 3 text to the Pick 3 tab rather than Tradicional',()=>{
  const r=run('pick3 123 con 5');
  assert.equal(r.ok,true,JSON.stringify(r.errors));
  assert.ok(r.rows.length>0);
  assert.equal(r.rows[0].tabla,'tabla-pick3');
  assert.equal(r.rows[0].montos.pick3,'5');
});
test('routes traditional text to the Tradicional tab',()=>{
  const r=run('12 34 con 5');
  assert.equal(r.ok,true,JSON.stringify(r.errors));
  assert.equal(r.rows[0].tabla,'tabla-tradicional');
  assert.equal(r.rows[0].montos.fijo,'5');
});
test('accepts group on previous line with amount instruction',()=>{const r=run('12 34\ncon 5 y 2');assert.equal(r.ok,true);});
test('rejects a final number group without amount',()=>{const r=run('12 34');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/último grupo/.test(e.message)));});
test('rejects unknown tokens instead of silently dropping them',()=>{const r=run('12 34 blabla con 5');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/Token no reconocido/.test(e.message)));});
test('rejects text amounts with more than two decimals and trailing garbage',()=>{const amount=run('12 34 con 5.123');assert.equal(amount.ok,false);assert.ok(amount.errors.some(e=>/dos decimales/.test(e.message)));const garbage=run('pick4 1234 con 5 extra');assert.equal(garbage.ok,false);});
test('rejects zero amount',()=>{const r=run('12 34 con 0');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/mayores que cero/.test(e.message)));});
test('routes Pick4 explicit text into Pick4 and validates digit length',()=>{const r=run('pick4 1234 con 5');assert.equal(r.ok,true,JSON.stringify(r.errors));assert.equal(r.rows[0].tabla,'tabla-pick4');assert.equal(r.rows[0].montos.pick4,'5');const bad=run('pick4 123 con 5');assert.equal(bad.ok,false);});
test('supports VS PF abbreviation expansions and preserves Pick4/Pick5 full tokens',()=>{
  const vs=run('T7 vspf D3 con 20');
  assert.equal(vs.ok,true,JSON.stringify(vs.errors));
  assert.equal(vs.rows[0].tabla,'tabla-vspf');
  assert.equal(vs.rows[0].numA.split(' ').length,10);
  assert.equal(vs.rows[0].numB.split(' ').length,10);
  const p4=run('pick4 1234 5678 con 5');
  assert.equal(p4.ok,true,JSON.stringify(p4.errors));
  assert.equal(p4.rows[0].num,'1234 5678');
  const p5=run('pick5 12345 67890 con 5');
  assert.equal(p5.ok,true,JSON.stringify(p5.errors));
  assert.equal(p5.rows[0].num,'12345 67890');
});
test('routes every supported modality to its destination table',()=>{
  const cases=[
    ['pick2 12 34 con 5','tabla-tradicional','pick2'],
    ['pf 12 34 con 5','tabla-tradicional','pf'],
    ['pick3 123 456 con 5','tabla-pick3','pick3'],
    ['pick4 1234 5678 con 5','tabla-pick4','pick4'],
    ['pick5 12345 67890 con 5','tabla-pick5','pick5'],
    ['centenas corridas 123 456 con 5','tabla-centenas','centenas corridas'],
    ['12 34 vs 56 78 con 5','tabla-vs','vs'],
    ['12 vspf 34 con 5','tabla-vspf','vspf'],
    ['12 vspick2 34 con 5','tabla-vspick2','vspick2'],
    ['12 34 pick2vspf 56 con 5','tabla-pick2vspf','pick2vspf'],
    ['vs100 12 34 con 5','tabla-vs100','vs100'],
    ['pos 2 12 34 con 5','tabla-posiciones','posicion'],
    ['tripleta 12 34 56 con 5','tabla-tripleta','tripleta'],
    ['solo parlet 12 34 56 con 5','tabla-solo-parlet','parlet'],
    ['12 34 pick2 con 5','tabla-tradicional','pick2'],
    ['12 34 pf con 5','tabla-tradicional','pf'],
    ['123 456 pick3 con 5','tabla-pick3','pick3'],
    ['1234 5678 pick4 con 5','tabla-pick4','pick4'],
    ['12345 67890 pick5 con 5','tabla-pick5','pick5'],
    ['123 456 centenas corridas con 5','tabla-centenas','centenas corridas'],
    ['12 34 vs100 con 5','tabla-vs100','vs100'],
    ['12 34 56 tripleta con 5','tabla-tripleta','tripleta'],
  ];
  cases.forEach(([text,table,form])=>{
    const result=run(text);
    assert.equal(result.ok,true,text+': '+JSON.stringify(result.errors));
    assert.equal(result.rows[0].tabla,table,text);
    assert.ok(result.rows[0].montos&&result.rows[0].montos[form]||result.rows[0].monto,text);
  });
});
test('accepts one explicit pair with con amount',()=>{const r=run('12x34 con 10');assert.equal(r.ok,true,JSON.stringify(r.errors));assert.equal(r.rows[0].montos.parlet,'10');});
test('routes multiple explicit pairs with a shared Parlet amount',()=>{const r=run('12x34 56x78 con 10');assert.equal(r.ok,true,JSON.stringify(r.errors));assert.equal(r.rows.length,2);assert.equal(r.rows[0].montos.parlet,'10');assert.equal(r.rows[1].montos.parlet,'10');});
test('accepts explicit pairlets completed with "cada parle"',()=>{const r=run('12x34\n13x14\ncada parle 2');assert.equal(r.ok,true);});
test('rejects orphan instruction',()=>{const r=run('con 5');assert.equal(r.ok,false);});
test('rejects mixed 2- and 3-digit groups',()=>{const r=run('12 123 con 5');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/No mezcles/.test(e.message)));});
test('accepts bracket headers and card metadata',()=>{const r=run('[Cliente X]\nTarjeta 123\n12 34 con 5');assert.equal(r.ok,true);});
test('supports standalone fixed/corridos suffixes after a number group',()=>{const r=run('12 34\n5f 10c');assert.equal(r.ok,true,JSON.stringify(r.errors));assert.equal(r.rows[0].montos.fijo,'5');assert.equal(r.rows[0].montos.corridos,'10');});
test('supports amount suffixes on inline groups (25f)',()=>{const r=run('12 34 5f');assert.equal(r.ok,true);assert.equal(r.rows[0].montos.fijo,'5');});
test('detects invalid amount text appended to group',()=>{const r=run('12 34 con 5 error');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/Texto no reconocido/.test(e.message)));});

test('live processor stays aria-disabled when pasted text is empty',()=>{
  const h=uiHarness('',[1],true);
  assert.equal(h.updateResult.ok,true);
  assert.equal(h.button.disabled,false);assert.equal(h.button.getAttribute('aria-disabled'),'true');
});

test('live processor marks aria-disabled when destination form is not enabled',()=>{
  const h=uiHarness('12 34 con 5',[1],true,{'1':{nombre:'Test',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['corridos'],rows:[]}}}});
  assert.equal(h.button.disabled,false);assert.equal(h.button.getAttribute('aria-disabled'),'true');
  assert.match(h.errorBox.innerHTML,/habilita la forma/);
});
test('live processor marks aria-disabled while draw configuration is loading',()=>{
  const h=uiHarness('12 34 con 5',[1],true,{'1':{nombre:'Test',cargado:false,tablasActivas:{}}});
  assert.equal(h.button.disabled,false);assert.equal(h.button.getAttribute('aria-disabled'),'true');
  assert.match(h.errorBox.innerHTML,/configuración aún cargando/);
});

test('live processor marks aria-disabled when selected draw is missing destination tab',()=>{
  const textarea={value:'pick3 123 con 5',scrollTop:0},button={disabled:false,style:{},attributes:{},setAttribute(name,value){this.attributes[name]=String(value);},getAttribute(name){return this.attributes[name]??null;}},checkbox={checked:true},errorBox={style:{},innerHTML:''};
  const doc={getElementById:id=>({procesarText:textarea,btnProcAhora:button,chkProcesar:checkbox,procErrores:errorBox}[id]||null)};
  const a=template.indexOf('function _procNormalizarTexto(texto){'),b=template.indexOf('function _procValidarTexto(texto){',a),u=template.indexOf('function _procValidarDestinos(filas){'),z=template.indexOf('  (function _bindProcesarText',u);
  const w=template.indexOf('function _procValidarTexto(texto){'),x=template.indexOf('function _procProcesarTexto(){',w);
  const sandbox={document:doc,window:{ApostarTextValidator:textValidator},ordenSorteos:[1],sorteosActivos:{'1':{nombre:'Test',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:[]}}}},_procActualizarEstado(){}};
  vm.runInNewContext(template.slice(a,b)+template.slice(w,x)+template.slice(u,z)+';this.update=_procActualizarUI;',sandbox);
  sandbox.update();
  assert.equal(button.disabled,false);assert.equal(button.getAttribute('aria-disabled'),'true');
  assert.match(errorBox.innerHTML,/no tiene la pestaña/);
});

test('user invalid block produces three line errors and preserves token 5p',()=>{
  const r=run('T7 con 25\n123 456 con 20\n12 con 5p\nhola mundo\n34 56 con');
  assert.equal(r.ok,false);
  assert.equal(r.errors.length,3);
  assert.ok(r.errors.some(e=>e.line===3&&e.token==='5p'));
  assert.ok(r.errors.some(e=>e.line===4&&/Token no reconocido/.test(e.message)));
  assert.ok(r.errors.some(e=>e.line===5&&/monto|instrucción/i.test(e.message)),JSON.stringify(r.errors));
});

test('valid first line cannot make an unparseable later line pass',()=>{
  const r=validate('12 34 con 5\ntexto no reconocido',{
    normalize:x=>String(x||''),
    parseAmounts:x=>{const m=String(x||'').match(/con\\s+(\\d+)/i);return m?{fijo:m[1]}:{};},
    detectInstruction:x=>{const m=String(x||'').match(/\\s+con\\s+/i);return m?m.index+1:-1;},
    parseText:x=>String(x||'').split(/\\r?\\n/).filter(l=>/12 34 con 5/.test(l)).map(()=>({num:'12 34',montos:{fijo:'5'},tabla:'tabla-tradicional'}))
  });
  assert.equal(r.ok,false);
  assert.ok(r.errors.some(e=>e.line===2));
});
test('strict group validation refuses unrecognized, wrong-width and ambiguous tokens',()=>{
  assert.equal(textValidator.validateGroup('12 xyz 34',2,{}).ok,false);
  assert.equal(textValidator.validateGroup('1234 56',2,{}).ok,false);
  assert.equal(textValidator.validateGroup('123 xyz 456',3,{}).ok,false);
  assert.equal(textValidator.validateGroup('1234 5678',4,{}).ok,true);
  assert.equal(textValidator.validateGroup('12x34',2,{allowPairs:true}).ok,true);
  assert.equal(textValidator.validateGroup('12x3',2,{allowPairs:true}).ok,false);
});
test('explicit modality parsers reject partial token drops for every destination family',()=>{
  const cases=[
    'pick2 12 xyz 34 con 5','pf 12 xyz 34 con 5',
    'pick3 123 xyz 456 con 5','pick4 1234 xyz 5678 con 5','pick5 12345 xyz 67890 con 5',
    'centenas corridas 123 xyz 456 con 5','12 xyz vs 34 con 5','12 xyz vspf 34 con 5',
    '12 xyz vspick2 34 con 5','12 34 pick2vspf 56 xyz con 5',
    'vs100 12 xyz 34 con 5','pos 2 12 xyz 34 con 5',
    'tripleta 12 xyz 34 56 con 5','solo parlet 12 xyz 34 con 5',
    '12 xyz 34 pick2 con 5','12 xyz 34 pf con 5','123 xyz 456 pick3 con 5',
    '1234 xyz 5678 pick4 con 5','12345 xyz 67890 pick5 con 5',
    '123 xyz 456 centenas corridas con 5','12 xyz 34 vs100 con 5','12 xyz 34 56 tripleta con 5'
  ];
  cases.forEach(text=>{const r=run(text);assert.equal(r.ok,false,text+' should fail closed: '+JSON.stringify(r.errors));});
});
test('Pick3 text with multiple amounts is rejected instead of dropping one',()=>{
  assert.equal(run('123 456 con 5 y 2').ok,false);
  assert.equal(run('123 456\n5f 10c').ok,false);
});
test('cada parlet only applies to explicit pairs missing their own amount',()=>{
  const r=run('12x34 con 5\n13x14\ncada parlet 2');
  assert.equal(r.ok,true,JSON.stringify(r.errors));
  assert.equal(r.rows.length,2);
  assert.equal(r.rows[0].montos.parlet,'5');
  assert.equal(r.rows[1].montos.parlet,'2');
});
test('VS permits unequal group counts but rejects incompatible digit widths',()=>{
  const valid=run('12 34 vs 56 con 5');
  assert.equal(valid.ok,true,JSON.stringify(valid.errors));
  assert.equal(valid.rows[0].numA.split(' ').length,2);
  assert.equal(valid.rows[0].numB.split(' ').length,1);
  const bad=run('12 34 vs 123 con 5');
  assert.equal(bad.ok,false);
});
test('traditional reverse shorthand 12V remains valid after normalization',()=>{
  const r=run('12V con 5');
  assert.equal(r.ok,true,JSON.stringify(r.errors));
  assert.equal(r.rows[0].num,'12 21');
});
test('rejects four-digit tokens from being misrouted to traditional',()=>{
  const r=run('1234 con 5');
  assert.equal(r.ok,false);
  assert.ok(r.errors.some(e=>/Pick 4 explícita|4 dígitos/i.test(e.message)));
});


test('stress audit: user-provided 24-line mixed-modality wager reports each line without silent loss',()=>{
  const input="T7 con 25\nD8 con 50\n12 34 56 con 10f\n12 con 10f 20c\n07 70 con 20c\n12x34 56x78 con 10p\n13 14 15 candado 30\n123 456 con 20\n1234 5678 con 30\n12345 con 40\n12 34 vs 56 78 con 10\nT7 vspf D3 con 20\n12 vspick2 34 con 10\n12 34 pick2vspf 56 con 10\n12 34 vs100 con 5\npos 2 12 34 56 con 20\n12 34 56 tripleta con 10\n123 456 centenas con 20\n40V con 15f\nPA con 15\n12 con 5p\n34 56 con\nhola mundo\n8 9 10 con 100f";
  const result=run(input);
  const lineStatuses=input.split(/\r?\n/).map((line,index)=>({line:index+1,text:line,status:result.errors.some(e=>e.line===index+1)?'PARSER_ERROR':'PARSER_VALID',errors:result.errors.filter(e=>e.line===index+1).map(e=>e.message)}));
  console.log('[STRESS 24 LINES] '+JSON.stringify({ok:result.ok,errorCount:result.errors.length,rowCount:result.rows.length,rowsByTable:result.rows.reduce((acc,row)=>{acc[row.tabla]=(acc[row.tabla]||0)+1;return acc;},{}),lines:lineStatuses}));
  assert.equal(lineStatuses.length,24);
  assert.equal(result.ok,lineStatuses.every(line=>line.status==='PARSER_VALID'));
  assert.equal(result.errors.length,lineStatuses.filter(line=>line.status==='PARSER_ERROR').length);
});


test('three-digit wager auto-routes to Pick3 and is accepted only when that destination is loaded',()=>{
  const parsed=run('123 456 con 20');
  assert.equal(parsed.ok,true,JSON.stringify(parsed.errors));
  assert.equal(parsed.rows.length,1);
  assert.equal(parsed.rows[0].tabla,'tabla-pick3');
  assert.equal(parsed.rows[0].montos.pick3,'20');
  const loaded=uiHarness('123 456 con 20',[1],true);
  assert.equal(loaded.button.getAttribute('aria-disabled'),'false');
  const missing=uiHarness('123 456 con 20',[1],true,{'1':{nombre:'Test',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:[]}}}});
  assert.equal(missing.button.getAttribute('aria-disabled'),'true');
  assert.match(missing.errorBox.innerHTML,/no tiene la pestaña tabla-pick3/);
});
