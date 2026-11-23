const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('all inline scripts in apostar.html are syntactically valid after Django token substitution', () => {
  const html = fs.readFileSync('jugadas/templates/jugadas/apostar.html', 'utf8');
  const blocks = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)]
    .map((match, index) => ({ index: index + 1, source: match[1] }))
    .filter(block => block.source.trim());
  assert.ok(blocks.length > 0, 'apostar.html must contain inline scripts');
  const failures = [];
  blocks.forEach(block => {
    const source = block.source
      .replace(/{%[\s\S]*?%}/g, '')
      .replace(/{{[\s\S]*?}}/g, '0');
    try {
      new vm.Script(source, { filename: 'apostar.html inline script #' + block.index });
    } catch (error) {
      failures.push('script #' + block.index + ': ' + error.message);
    }
  });
  assert.deepEqual(failures, [], failures.join('\n'));
});

test('Apostar processor button uses native disabled state and semáforo', () => {
  const html = fs.readFileSync('jugadas/templates/jugadas/apostar.html', 'utf8');
  assert.match(html, /btn\.disabled=!uiValido/);
  assert.match(html, /setAttribute\('aria-disabled'/);
  assert.match(html, /Corregir Errores/);
  assert.match(html, /_procUiValido/);
  assert.match(html, /_procTextoProcesado/);
  assert.match(html, /Procesar nuevamente/);
  assert.match(html, /Corrige los errores antes de procesar|No se procesó/);
});

test('Apostar destination validation fails closed when the table validator is missing', () => {
  const html = fs.readFileSync('jugadas/templates/jugadas/apostar.html', 'utf8');
  assert.match(html, /no está cargado el validador de filas; procesamiento bloqueado por seguridad/);
  assert.match(html, /no existe definición de tabla; validación imposible/);
});
