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
test('tripleta table row becomes one grouped item with one amount',()=>{const a=tripleta.itemForRow(['12','34','56'],5,9);assert.equal(a.length,1);assert.equal(a[0].numero,'12 34 56');assert.equal(a[0].monto,5);});
test('tripleta row validation requires exactly three numbers and positive amount',()=>{assert.equal(tripleta.validateRow('12 34 56',['12','34','56'],7),null);assert.match(tripleta.validateRow('12 34 56 78',['12','34','56','78'],7),/exactamente tres/);assert.match(tripleta.validateRow('12 34 56',['12','34','56'],0),/monto/);});
test('tripleta helper refuses incomplete rows',()=>{assert.deepEqual(tripleta.itemForRow(['12','34'],5,9),[]);assert.deepEqual(tripleta.itemForRow(['12','34','ab'],5,9),[]);});
test('accepts T/D shorthand with a following amount',()=>{const a=run('T 7 con 25');assert.equal(a.ok,true,JSON.stringify(a.errors));const b=run('D 8 1 5 con 50');assert.equal(b.ok,true,JSON.stringify(b.errors));});
test('accepts inline traditional numbers and fixed amount',()=>{const r=run('12 34 con 5');assert.equal(r.ok,true);assert.equal(r.errors.length,0);assert.ok(r.rows.length>0);});
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
