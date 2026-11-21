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
vm.runInNewContext(template.slice(start,end)+';this.helpers={normalize:_procNormalizarTexto,parseAmounts:_procParsearMontos,detectInstruction:_detectarInstruccionPos,parseText:_procParsearTexto,expandNumbers:_procExpandirNumeros};',sandbox);
const h=sandbox.helpers;
function run(text){return validate(text,h);}

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
