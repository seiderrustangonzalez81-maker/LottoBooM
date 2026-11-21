/* Tripleta item conversion. A table row is one bet of its amount, not one bet per digit. */
(function(root){
  function itemForRow(numbers,amount,sorteoId){
    var monto=Number(amount);
    if(!Array.isArray(numbers)||numbers.length!==3||!isFinite(monto)||monto<=0)return [];
    if(numbers.some(function(n){return !/^\\d{2}$/.test(String(n));}))return [];
    return [{tipo:'tripleta',numero:numbers.join(' '),monto:monto,sorteo_id:sorteoId}];
  }
  var api={itemForRow:itemForRow};
  root.ApostarTripleta=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
