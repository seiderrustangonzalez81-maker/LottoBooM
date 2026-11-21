/* LottoBooM apostador text validation: pure, testable, blocks silent partial parses. */
(function(root){
  'use strict';
  function validate(text, helpers){
    helpers=helpers||{};
    var normalize=helpers.normalize||function(x){return String(x||'');};
    var parseAmounts=helpers.parseAmounts||function(){return {};};
    var parseText=helpers.parseText||function(){return [];};
    var detectInstruction=helpers.detectInstruction||function(){return -1;};
    var normalized=normalize(text), lines=normalized.split(/\r?\n/), errors=[], pending=false, explicitPairs=0, hasContent=false;
    function err(line,message){errors.push({line:line,message:message});}
    function ignore(line){return !line||/^\[/.test(line)||/^(tarjeta|tarieta|saldo)\b/i.test(line);}
    function suffixOnly(line){return /^(?:\d+(?:\.\d+)?\s*[fc]\b)(?:\s+\d+(?:\.\d+)?\s*[fc]\b)*$/i.test(line);}
    function nums(group){
      var tokens=String(group||'').toUpperCase().replace(/[-;,_]/g,' ').replace(/\s+/g,' ').trim().split(' ').filter(Boolean);
      if(!tokens.length)return {ok:false,message:'No se encontraron números.'};
      var lengths=[],pendingLetter=null,pendingUsed=false;
      for(var i=0;i<tokens.length;i++){
        var t=tokens[i];
        if(t==='T'||t==='D'){pendingLetter=t;pendingUsed=false;continue;}
        if(/^[TD]\d$/.test(t)||t==='PA'||t==='PAREJAS'||t==='PICK3'||/^\d{2}V$/.test(t)){pendingLetter=null;continue;}
        if(/^\d+$/.test(t)){
          if(t.length>4)return {ok:false,message:'Número demasiado largo: '+t+'. Pick 4/5 aún no está admitido.'};
          if(t.length===1&&!pendingLetter)return {ok:false,message:'Dígito aislado '+t+'. Usa T/D o escribe el número completo.'};
          lengths.push(t.length);if(t.length===1)pendingUsed=true;else{pendingLetter=null;pendingUsed=false;}continue;
        }
        return {ok:false,message:'Token no reconocido: '+t+'.'};
      }
      if(pendingLetter&&!pendingUsed)return {ok:false,message:'La letra T/D quedó sin dígito.'};
      if(lengths.indexOf(2)>=0&&lengths.indexOf(3)>=0)return {ok:false,message:'No mezcles números de 2 y 3 dígitos en el mismo grupo.'};
      if(tokens.indexOf('PICK3')>=0&&lengths.some(function(n){return n!==3;}))return {ok:false,message:'Pick3 requiere números de 3 dígitos.'};
      return {ok:true};
    }
    function instruction(str){
      var m=parseAmounts(str)||{},vals=Object.keys(m).map(function(k){return m[k];}).filter(function(v){return v!==null&&v!=='';});
      if(!vals.length)return {ok:false,message:'No se reconoció ningún monto.'};
      for(var j=0;j<vals.length;j++){var n=Number(vals[j]);if(!isFinite(n)||n<=0)return {ok:false,message:'Todos los montos deben ser mayores que cero.'};}
      var residual=String(str||'').toLowerCase().replace(/\d+(?:\.\d+)?/g,' ').replace(/\b(cada|con|y|f|c|fijo|corridos?|parlet|parle|parl|palet|parler|parley|candado|candad|candao|kandado|canado|caandado)\b/gi,' ').replace(/[🔒🔐🔓]/g,' ').replace(/[\s:]+/g,' ').trim();
      return residual?{ok:false,message:'Texto no reconocido en la instrucción: '+residual+'.'}:{ok:true,montos:m};
    }
    var unsupported=/\b(pick2|pf|pick4|pick5|vs|vspf|vspick2|pick2vspf|vs100|posicion|tripleta|centenas? corridas?)\b/i;
    for(var i=0;i<lines.length;i++){
      var line=String(lines[i]||'').trim();if(ignore(line))continue;hasContent=true;
      if(unsupported.test(line)){err(i+1,'Forma de juego aún no admitida por el parser: '+line.match(unsupported)[0]+'.');continue;}
      var pair=line.match(/^\s*([0-9]{2})\s*[*xX]\s*([0-9]{2})\s*(?:[-\s]\s*([0-9]+(?:\.[0-9]+)?))?\s*$/);
      if(pair){if(pair[3]&&Number(pair[3])<=0)err(i+1,'El monto del parlet debe ser mayor que cero.');else if(!pair[3])explicitPairs++;continue;}
      if(/^cada\s+parlet\b/i.test(line)){var each=instruction(line);if(!explicitPairs)err(i+1,'“Cada parlet” no tiene pares explícitos anteriores.');else if(!each.ok)err(i+1,each.message);else explicitPairs=0;continue;}
      if(suffixOnly(line)){var suf=instruction(line);if(!suf.ok)err(i+1,suf.message);else if(pending)pending=false;else err(i+1,'Monto sin grupo de números asociado.');continue;}
      if(/^(con|candado|parlet|parle|parl|palet|parler|parley)\b/i.test(line)||/^[🔒🔐🔓]/.test(line)){var only=instruction(line);if(!only.ok)err(i+1,only.message);else if(pending)pending=false;else if(explicitPairs&&(only.montos.parlet||only.montos.candado))explicitPairs=0;else err(i+1,'Instrucción sin números anteriores.');continue;}
      var pos=detectInstruction(line);
      if(pos>0){var n=nums(line.slice(0,pos).trim()),m=instruction(line.slice(pos).trim());if(!n.ok)err(i+1,n.message);else if(!m.ok)err(i+1,m.message);else if(pending)err(i+1,'Hay un grupo anterior sin monto asociado.');continue;}
      var pure=nums(line);if(pure.ok){if(pending)err(i+1,'El grupo anterior no tiene monto asociado.');pending=true;}else err(i+1,pure.message);
    }
    if(pending)err(lines.length,'El último grupo de números quedó sin monto.');
    if(explicitPairs)err(lines.length,'Hay parlets explícitos sin monto; añade “cada parle X” o monto individual.');
    var rows=[];try{rows=parseText(normalized)||[];}catch(e){err(1,'No se pudo interpretar: '+(e.message||e));}
    if(hasContent&&!rows.length&&!errors.length)err(1,'No se generaron jugadas.');
    return {ok:errors.length===0,normalized:normalized,rows:rows,errors:errors};
  }
  var api={validate:validate};
  root.ApostarTextValidator=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
