const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {validate}=require('../../static/js/apostar_text_validator.js');

const template=fs.readFileSync('jugadas/templates/jugadas/apostar.html','utf8');
const start=template.indexOf('function _procNormalizarTexto(texto){');
const end=template.indexOf('function _procValidarTexto(texto){',start);
assert.ok(start>=0&&end>start,'parser helpers must be present in apostar.html');
const sandbox={};
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
  const sandbox={TABLE_DEFS:{},sorteosActivos:{},window:{ApostarTripleta:tripleta}};
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
  const button={disabled:false,style:{}};
  const checkbox={checked:!!checked};
  const errorBox={style:{},innerHTML:''};
  const doc={getElementById:(id)=>({procesarText:textarea,btnProcAhora:button,chkProcesar:checkbox,procErrores:errorBox}[id]||null)};
  const helperStart=template.indexOf('function _procNormalizarTexto(texto){');
  const helperEnd=template.indexOf('function _procValidarTexto(texto){',helperStart);
  const destStart=template.indexOf('function _procValidarDestinos(filas){');
  const uiStart=template.indexOf('function _procRenderErrores');
  const uiEnd=template.indexOf('  (function _bindProcesarText',uiStart);
  assert.ok(uiStart>=0&&uiEnd>uiStart,'live UI helpers must be present');
  const wrapperStart=template.indexOf('function _procValidarTexto(texto){');
  const wrapperEnd=template.indexOf('function _procProcesarTexto(){',wrapperStart);
  assert.ok(wrapperStart>=0&&wrapperEnd>wrapperStart,'validation wrapper must be present');
  const source=template.slice(helperStart,helperEnd)+template.slice(wrapperStart,wrapperEnd)+template.slice(destStart,uiStart)+template.slice(uiStart,uiEnd)+';this.update=_procActualizarUI;';
  const ids=drawIds||[];
  const sorteos={};
  ids.forEach(id=>{
    sorteos[String(id)]=(overrides&&overrides[id])||{nombre:'Test '+id,cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo','corridos','parlet','candado'],rows:[]},'tabla-pick3':{forms:['pick3'],rows:[]}}};
  });
  const sandbox={document:doc,window:{ApostarTextValidator:{validate:validate}},ordenSorteos:ids,sorteosActivos:sorteos,_procActualizarEstado:function(){},};
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
test('live processor button enables only for valid text, mode and selected draw',()=>{
  const valid=uiHarness('12 34 con 5',[1],true);assert.equal(valid.updateResult.ok,true,JSON.stringify(valid.updateResult));assert.equal(valid.button.disabled,false,JSON.stringify({validation:valid.updateResult,checkbox:valid.checkbox}));
  assert.equal(uiHarness('12 34 con 5 bad',[1],true).button.disabled,true);
  assert.equal(uiHarness('12 34 con 5',[],true).button.disabled,true);
  assert.equal(uiHarness('12 34 con 5',[1],false).button.disabled,true);
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
test('rejects zero amount',()=>{const r=run('12 34 con 0');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/mayores que cero/.test(e.message)));});
test('rejects unsupported pick4 instead of silently ignoring it',()=>{const r=run('pick4 1234 con 5');assert.equal(r.ok,false);assert.match(r.errors[0].message,/no admitida/i);});
test('accepts explicit pairlets completed with "cada parle"',()=>{const r=run('12x34\n13x14\ncada parle 2');assert.equal(r.ok,true);});
test('rejects orphan instruction',()=>{const r=run('con 5');assert.equal(r.ok,false);});
test('rejects mixed 2- and 3-digit groups',()=>{const r=run('12 123 con 5');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/No mezcles/.test(e.message)));});
test('accepts bracket headers and card metadata',()=>{const r=run('[Cliente X]\nTarjeta 123\n12 34 con 5');assert.equal(r.ok,true);});
test('supports amount suffixes on inline groups (25f)',()=>{const r=run('12 34 5f');assert.equal(r.ok,true);assert.equal(r.rows[0].montos.fijo,'5');});
test('detects invalid amount text appended to group',()=>{const r=run('12 34 con 5 error');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/Texto no reconocido/.test(e.message)));});

test('live processor stays disabled when pasted text is empty',()=>{
  const h=uiHarness('',[1],true);
  assert.equal(h.updateResult.ok,true);
  assert.equal(h.button.disabled,true);
});

test('live processor disables when a destination form is not enabled',()=>{
  const h=uiHarness('12 34 con 5',[1],true,{'1':{nombre:'Test',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['corridos'],rows:[]}}}});
  assert.equal(h.button.disabled,true);
  assert.match(h.errorBox.innerHTML,/habilita la forma/);
});
test('live processor disables while draw configuration is loading',()=>{
  const h=uiHarness('12 34 con 5',[1],true,{'1':{nombre:'Test',cargado:false,tablasActivas:{}}});
  assert.equal(h.button.disabled,true);
  assert.match(h.errorBox.innerHTML,/configuración aún cargando/);
});

test('live processor disables when selected draw is missing the destination tab',()=>{
  const textarea={value:'pick3 123 con 5',scrollTop:0},button={disabled:false,style:{}},checkbox={checked:true},errorBox={style:{},innerHTML:''};
  const doc={getElementById:id=>({procesarText:textarea,btnProcAhora:button,chkProcesar:checkbox,procErrores:errorBox}[id]||null)};
  const a=template.indexOf('function _procNormalizarTexto(texto){'),b=template.indexOf('function _procValidarTexto(texto){',a),u=template.indexOf('function _procValidarDestinos(filas){'),z=template.indexOf('  (function _bindProcesarText',u);
  const w=template.indexOf('function _procValidarTexto(texto){'),x=template.indexOf('function _procProcesarTexto(){',w);
  const sandbox={document:doc,window:{ApostarTextValidator:{validate}},ordenSorteos:[1],sorteosActivos:{'1':{nombre:'Test',cargado:true,tablasActivas:{'tabla-tradicional':{forms:['fijo'],rows:[]}}}},_procActualizarEstado(){}};
  vm.runInNewContext(template.slice(a,b)+template.slice(w,x)+template.slice(u,z)+';this.update=_procActualizarUI;',sandbox);
  sandbox.update();
  assert.equal(button.disabled,true);
  assert.match(errorBox.innerHTML,/no tiene la pestaña/);
});
