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
  const context={window,document,localStorage,URLSearchParams,Date,JSON,console,setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){},Event:function(){},location:window.location};
  vm.runInNewContext(source,context);
  return {api:window._borradorDraftApi,store,window,document,elements};
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
