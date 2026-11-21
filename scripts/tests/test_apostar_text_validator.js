const test=require('node:test');
const assert=require('node:assert/strict');
const {validate}=require('../../static/js/apostar_text_validator.js');

function parseAmounts(s){
  s=String(s||'').toLowerCase();
  const r={fijo:null,corridos:null,parlet:null,candado:null};
  let m;
  if((m=s.match(/candado\\s*([0-9]+(?:\\.[0-9]+)?)/)))r.candado=m[1];
  if((m=s.match(/parlet\\s*([0-9]+(?:\\.[0-9]+)?)/)))r.parlet=m[1];
  if((m=s.match(/([0-9]+(?:\\.[0-9]+)?)\\s*f\\b/))||(m=s.match(/con\\s*([0-9]+(?:\\.[0-9]+)?)/)))r.fijo=m[1];
  if((m=s.match(/([0-9]+(?:\\.[0-9]+)?)\\s*c\\b/))||(m=s.match(/corrido\\s*([0-9]+(?:\\.[0-9]+)?)/)))r.corridos=m[1];
  const both=s.match(/con\\s*([0-9]+(?:\\.[0-9]+)?)\\s*y\\s*([0-9]+(?:\\.[0-9]+)?)/);
  if(both){r.fijo=both[1];r.corridos=both[2];}
  return r;
}
function normalize(s){return String(s||'').replace(/\\b(fijo)\\b/gi,'con').replace(/\\s+/g,' ').trim();}
function detect(s){const m=s.match(/\\s+(con|candado|parlet|fijo|corrido)\\s/i);if(m)return m.index+1;const x=s.match(/\\s+((?:\\d+(?:\\.\\d+)?\\s*[fc]\\b)(?:\\s+\\d+(?:\\.\\d+)?\\s*[fc]\\b)*)\\s*$/i);return x?x.index+1:-1;}
function fakeParse(text){return text.trim()? [{num:'12 34',montos:{fijo:'5'}}]:[];}
function run(text){return validate(text,{normalize,parseAmounts,detectInstruction:detect,parseText:fakeParse});}

test('accepts inline group and fixed amount',()=>{const r=run('12 34 con 5');assert.equal(r.ok,true);assert.equal(r.errors.length,0);});
test('accepts a number group followed by amount instruction',()=>{const r=run('12 34\\ncon 5 y 2');assert.equal(r.ok,true);});
test('rejects a final number group without amount',()=>{const r=run('12 34');assert.equal(r.ok,false);assert.match(r.errors[0].message,/sin monto|sin monto asociado/i);});
test('rejects malformed tokens instead of silently dropping them',()=>{const r=run('12 34 blabla con 5');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/Token no reconocido/.test(e.message)));});
test('rejects zero amount',()=>{const r=run('12 34 con 0');assert.equal(r.ok,false);assert.ok(r.errors.some(e=>/mayores que cero/.test(e.message)));});
test('rejects unsupported pick4 instead of silently ignoring it',()=>{const r=run('pick4 1234 con 5');assert.equal(r.ok,false);assert.match(r.errors[0].message,/no admitida/i);});
test('accepts explicit pair with each parlet amount',()=>{const r=run('12x34\\n13x14\\ncada parle 2');assert.equal(r.ok,true);});
test('rejects orphan instruction',()=>{const r=run('con 5');assert.equal(r.ok,false);});
test('rejects mixed 2- and 3-digit groups',()=>{const r=run('12 123 con 5');assert.equal(r.ok,false);assert.match(r.errors[0].message,/No mezcles/);});
test('accepts bracket headers and tarjeta lines as ignored metadata',()=>{const r=run('[Cliente X]\\nTarjeta 123\\n12 34 con 5');assert.equal(r.ok,true);});
