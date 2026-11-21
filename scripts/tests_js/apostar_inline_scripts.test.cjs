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
