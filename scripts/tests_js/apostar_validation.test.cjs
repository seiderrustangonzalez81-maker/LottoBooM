const test = require('node:test');
const assert = require('node:assert/strict');
const validator = require('../../static/js/apostar_text_validator.js');

function helpers(text) {
  return {
    normalize: value => String(value || '').replace(/\bcon\b/gi, ' con ').replace(/[ \t]+/g, ' ').trim(),
    parseAmounts: value => {
      const out = {};
      const m = String(value || '').match(/con\s+(\d+(?:\.\d+)?)/i);
      if (m) out.fijo = m[1];
      return out;
    },
    detectInstruction: value => {
      const m = String(value || '').match(/\s+con\s+/i);
      return m ? m.index + 1 : -1;
    },
    parseText: value => [{ num: '07 17 27 37 47 57 67 77 87 97', montos: { fijo: '25' }, tabla: 'tabla-tradicional' }]
  };
}

test('validador devuelve rows (contrato que consume apostar.html)', () => {
  const result = validator.validate('T7 con 25', helpers());
  assert.equal(result.ok, true);
  assert.equal(Array.isArray(result.rows), true);
  assert.equal(result.rows.length, 1);
  assert.equal(result.rows[0].tabla, 'tabla-tradicional');
});

test('validador bloquea grupos sin monto', () => {
  const result = validator.validate('12 34', helpers());
  assert.equal(result.ok, false);
  assert.ok(result.errors.length > 0);
});

test('validador bloquea formas avanzadas que el parser no distribuye', () => {
  const result = validator.validate('12 34 vs 56 78 con 5', helpers());
  assert.equal(result.ok, false);
  assert.match(result.errors[0].message, /no admitida/i);
});

test('validador bloquea texto que no produce jugadas', () => {
  const result = validator.validate('texto aleatorio', {
    ...helpers(),
    parseText: () => []
  });
  assert.equal(result.ok, false);
  assert.ok(result.errors.length > 0);
});
