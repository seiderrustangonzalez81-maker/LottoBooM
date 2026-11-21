const test = require('node:test');
const assert = require('node:assert/strict');
const validator = require('../../static/js/apostar_table_validation.js');

const helpers = {
  expandToken: (token, digits) => String(token).length === digits && /^\d+$/.test(String(token)) ? [String(token)] : [],
  numerosEnFila: (row) => ({numeros: String(row.num||'').trim().split(/\s+/).filter(Boolean), paresExplicitos: []}),
  contarParletsDeFila: () => 1
};

test('traditional row with numbers but no positive amount is rejected',()=>{
  const errors=validator.validateRows([{num:'12 34',montos:{fijo:''}}],{kind:'multi',numDigits:2},['fijo'],helpers);
  assert.ok(errors.some(e=>/sin ningún monto positivo/i.test(e.message)));
});

test('empty trailing row is allowed',()=>{
  const errors=validator.validateRows([{num:'',montos:{fijo:''}}],{kind:'multi',numDigits:2},['fijo'],helpers);
  assert.deepEqual(errors,[]);
});

test('positions numbers without amount are rejected',()=>{
  const errors=validator.validateRows([{num:'12 34',posicion:'1',monto:''}],{kind:'posiciones',numDigits:2},['posicion'],helpers);
  assert.ok(errors.some(e=>/sin monto positivo/i.test(e.message)));
});

test('VS groups without amount are rejected',()=>{
  const errors=validator.validateRows([{numA:'12 13',numB:'44 45',monto:''}],{kind:'vs_groups',numDigits:2},['vs'],helpers);
  assert.ok(errors.some(e=>/sin monto positivo/i.test(e.message)));
});

test('amount without numbers is rejected for traditional and VS rows',()=>{
  const traditional=validator.validateRows([{num:'',montos:{fijo:'2'}}],{kind:'multi',numDigits:2},['fijo'],helpers);
  const vs=validator.validateRows([{numA:'',numB:'',monto:'2'}],{kind:'vs_groups',numDigits:2},['vs'],helpers);
  assert.ok(traditional.some(e=>/sin números/i.test(e.message)));
  assert.ok(vs.some(e=>/sin ambos grupos/i.test(e.message)));
});

test('row with numbers and at least one positive applicable amount is valid',()=>{
  const errors=validator.validateRows([{num:'12 34',montos:{fijo:'1.25',pick2:''}}],{kind:'multi',numDigits:2},['fijo','pick2'],helpers);
  assert.deepEqual(errors,[]);
});
