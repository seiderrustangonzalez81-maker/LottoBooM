/* Tripleta item conversion. A table row is one bet of its amount, not one bet per digit. */
(function(root){
  function validateRow(rawNumbers,numbers,amount){
    var raw=String(rawNumbers||'').trim(),monto=Number(amount);
    if(!raw&&(!isFinite(monto)||monto<=0))return null;
    if(!raw)return 'Tripleta: falta ingresar los tres números.';
    if(!Array.isArray(numbers)||numbers.length!==3||numbers.some(function(n){return !/^\\d{2}$/.test(String(n));}))return 'Tripleta requiere exactamente tres números de dos dígitos; no se truncará ni descartará ninguno.';
    if(!isFinite(monto)||monto<=0)return 'Tripleta: el monto debe ser mayor que cero.';
    return null;
  }
  function itemForRow(numbers,amount,sorteoId){
    var monto=Number(amount);
    if(!Array.isArray(numbers)||numbers.length!==3||!isFinite(monto)||monto<=0)return [];
    if(numbers.some(function(n){return !/^\\d{2}$/.test(String(n));}))return [];
    return [{tipo:'tripleta',numero:numbers.join(' '),monto:monto,sorteo_id:sorteoId}];
  }
  var api={itemForRow:itemForRow,validateRow:validateRow};
  root.ApostarTripleta=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
