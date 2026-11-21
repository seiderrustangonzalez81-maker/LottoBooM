/* LottoBooM apostador text validation: pure, testable, blocks silent partial parses. */
(function(root){
  'use strict';
  function validate(text, helpers){
    helpers=helpers||{};
    var normalize=helpers.normalize||function(x){return String(x||'');};
    var parseAmounts=helpers.parseAmounts||function(){return {};};
    var parseText=helpers.parseText||function(){return [];};
    var detectInstruction=helpers.detectInstruction||function(){return -1;};
    var rawLines=String(text||'').split(/\r?\n/), normalized=normalize(text), lines=normalized.split(/\r?\n/), errors=[], pending=false, explicitPairs=0, hasContent=false;
    function err(line,message,token){errors.push({line:line,message:message,token:token||null});}
    function rawToken(raw){var s=String(raw||''),m=s.match(/\b\d+(?:\.\d+)?[a-z]+\b/i);return m?m[0]:null;}
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
          if(t.length>=4)return {ok:false,message:'Número de '+t.length+' dígitos no admitido sin una modalidad Pick '+t.length+' explícita; no se enviará a Tradicional.',token:t};
          if(t.length===1&&!pendingLetter)return {ok:false,message:'Dígito aislado '+t+'. Usa T/D o escribe el número completo.',token:t};
          lengths.push(t.length);if(t.length===1)pendingUsed=true;else{pendingLetter=null;pendingUsed=false;}continue;
        }
        return {ok:false,message:'Token no reconocido: '+t+'.',token:t};
      }
      if(pendingLetter&&!pendingUsed)return {ok:false,message:'La letra T/D quedó sin dígito.'};
      if(lengths.indexOf(2)>=0&&lengths.indexOf(3)>=0)return {ok:false,message:'No mezcles números de 2 y 3 dígitos en el mismo grupo.'};
      if(tokens.indexOf('PICK3')>=0&&lengths.some(function(n){return n!==3;}))return {ok:false,message:'Pick3 requiere números de 3 dígitos.'};
      return {ok:true};
    }
    function instruction(str){
      var m=parseAmounts(str)||{},vals=Object.keys(m).map(function(k){return m[k];}).filter(function(v){return v!==null&&v!=='';});
      if(!vals.length)return {ok:false,message:'No se reconoció ningún monto.'};
      for(var j=0;j<vals.length;j++){var n=Number(vals[j]);if(!isFinite(n)||n<=0)return {ok:false,message:'Todos los montos deben ser mayores que cero.'};if(/\\.\\d{3,}$/.test(String(vals[j])))return {ok:false,message:'Los montos admiten máximo dos decimales.'};}
      var residual=String(str||'').toLowerCase().replace(/\d+(?:\.\d+)?/g,' ').replace(/\b(cada|con|y|f|c|fijo|corridos?|parlet|parle|parl|palet|parler|parley|candado|candad|candao|kandado|canado|caandado)\b/gi,' ').replace(/[🔒🔐🔓]/g,' ').replace(/[\s:]+/g,' ').trim();
      return residual?{ok:false,message:'Texto no reconocido en la instrucción: '+residual+'.'}:{ok:true,montos:m};
    }
    var modality=/\b(pick2|pf|pick3|pick4|pick5|vs|vspf|vspick2|pick2vspf|vs100|pos(?:icion)?|tripleta|centenas?\s+corridas?|solo\s+parlet)\b/i;
    for(var i=0;i<lines.length;i++){
      var line=String(lines[i]||'').trim();if(ignore(line))continue;hasContent=true;
      if(modality.test(line)){var routed=[];try{routed=parseText(line)||[];}catch(_){} if(!routed.length){err(i+1,'No se pudo interpretar la modalidad o sus números/monto: '+line,rawToken(rawLines[i]));}else{var amountTokens=line.match(/\d+(?:\.\d+)?/g)||[];if(!amountTokens.length||Number(amountTokens[amountTokens.length-1])<=0)err(i+1,'El monto debe ser mayor que cero.');else if(/\\.\\d{3,}$/.test(amountTokens[amountTokens.length-1]))err(i+1,'Los montos admiten máximo dos decimales.');}continue;}
      var pair=line.match(/^\s*([0-9]{2})\s*[*xX]\s*([0-9]{2})\s*(?:[-\s]\s*([0-9]+(?:\.[0-9]+)?))?\s*$/);
      if(pair){if(pair[3]&&Number(pair[3])<=0)err(i+1,'El monto del parlet debe ser mayor que cero.');else if(!pair[3])explicitPairs++;continue;}
      if(/^cada\s+parlet\b/i.test(line)){var each=instruction(line);if(!explicitPairs)err(i+1,'“Cada parlet” no tiene pares explícitos anteriores.');else if(!each.ok)err(i+1,each.message);else explicitPairs=0;continue;}
      if(suffixOnly(line)){var suf=instruction(line);if(!suf.ok)err(i+1,suf.message);else if(pending)pending=false;else err(i+1,'Monto sin grupo de números asociado.');continue;}
      if(/^(con|candado|parlet|parle|parl|palet|parler|parley)\b/i.test(line)||/^[🔒🔐🔓]/.test(line)){var only=instruction(line);if(!only.ok)err(i+1,only.message,(line.match(/\b\d+(?:\.\d+)?\s*[a-z]+\b/i)||[])[0]||null);else if(pending)pending=false;else if(explicitPairs&&(only.montos.parlet||only.montos.candado))explicitPairs=0;else err(i+1,'Instrucción sin números anteriores.');continue;}
      var pos=detectInstruction(line);
      if(pos>0){var n=nums(line.slice(0,pos).trim()),m=instruction(line.slice(pos).trim());if(!n.ok)err(i+1,n.message,n.token);else if(!m.ok)err(i+1,m.message,rawToken(rawLines[i]));else if(pending)err(i+1,'Hay un grupo anterior sin monto asociado.');continue;}
      var pure=nums(line);if(pure.ok){if(pending)err(i+1,'El grupo anterior no tiene monto asociado.');pending=true;}else err(i+1,pure.message,pure.token);
    }
    if(pending)err(lines.length,'El último grupo de números quedó sin monto.');
    if(explicitPairs)err(lines.length,'Hay parlets explícitos sin monto; añade “cada parle X” o monto individual.');
    var rows=[];try{rows=parseText(normalized)||[];}catch(e){err(1,'No se pudo interpretar: '+(e.message||e));}
    // FAIL-CLOSED: every content line must map to a row, be a pure number group
    // awaiting its instruction, or be a valid continuation. Existing line errors
    // are not duplicated. No partial parser output can pass validation.
    for(var cov=0;cov<lines.length;cov++){
      var ln=String(lines[cov]||'').trim(),raw=String(rawLines[cov]||'').trim();
      if(ignore(ln)||errors.some(function(e){return Number(e.line)===cov+1;}))continue;
      var standalone=[];try{standalone=parseText(ln)||[];}catch(_){}
      var pureGroup=nums(ln);
      var continuation=/^(?:con|candado|parlet|parle|parl|palet|fijo|corrido|cada\s+parlet)\b/i.test(ln)||/^[🔒🔐🔓]/.test(ln)||suffixOnly(ln);
      if(!standalone.length&&!pureGroup.ok&&!continuation){
        err(cov+1,'Esta línea no genera ninguna fila de apuesta y no puede procesarse parcialmente.',rawToken(raw));
      }
    }
    if(hasContent&&!rows.length&&!errors.length)err(1,'No se generaron jugadas.');
    return {ok:errors.length===0,normalized:normalized,rows:rows,errors:errors};
  }
  var api={validate:validate};
  root.ApostarTextValidator=api;
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
