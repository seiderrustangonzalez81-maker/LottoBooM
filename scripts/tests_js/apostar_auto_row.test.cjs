const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html=fs.readFileSync('jugadas/templates/jugadas/apostar.html','utf8');
function extract(start,end){
  const a=html.indexOf(start),b=html.indexOf(end,a);
  assert.ok(a>=0&&b>a, 'extract anchors exist: '+start);
  return html.slice(a,b);
}
const hasContent=extract('function _filaTieneContenido(row, def){','function _autoAddFilaSiNecesario');
const autoAdd=extract('function _autoAddFilaSiNecesario(cont, st, def, sid, i){','function renderTablaActivaSorteo');
const newRow=extract('function newRow(forms, kind){','function _procCrearFilaDestino');
function makeHarness(kind,forms,row){
  const st={forms,rows:[{num:'',numA:'',numB:'',montos:{}},row]};
  const calls=[];
  const context={document:{activeElement:null},sorteosActivos:{S: {tabActual:'T',tablasActivas:{T:st}}},TABLE_DEFS:{T:{kind}},newRow,renderTablaActivaSorteo:sid=>calls.push(sid),setTimeout:fn=>fn()};
  const fn=vm.runInNewContext(hasContent+autoAdd+newRow+';_autoAddFilaSiNecesario',context);
  fn({},st,{kind},'S',1);
  return {st,calls,fn,context};
}

test('row content is driven by numbers, not amount-only input',()=>{
  const isContent=vm.runInNewContext(hasContent+';_filaTieneContenido',{});
  assert.equal(isContent({num:'',montos:{fijo:'5'}},{kind:'multi'}),false);
  assert.equal(isContent({num:'12'},{kind:'multi'}),true);
  assert.equal(isContent({num:'',monto:'5'},{kind:'posiciones'}),false);
  assert.equal(isContent({num:'',numA:'',numB:'',monto:'5'},{kind:'vs_groups'}),false);
});

test('traditional, positions and VS append one blank tail row after numbers',()=>{
  const cases=[
    ['multi',['fijo'],{num:'12',montos:{fijo:''}}],
    ['posiciones',[],{posicion:'1',num:'12',monto:''}],
    ['vs_groups',['vs'],{numA:'12',numB:'',monto:''}]
  ];
  cases.forEach(([kind,forms,row])=>{
    const {st,calls,fn,context}=makeHarness(kind,forms,row);
    assert.equal(st.rows.length,3,kind+' should append one row');
    assert.equal(calls.length,1,kind+' should render once');
    const last=st.rows[2];
    assert.equal(context._filaTieneContenido?context._filaTieneContenido(last,{kind}):false,false);
    fn({},st,{kind},'S',1);
    assert.equal(st.rows.length,3,kind+' should not duplicate tail');
  });
});

test('amount-only row does not create additional empty rows',()=>{
  const {st,calls}=makeHarness('multi',['fijo'],{num:'',montos:{fijo:'5'}});
  assert.equal(st.rows.length,2);
  assert.equal(calls.length,0);
});
