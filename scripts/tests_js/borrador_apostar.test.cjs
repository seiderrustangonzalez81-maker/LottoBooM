const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname,'../../static/js/borrador_apostar.js'),'utf8');

function boot(userId){
  const store = new Map();
  const elements = {
    selCliente:{value:'client-1',options:[],addEventListener(){}},
    selGestorCuenta:{value:'manager-1',options:[],addEventListener(){}},
    inpFecha:{value:'2026-11-21',addEventListener(){}}
  };
  const document = {
    readyState:'complete',
    body:{appendChild(){}},
    getElementById:id=>elements[id]||null,
    querySelector:()=>({dataset:{id:'fp-1'},textContent:'Pago seleccionado'}),
    querySelectorAll:()=>[],
    addEventListener(){},
    createElement:()=>({style:{},remove(){}})
  };
  const window = {
    _BORRADOR_CTX:{userId,editMode:false},
    location:{pathname:'/apostar/',search:''},
    sorteosActivos:{},
    enviarApuesta(){return undefined}
  };
  const localStorage={getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)};
  const timers=new Map(),intervals=new Map();let nextTimer=0,nextInterval=0;
  const setTimeoutMock=(fn,ms)=>{const id=++nextTimer;timers.set(id,{fn,ms});return id;};
  const clearTimeoutMock=id=>timers.delete(id);
  const setIntervalMock=(fn,ms)=>{const id=++nextInterval;intervals.set(id,{fn,ms});return id;};
  const clearIntervalMock=id=>intervals.delete(id);
  function runTimeout(ms){const matches=Array.from(timers.entries()).filter(([,t])=>t.ms===ms);matches.forEach(([id,t])=>{timers.delete(id);t.fn();});return matches.length;}
  function tickIntervals(){Array.from(intervals.values()).forEach(t=>t.fn());}
  const context={window,document,localStorage,URLSearchParams,Date,JSON,console,setTimeout:setTimeoutMock,clearTimeout:clearTimeoutMock,setInterval:setIntervalMock,clearInterval:clearIntervalMock,Event:function(){},location:window.location};
  vm.runInNewContext(source,context);
  return {api:window._borradorDraftApi,store,window,document,elements,context,runTimeout,tickIntervals,scheduleTimeout:setTimeoutMock};
}

function eligibleSnap(){
  return {
    clienteId:'client-1',gestorId:'manager-1',fpId:'fp-1',fpNombre:'Pago',
    orden:['54'],
    sorteos:{'54':{tablasActivas:{'tabla-tradicional':{rows:[{num:'12 34',montos:{fijo:''}}]}}}}
  };
}

test('draft storage key is scoped by authenticated user',()=>{
  assert.notEqual(boot('17').api.storageKey,boot('18').api.storageKey);
});

test('eligible draft requires client, payment, draw, and at least one number',()=>{
  const {api}=boot('17');
  const snap=eligibleSnap();
  assert.equal(api.isEligible(snap),true);
  const noClient={...snap,clienteId:null};
  const noPayment={...snap,fpId:null,fpNombre:null};
  const noDraw={...snap,orden:[],sorteos:{}};
  const noNumbers={...snap,sorteos:{'54':{tablasActivas:{tradicional:{rows:[{num:'',numA:'',numB:'',montos:{fijo:'5'}}]}}}}};
  assert.equal(api.isEligible(noClient),false);
  assert.equal(api.isEligible(noPayment),false);
  assert.equal(api.isEligible(noDraw),false);
  assert.equal(api.isEligible(noNumbers),false);
});

test('manager selection is a prerequisite when the manager selector exists',()=>{
  const {api}=boot('17');
  assert.equal(api.isEligible(eligibleSnap()),true);
  assert.equal(api.isEligible({...eligibleSnap(),gestorId:null}),false);
});

test('numbers in VS groups also qualify as draft content',()=>{
  const {api}=boot('17');
  const snap=eligibleSnap();
  snap.sorteos['54'].tablasActivas={vs:{rows:[{numA:'12 13',numB:'',monto:''}]}};
  assert.equal(api.hasNumbers(snap),true);
  assert.equal(api.isEligible(snap),true);
});


test('snapshot preserves the selected draw order for replicate master',()=>{
  const {api,window,context}=boot('17');
  window.sorteosActivos={'6':{nombre:'Draw 6',tablasActivas:{}},'54':{nombre:'Draw 54',tablasActivas:{}}};
  context.ordenSorteos=['54','6'];
  const snap=api.snapshot();
  assert.deepEqual(Array.from(snap.orden),['54','6']);
});

test('draft rows are restored only after all selected draws finish loading',()=>{
  const {api,window,document,elements,runTimeout,tickIntervals,scheduleTimeout}=boot('17');
  const snap=eligibleSnap();
  snap.orden=['54'];
  snap.sorteos['54'].tabActual='tabla-tradicional';
  snap.sorteos['54'].tablasActivas={'tabla-tradicional':{forms:['fijo'],rows:[{num:'12 34',montos:{fijo:'5'}}]}};
  const draw={cargado:false,nombre:'Draw 54',tablasActivas:{},tabActual:null};
  window.sorteosActivos={'54':draw};
  const originalGetElement=document.getElementById;
  document.getElementById=id=>id==='selCliente'?null:originalGetElement(id);
  const chip={dataset:{id:'fp-1'},textContent:'Pago seleccionado',click(){}};
  const button={classList:{contains:()=>false},click(){
    draw.cargado=false;
    draw.tablasActivas={};
    scheduleTimeout(()=>{
      draw.cargado=true;
      draw.tablasActivas={'tabla-tradicional':{forms:['fijo'],rows:[{num:'',montos:{fijo:''}}]}};
    },1200);
  }};
  document.querySelector=selector=>selector.indexOf('.sorteo-btn')===0?button:chip;
  document.querySelectorAll=selector=>selector==='.fp-chip'?[chip]:[];
  window.renderTabsSorteo=function(){};
  window.renderMiniResumenSorteo=function(){};
  window.recalcGlobal=function(){};
  api.apply(snap); // Skip client-option loading; test only the draw-config race.
  runTimeout(900);  // The old fixed-delay restoration would run before loading.
  runTimeout(1200); // Simulate configuration finishing and initializing blank rows.
  tickIntervals(); // The new loader-wait callback restores the snapshot now.
  assert.equal(draw.cargado,true);
  assert.equal(draw.tabActual,'tabla-tradicional');
  assert.equal(draw.tablasActivas['tabla-tradicional'].rows[0].num,'12 34');
  assert.equal(draw.tablasActivas['tabla-tradicional'].rows[0].montos.fijo,'5');
});
