(function(){
  function saveAllSettings(){
    var b=document.getElementById('saveButton');
    if(!b){return;}
    b.disabled=true; b.textContent='Speichern...';

    var a=[];
    var bs=document.querySelectorAll('#alarmForm fieldset');
    for(var i=0;i<bs.length;i++){
      var x=bs[i];
      var t=x.querySelector('input[type="time"]');
      var m=x.querySelector('input[type="text"]');
      if(!t||!m){continue;}
      var tv=(t.value||'').trim();
      var mv=(m.value||'').trim();
      if(!tv&&!mv){continue;}
      var c=x.querySelectorAll('input[type="checkbox"]');
      var daySet={};
      for(var j=0;j<c.length;j++){
        var cb=c[j];
        var label=(cb.parentElement && cb.parentElement.textContent)?cb.parentElement.textContent.trim():'';
        if(cb.checked && (label==='Mo'||label==='Di'||label==='Mi'||label==='Do'||label==='Fr'||label==='Sa'||label==='So')){
          daySet[label]=true;
        }
      }
      var days=[]; for(var k in daySet){ if(daySet.hasOwnProperty(k)){ days.push(k); } }
      days.sort();
      var active = days.length>0 ? 'Aktiv' : 'Inaktiv';
      a.push([tv, mv||'Kein Text', days.join(','), active].join(','));
    }

    function post(url, body, headers, cb){
      try{
        var xhr=new XMLHttpRequest();
        xhr.open('POST', url, true);
        if(headers){ for(var h in headers){ if(headers.hasOwnProperty(h)){ xhr.setRequestHeader(h, headers[h]); } } }
        xhr.onreadystatechange=function(){ if(xhr.readyState===4){ cb(xhr.status>=200 && xhr.status<300); } };
        xhr.send(body);
      }catch(e){ cb(false); }
    }

    var ok1=true, ok2=true; var pending=0;
    function finish(){ b.textContent=(ok1&&ok2)?'Gespeichert':'Fehler'; setTimeout(function(){ b.disabled=false; b.textContent='Speichern'; }, 2000); }

    if(a.length){ pending++; post('/save_alarms', a.join('\n'), {'Content-Type':'text/plain'}, function(success){ ok1=success; if(--pending===0){ finish(); } }); }

    var da=document.getElementById('displayAuto');
    var don=document.getElementById('displayOn');
    var doff=document.getElementById('displayOff');
    if(da&&don&&doff){
      pending++;
      var d=[ 'DISPLAY_AUTO='+(da.checked?'true':'false'), 'DISPLAY_ON_TIME='+don.value, 'DISPLAY_OFF_TIME='+doff.value ];
      post('/save_display_settings', d.join('\n'), null, function(success){ ok2=success; if(--pending===0){ finish(); } });
    }

    if(pending===0){ finish(); }
  }
  try{ window.saveAllSettings=saveAllSettings; }catch(e){}
  function bind(){ var b=document.getElementById('saveButton'); if(b && !b._saveBound){ b._saveBound=true; b.addEventListener('click', saveAllSettings); try{ console.log('Save-Button gebunden'); }catch(e){} } }
  if(document.readyState==='complete' || document.readyState==='interactive'){ bind(); } else { try{ document.addEventListener('DOMContentLoaded', bind); }catch(e){ setTimeout(bind, 200); } }
})();
