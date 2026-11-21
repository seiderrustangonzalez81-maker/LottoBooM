/* Strict pre-submit validation for table rows; prevents silent omissions. */
(function(root){
  'use strict';
  function validateRows(rows,def,forms,helpers){
    rows=rows||[];forms=forms||[];helpers=helpers||{};
    var errors=[];
    function err(index,message){errors.push({row:index+1,message:message});}
    function amount(value){
      if(value===undefined||value===null||String(value).trim()==='')return {blank:true,value:0};
      var n=Number(value);
      if(!isFinite(n)||n<0||Math.round(n*100)!==n*100)return {invalid:true,value:n};
      return {blank:false,value:n};
    }
    function validTokens(text,digits,allowPairs){
      var tokens=String(text||'').trim().split(/\s+/).filter(Boolean),expanded=[],pairs=0,invalid=[];
      tokens.forEach(function(tok){
        if(/^\d{2}[xX]\d{2}$/.test(tok)){
          if(allowPairs&&digits===2)pairs++;
          else invalid.push(tok);
          return;
        }
        var nums=helpers.expandToken?helpers.expandToken(tok,digits):[tok];
        if(!Array.isArray(nums))nums=[nums];
        if(!nums.length||nums.some(function(n){return !new RegExp('^\\d{'+digits+'}$').test(String(n));})){
          invalid.push(tok);return;
        }
        expanded=expanded.concat(nums.map(String));
      });
      return {expanded:expanded,pairs:pairs,invalid:invalid,tokens:tokens};
    }
    rows.forEach(function(row,index){
      row=row||{};
      if(def.kind==='vs_groups'){
        var aText=String(row.numA||'').trim(),bText=String(row.numB||'').trim(),m=amount(row.monto);
        if(m.invalid)err(index,'VS: monto inválido o con más de dos decimales.');
        if(!aText&&!bText&&m.blank)return;
        var a=validTokens(aText,def.numDigits,false),b=validTokens(bText,def.numDigits,false);
        if(a.invalid.length)err(index,'VS: grupo A contiene números inválidos: '+a.invalid.join(', ')+'.');
        if(b.invalid.length)err(index,'VS: grupo B contiene números inválidos: '+b.invalid.join(', ')+'.');
        if(aText&&a.expanded.length===0)err(index,'VS: grupo A vacío.');
        if(bText&&b.expanded.length===0)err(index,'VS: grupo B vacío.');
        if(m.value>0&&(!a.expanded.length||!b.expanded.length))err(index,'VS: monto sin ambos grupos de números.');
        if((aText||bText)&&m.value<=0)err(index,'VS: grupos ingresados sin monto positivo.');
        return;
      }
      if(def.kind==='posiciones'){
        var pText=String(row.num||'').trim(),pMonto=amount(row.monto);
        var pTokens=pText.split(/\s+/).filter(Boolean);
        var bad=pTokens.filter(function(t){return !/^\d{2}$/.test(t);});
        if(bad.length)err(index,'Posiciones requiere números de dos dígitos: '+bad.join(', ')+'.');
        if(pMonto.invalid)err(index,'Posiciones: monto inválido o con más de dos decimales.');
        if(pText&&pMonto.value<=0)err(index,'Posiciones: números ingresados sin monto positivo.');
        if(pMonto.value>0&&!pTokens.length)err(index,'Posiciones: monto sin números.');
        if(pMonto.value>0&&String(row.posicion||'')!=='1'&&String(row.posicion||'')!=='2'&&String(row.posicion||'')!=='3')err(index,'Posiciones: selecciona 1, 2 o 3.');
        return;
      }
      var text=String(row.num||'').trim(),parsed=helpers.numerosEnFila?helpers.numerosEnFila(row,def.numDigits,undefined):{numeros:[],paresExplicitos:[]};
      var tokenResult=validTokens(text,def.numDigits,true);
      if(tokenResult.invalid.length)err(index,'Números inválidos: '+tokenResult.invalid.join(', ')+'.');
      if(def.maxNums&&tokenResult.expanded.length>def.maxNums)err(index,'Esta tabla admite máximo '+def.maxNums+' números; no se truncarán.');
      if(parsed.numeros.length!==tokenResult.expanded.length)err(index,'Hay números repetidos que la tabla descartaría; corrige la fila.');
      var montos=row.montos||{},positive=0,parletMonto=0;
      forms.forEach(function(form){
        var m=amount(montos[form]);
        if(m.invalid)err(index,'Monto inválido para '+form+'.');
        if(m.value>0){
          positive++;
          if(form==='parlet')parletMonto=m.value;
          if(form==='tripleta'){
            if(tokenResult.expanded.length!==3)err(index,'Tripleta exige exactamente tres números de dos dígitos.');
          }else if(form==='parlet'){
            var plays=helpers.contarParletsDeFila?helpers.contarParletsDeFila(row,def.numDigits,def.maxNums):0;
            if(plays<=0)err(index,'Parlet requiere al menos una combinación.');
          }else if(form==='candado'){
            if(forms.indexOf('parlet')<0||!(Number(montos.parlet)>0))err(index,'Candado requiere Parlet activo y monto Parlet asociado.');
          }else if(tokenResult.expanded.length===0)err(index,'Monto para '+form+' sin números.');
        }
      });
      if(text&&positive===0)err(index,'Números ingresados sin ningún monto positivo.');
      if(tokenResult.pairs>0&&!(forms.indexOf('parlet')>=0&&parletMonto>0))err(index,'Los pares explícitos requieren la forma Parlet y su monto.');
      if(!text&&positive>0)err(index,'Monto ingresado sin números.');
    });
    return errors;
  }
  var api={validateRows:validateRows};
  root.ApostarTableValidator=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
