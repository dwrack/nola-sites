const now=new Date(new Date().toLocaleString('en-US',{timeZone:'America/Chicago'}));
const jsDay=(now.getDay()+6)%7, mins=now.getHours()*60+now.getMinutes();
function fmt(m){m=m%1440;let h=Math.floor(m/60),mm=m%60,ap=h<12?'am':'pm';h=h%12||12;return mm?`${h}:${String(mm).padStart(2,'0')}${ap}`:`${h}${ap}`;}
function status(){let open=false,closes=null,opens=null;const today=HOURS[jsDay]||[],yest=HOURS[(jsDay+6)%7]||[];
 for(const [o,c] of yest){if(c>1440&&mins<c-1440){open=true;closes=c-1440;}}
 for(const [o,c] of today){if(o===0&&c>=1440){open=true;closes=null;break;} if(mins>=o&&mins<c){open=true;closes=c;} else if(mins<o&&(opens===null||o<opens))opens=o;}
 const el=document.querySelectorAll('.status');el.forEach(e=>{e.classList.add(open?'open':'closed');e.textContent=open?(closes===null?'Open 24 hours':(closes-mins<=60?`Closing soon · ${fmt(closes)}`:`Open now · closes ${fmt(closes)}`)):(opens!==null?`Closed · opens ${fmt(opens)}`:'Closed today');});}
status();
document.querySelectorAll('tr[data-day]').forEach(tr=>{if(+tr.dataset.day===jsDay)tr.classList.add('today');});
// popular times
(function(){const day=PT[jsDay]&&PT[jsDay].length?PT[jsDay]:(PT[4]||[]);const wrap=document.getElementById('chart');if(!wrap||!day.length){const b=document.querySelector('.busy');if(b)b.remove();return;}
 const h=now.getHours();let best=null;day.forEach(([hr,v])=>{const i=document.createElement('i');i.style.setProperty('--h',Math.max(v,2));i.dataset.l=`${fmt(hr*60)} · ${v<25?'quiet':v<60?'steady':'busy'}`;if(hr===h)i.classList.add('now');wrap.appendChild(i);});
 const open=day.filter(([hr,v])=>v>0);const quiet=open.filter(([hr,v])=>v<40&&hr>=10);const peak=open.reduce((a,b)=>b[1]>a[1]?b:a,[0,0]);
 const s=document.getElementById('busytxt');if(s)s.textContent=peak[1]?`Busiest around ${fmt(peak[0]*60)}${quiet.length?`, quietest ${fmt(quiet[0][0]*60)}`:''}`:'';
 const x=document.getElementById('chartx');if(x&&day.length){x.innerHTML=`<span>${fmt(day[0][0]*60)}</span><span>${fmt(day[Math.floor(day.length/2)][0]*60)}</span><span>${fmt(day[day.length-1][0]*60)}</span>`;}})();
// reveal
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}}),{threshold:.12});document.querySelectorAll('.rv,.ratingblock').forEach(el=>io.observe(el));
function sweep(){document.querySelectorAll('.rv:not(.in),.ratingblock:not(.in)').forEach(el=>{const r=el.getBoundingClientRect();if(r.top<innerHeight*.95&&r.bottom>0)el.classList.add('in');});}addEventListener('scroll',sweep,{passive:true});setTimeout(sweep,600);
// count up
document.querySelectorAll('[data-count]').forEach(b=>{const raw=b.dataset.count;const m=raw.match(/^([^0-9]*)([0-9,]+)(.*)$/);if(!m)return;const target=parseInt(m[2].replace(/,/g,''));if(!target||target>100000)return;b.textContent=m[1]+'0'+m[3];const o=new IntersectionObserver(es=>{if(!es[0].isIntersecting)return;o.disconnect();const t0=performance.now();const dur=1400;(function step(t){const p=Math.min(1,(t-t0)/dur),e=1-Math.pow(1-p,3);b.textContent=m[1]+(m[2].includes(',')?Math.round(target*e).toLocaleString():String(Math.round(target*e)))+m[3];if(p<1)requestAnimationFrame(step);})(t0);});o.observe(b);});
// parallax quote image
const qimg=document.querySelector('.quoteband img');if(qimg&&matchMedia('(min-width:900px)').matches){addEventListener('scroll',()=>{const r=qimg.parentElement.getBoundingClientRect();const p=(r.top+r.height/2-innerHeight/2)/innerHeight;qimg.style.transform=`translateY(${p*-40}px)`;},{passive:true});}
// hide top bar on scroll down
let ly=0;addEventListener('scroll',()=>{const y=scrollY;const top=document.querySelector('.top');top.style.transform=(y>ly&&y>300)?'translateY(-100%)':'translateY(0)';ly=y;},{passive:true});
// lightbox
const imgs=[...document.querySelectorAll('.lb')].map(a=>a.href);const lbx=document.getElementById('lbx'),lbi=lbx.querySelector('img');let idx=0;
function show(i){idx=(i+imgs.length)%imgs.length;lbi.src=imgs[idx];lbx.classList.add('on');}
document.querySelectorAll('.lb').forEach((a,i)=>a.addEventListener('click',e=>{e.preventDefault();show(i);}));
lbx.addEventListener('click',e=>{if(e.target===lbx||e.target.classList.contains('x'))lbx.classList.remove('on');});
lbx.querySelector('.prev').onclick=e=>{e.stopPropagation();show(idx-1);};lbx.querySelector('.next').onclick=e=>{e.stopPropagation();show(idx+1);};
addEventListener('keydown',e=>{if(!lbx.classList.contains('on'))return;if(e.key==='Escape')lbx.classList.remove('on');if(e.key==='ArrowLeft')show(idx-1);if(e.key==='ArrowRight')show(idx+1);});
// share
const sh=document.getElementById('share');if(sh){if(navigator.share)sh.onclick=()=>navigator.share({title:document.title,url:location.href});else sh.onclick=()=>{navigator.clipboard.writeText(location.href);sh.textContent='Link copied';};}
</script>
</body></html>