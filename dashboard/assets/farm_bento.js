/* AgriGenesis farm bento: the finance-bento layout (net-worth stream, allocation gauge, KPI tiles,
   flow waves, asset list, capsule columns) redrawn with plain DOM + SVG from optimiser results.
   Mounted as a Streamlit components.v2 module; every number comes from `data` (no hardcoded samples). */

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

function loadFonts() {
  const id = "geist-fonts";
  if (document.getElementById(id)) return;
  const l = document.createElement("link");
  l.id = id; l.rel = "stylesheet";
  l.href = "https://fonts.googleapis.com/css2?family=Geist:wght@200;300;400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap";
  document.head.appendChild(l);
}

const markup = (d) => {
  const pills = d.pills.map((p) => `<span class="pill${p.on ? " on" : ""}"><i></i>${esc(p.label)}</span>`).join("");
  const ctrls = d.strategies.length > 1 ? `<div class="ctrls"><div class="seg" id="rank" role="group" aria-label="Strategy"></div></div>` : "";
  const cards = d.strategies.length ? `
        <section class="card h1" id="nw" aria-label="Evolution"></section>
        <section class="card h1" id="alloc" aria-label="Crop mix"></section>
        <section class="card h2 kpi" id="ret" aria-label="Return on inputs"></section>
        <section class="card glass h2 kpi" id="cash" aria-label="Budget headroom"></section>
        <section class="card glass h2 kpi" id="pay" aria-label="Input costs"></section>
        <section class="card glass h2 kpi" id="goals" aria-label="Resources"></section>
        <section class="card h3" id="flow" aria-label="Scenario stress test"></section>
        <section class="card h3" id="crypto" aria-label="Crops"></section>
        <section class="card h3" id="stocks" aria-label="Irrigation"></section>` : `
        <section class="card h1" id="nw" aria-label="Farm"></section>
        <section class="card h1" id="alloc" aria-label="Seasons"></section>
        <section class="card h2 kpi" id="ret" aria-label="Land"></section>
        <section class="card glass h2 kpi" id="cash" aria-label="Plots"></section>
        <section class="card glass h2 kpi" id="pay" aria-label="Water"></section>
        <section class="card glass h2 kpi" id="goals" aria-label="Soil"></section>`;
  return `<div class="fpb-c canvas">
      <div class="top">
        <h1>${esc(d.title)}<span>${esc(d.subtitle)}</span></h1>
        <div class="pills">${pills}</div>${ctrls}
        ${d.avatar ? `<img class="ava" alt="${esc(d.avatarAlt)}" src="${esc(d.avatar)}" onerror="this.remove()">` : ""}
      </div>
      <div class="grid" id="grid">${cards}</div>
      <div class="note">${esc(d.note)}</div>
    </div>
${d.credit ? `<div class="vbrow"><a class="vb-badge" href="https://vasnev.art" target="_blank" rel="noopener" aria-label="Design by vasnev.art"><span class="vb-mark" id="vbm" aria-hidden="true"></span><span><span class="vb-by">design by</span> vasnev.art</span><svg class="vb-arr" viewBox="0 0 12 12" aria-hidden="true"><path d="M3.5 8.5l5-5M4.5 3.5h4v4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></a></div>` : ""}
<div class="tip" id="tip"></div>`;
};

function mount(root, data) {
  let alive = true;
  const frames = new Set();
  const RAF = (cb) => { if (!alive) return 0; const id = requestAnimationFrame((t) => { frames.delete(id); if (alive) cb(t); }); frames.add(id); return id; };
  const $id = (id) => root.querySelector("#" + id);

const reduce=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const ACC='#E8FF1F',T2='rgba(255,255,255,.56)',T3='rgba(255,255,255,.38)',HAIR='rgba(255,255,255,.14)';
const COL=['#FFFFFF','#A9B2FF','#FFB37A','rgba(255,255,255,.35)'];
const ease=t=>1-Math.pow(1-t,3);
const NS='http://www.w3.org/2000/svg';
const el=(t,a={},p)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);p&&p.appendChild(e);return e};

/* ---------- state ---------- */
const S={rank:0,ccy:'USD'};
const RATE={USD:1},SYM={USD:'$'};
const money=(v,{dec=0,compact=false}={})=>{const s=SYM[S.ccy],a=Math.abs(v);
  if(compact&&a>=1000)return (v<0?'−':'')+s+(a/1000).toFixed(a>=10000?0:1)+'K';
  return (v<0?'−':'')+s+a.toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec})};
const num=(v,dec=0)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec});
const kfmt=v=>Math.abs(v)>=1000?(v/1000).toFixed(Math.abs(v)>=10000?0:1)+'K':num(v);
const pct=v=>Math.round(v*100)+'%';
const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));

/* ---------- helpers ---------- */
function bg({top,base,bottom,core}){return `<div class="g" style="background:linear-gradient(180deg,${top} 0%,${base} 36%,${base} 74%,${bottom} 100%)"></div><div class="core" style="background:${core}"></div>`}
const GR={
  blue:{top:'#b9a6ff',base:'#2e43ff',bottom:'#6d7dff',core:'#05082a'},
  graph:{top:'#9a9aa8',base:'#3a3a44',bottom:'#55555f',core:'#060608'},
  pink:{top:'#ffb3d6',base:'#ff2a85',bottom:'#ff6aa8',core:'#3a031c'},
  copper:{top:'#f6bf96',base:'#c2683a',bottom:'#dc8a5c',core:'#1d0b05'},
  green:{top:'#a6e8c8',base:'#36956f',bottom:'#58b58c',core:'#061d15'},
  lime:{top:'#f4ffb8',base:'#a3c400',bottom:'#c9e03a',core:'#121700'},
};
function smoothPath(P,move=true){let d=(move?'M':'L')+`${P[0][0]},${P[0][1]}`;for(let i=0;i<P.length-1;i++){const p0=P[i-1]||P[i],p1=P[i],p2=P[i+1],p3=P[i+2]||p2,k=.17;
  d+=`C${p1[0]+(p2[0]-p0[0])*k},${p1[1]+(p2[1]-p0[1])*k} ${p2[0]-(p3[0]-p1[0])*k},${p2[1]-(p3[1]-p1[1])*k} ${p2[0]},${p2[1]}`}return d}
const P2=(r,a)=>[r*Math.cos(a*Math.PI/180),r*Math.sin(a*Math.PI/180)];
const F={'0':['01110','10001','10011','10101','11001','10001','01110'],'1':['00100','01100','00100','00100','00100','00100','01110'],'2':['01110','10001','00001','00010','00100','01000','11111'],'3':['11111','00010','00100','00010','00001','10001','01110'],'4':['00010','00110','01010','10010','11111','00010','00010'],'5':['11111','10000','11110','00001','00001','10001','01110'],'6':['00110','01000','10000','11110','10001','10001','01110'],'7':['11111','00001','00010','00100','01000','01000','01000'],'8':['01110','10001','10001','01110','10001','10001','01110'],'9':['01110','10001','10001','01111','00001','00010','01100'],'$':['00100','01111','10100','01110','00101','11110','00100'],'€':['00111','01000','11110','01000','11110','01000','00111'],',':['0','0','0','0','0','1','1'],' ':['00','00','00','00','00','00','00'],'−':['000','000','000','111','000','000','000'],'−':['000','000','000','111','000','000','000'],'.':['0','0','0','0','0','0','1']};
function DotNumber(host,pitch){
  const cols=48,svg=el('svg',{class:'dots','aria-hidden':'true'},host),cells=[];
  for(let c=0;c<cols;c++)for(let r=0;r<7;r++){const ci=el('circle',{cx:c*pitch+pitch/2,cy:r*pitch+pitch/2,r:pitch*.36,fill:'#fff',opacity:0},svg);ci.style.transitionDelay=(c*7)+'ms';cells.push([c,r,ci])}
  const set=t=>{const on=new Set();let x=0;for(const ch of t){const g=F[ch]||F[' '];const w=g[0].length;for(let r=0;r<7;r++)for(let k=0;k<w;k++)if(g[r][k]==='1')on.add((x+k)*8+r);x+=w+1}
    const used=Math.max(1,x-1);for(const [c,r,ci] of cells){const v=on.has(c*8+r);ci.setAttribute('opacity',v?1:(c<used?.08:0));ci.style.transform=v?'none':'scale(.55)'}
    svg.setAttribute('width',used*pitch);svg.setAttribute('height',7*pitch);svg.setAttribute('viewBox',`0 0 ${used*pitch} ${7*pitch}`)};
  let raf=0,cur=0;
  return {count(to,dur=900){cancelAnimationFrame(raf);const from=cur,t0=performance.now();let last='';
    const f=now=>{const t=reduce?1:Math.min(1,(now-t0)/dur);cur=from+(to-from)*ease(t);const s=(cur<-.5?'−':'')+SYM[S.ccy]+Math.abs(Math.round(cur)).toLocaleString('en-US');if(s!==last){set(s);last=s}if(t<1)raf=RAF(f)};raf=RAF(f)}};
}
function tween(node,to,fmt,dur=900){const from=+node.dataset.v||0,t0=performance.now();node.dataset.v=to;
  (function f(now){const t=reduce?1:Math.min(1,(now-t0)/dur);node.textContent=fmt(from+(to-from)*ease(t));if(t<1)RAF(f)})(t0)}
const tip=$id('tip');
function showTip(x,y,title,rows){tip.innerHTML=`<div class="t">${title}</div>`+rows.map(([k,v,c])=>`<div class="r"><span>${c?`<i style="background:${c}"></i>`:''}${k}</span><b>${v}</b></div>`).join('');
  tip.classList.add('on');const r=tip.getBoundingClientRect();let L=x+16,T=y-r.height-14;if(L+r.width>innerWidth-8)L=x-r.width-16;if(T<8)T=y+16;tip.style.left=L+'px';tip.style.top=T+'px'}
const hideTip=()=>tip.classList.remove('on');

/* ================= cards ================= */
if(!data.strategies.length)return emptyMode();
const ST=data.strategies,HIST=data.history.length>1?data.history:[...data.history,...data.history];
const cur=()=>ST[S.rank];
const cards=[];

/* ---- Evolution: best / mean / worst fitness as a stream that grows from the centre ---- */
const BAND=[['best','Best','#FFB37A'],['mean','Mean','#A9B2FF'],['worst','Worst','#FFFFFF']];
const nw=$id('nw');
nw.innerHTML=`${bg(GR.blue)}<div class="in-c">
  <div class="row hrow" style="justify-content:space-between"><div class="ttl">Net profit</div>
    <div class="legend">${BAND.map(([k,n,c])=>`<span><i style="background:${c}"></i>${n} fitness</span>`).join('')}</div></div>
  <div class="row nrow" style="margin-top:16px;align-items:flex-end;gap:16px"><div class="nwn"></div>
    <div style="padding-bottom:6px"><div class="delta nwd"></div><div class="muted nwc" style="margin-top:3px"></div></div></div>
  <svg class="nws" style="position:absolute;left:0;right:0;bottom:0;display:block" aria-hidden="true"></svg></div><div class="rim"></div>`;
const nwNum=DotNumber(nw.querySelector('.nwn'),innerWidth<520?5.4:7);
let nwGrow=0,nwRaf=0;
function drawNW(){
  const svg=nw.querySelector('.nws'),W=nw.clientWidth,Hh=226,top=26,bot=26,mid=top+(Hh-top-bot)/2,half=(Hh-top-bot)/2;
  svg.setAttribute('width',W);svg.setAttribute('height',Hh);svg.setAttribute('viewBox',`0 0 ${W} ${Hh}`);
  const D=HIST,n=D.length,bMx=Math.max(...D.map(h=>h.best)),bMn=Math.min(...D.map(h=>h.best)),spread=Math.max(1e-9,...D.map(h=>h.best-h.worst));
  const X=i=>-20+i/(n-1)*(W+40),g=ease(nwGrow);
  /* outer edge grows with the best fitness; inner bands split it by the population spread (best-mean, mean-worst) */
  const H=(p,k)=>{const outer=half*g*(.45+.55*(bMx>bMn?(p.best-bMn)/(bMx-bMn):1));return k==='best'?outer:outer*(1-.8*(p.best-p[k])/spread)};
  const band=k=>{const T=D.map((p,i)=>[X(i),mid-H(p,k)]),B=D.map((p,i)=>[X(i),mid+H(p,k)]).reverse();return smoothPath(T)+smoothPath(B,false)+'Z'};
  const marks=[...new Set([Math.round((n-1)*.18),Math.round((n-1)*.55),n-1])];
  svg.innerHTML=`
    <defs><linearGradient id="nwf" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity=".0"/><stop offset=".25" stop-color="#fff" stop-opacity="1"/></linearGradient>
      <mask id="nwm"><rect width="${W}" height="${Hh}" fill="url(#nwf)"/></mask></defs>
    <g mask="url(#nwm)">${BAND.map(([k,,c],j)=>`<path d="${band(k)}" fill="${c}" opacity="${j===1?1:.95}"/>`).join('')}</g>
    ${marks.map((i,k)=>{const x=Math.min(W-36,Math.max(36,X(i)));return `<g style="opacity:${g>.6?1:0};transition:opacity .4s ${k*.08}s">
      <line x1="${x}" x2="${x}" y1="${top-4}" y2="${Hh-bot+4}" stroke="rgba(0,0,0,.55)" stroke-width="1.5"/>
      <rect x="${x-34}" y="${top-14}" width="68" height="22" rx="11" fill="#000"/><text x="${x}" y="${top+1}" text-anchor="middle" font-size="11" font-weight="600" fill="#fff" font-family="Geist Mono">${D[i].best.toFixed(3)}</text>
      <rect x="${x-30}" y="${Hh-bot-8}" width="60" height="22" rx="11" fill="#000"/><text x="${x}" y="${Hh-bot+7}" text-anchor="middle" font-size="10.5" font-weight="500" fill="rgba(255,255,255,.7)" font-family="Geist Mono">Gen ${D[i].g}</text></g>`}).join('')}
    <line class="hl" y1="${top}" y2="${Hh-bot}" stroke="#fff" stroke-width="1.5" opacity="0"/>
    <rect width="${W}" height="${Hh}" fill="transparent" class="hit"/>`;
  const hit=svg.querySelector('.hit'),hl=svg.querySelector('.hl');
  hit.onpointermove=e=>{const r=svg.getBoundingClientRect(),z=r.width/W,x=(e.clientX-r.left)/z;const i=Math.max(0,Math.min(n-1,Math.round((x+20)/(W+40)*(n-1))));const p=D[i];
    hl.setAttribute('x1',X(i));hl.setAttribute('x2',X(i));hl.setAttribute('opacity',1);
    showTip(r.left+X(i)*z,r.top+(mid-H(p,'best'))*z,'Generation '+p.g,[...BAND.map(([k,nm,c])=>[nm,p[k].toFixed(4),c]),['Best profit',money(p.profit)],['Unique strategies',p.unique]])};
  hit.onpointerleave=()=>{hl.setAttribute('opacity',0);hideTip()};
}
function updateNW(){
  const s=cur(),a=data.history[0].best,b=data.history[data.history.length-1].best;
  nwNum.count(s.net_profit);
  nw.querySelector('.nwd').textContent=(b>=a?'↑ ':'↓ ')+Math.abs((b-a)/(a||1)*100).toFixed(1)+'% fitness';
  nw.querySelector('.nwc').textContent=`Strategy ${s.label} · fitness ${s.fitness.toFixed(4)} · ${data.generations} generations, ${num(data.evaluations)} strategies simulated`;
  if(nwGrow>=1){drawNW();return}
  cancelAnimationFrame(nwRaf);const t0=performance.now();
  const f=now=>{nwGrow=reduce?1:Math.min(1,(now-t0)/1100);drawNW();if(nwGrow<1)nwRaf=RAF(f)};nwRaf=RAF(f);
}
cards.push(updateNW);

/* ---- Crop mix: a half gauge of plot-season tick marks ---- */
const al=$id('alloc');
al.innerHTML=`${bg(GR.graph)}<div class="in-c">
  <div class="row" style="justify-content:space-between"><div class="ttl">Crop mix</div><span class="chip alc"></span></div>
  <svg class="alg" width="300" height="168" viewBox="-150 -150 300 168" style="position:absolute;left:50%;margin-left:-150px;top:70px" aria-hidden="true"></svg>
  <div class="all" style="position:absolute;left:24px;right:24px;bottom:20px"></div></div><div class="rim"></div>`;
function updateAlloc(){
  const s=cur(),M=s.mix,n=56,svg=al.querySelector('.alg');let s2='',acc=[],t=0;
  M.forEach(m=>{t+=m.share;acc.push(t)});
  for(let i=0;i<=n;i++){const f=i/n,a=180+f*180;let j=acc.findIndex(v=>f<=v+1e-9);if(j<0)j=M.length-1;const [x1,y1]=P2(136,a),[x2,y2]=P2(i%7===0?112:118,a);
    s2+=`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${M[j].color}" stroke-width="3.2" stroke-linecap="round" style="opacity:0;animation:tk .4s ${i*12}ms forwards"/>`}
  s2+=`<text y="-22" text-anchor="middle" font-family="Geist" font-weight="200" font-size="52" fill="#fff" letter-spacing="-2">${Math.round(s.cropped_share*100)}<tspan font-size="17" dy="-24" fill="${T2}">%</tspan></text><text y="0" text-anchor="middle" font-size="12" font-weight="500" fill="${T3}" font-family="Geist">of plot-seasons cropped</text>`;
  svg.innerHTML=`<style>@keyframes tk{to{opacity:1}}</style>`+s2;
  al.querySelector('.alc').textContent=s.slots+' plot-seasons';
  al.querySelector('.all').innerHTML=M.slice(0,3).map((m,i)=>
    `<div class="row" style="height:30px;${i?'border-top:1px solid rgba(255,255,255,.1)':''}"><i style="width:8px;height:8px;border-radius:50%;background:${m.color}"></i><span style="flex:1;font-size:13px;font-weight:600">${esc(m.name)}</span><span class="mono muted" style="width:44px;text-align:right">${pct(m.share)}</span><span class="mono" style="width:86px;text-align:right;font-size:13px">${m.count} ${m.count===1?'slot':'slots'}</span></div>`).join('');
}
cards.push(updateAlloc);

/* ---- KPI: return on inputs (solid accent tile) ---- */
const ret=$id('ret');
ret.innerHTML=`${bg(GR.lime)}<div class="in-c"><div class="row" style="justify-content:space-between"><div class="cap">Return on inputs</div><span class="chip rtc">+$0</span></div>
  <div style="position:absolute;left:22px;bottom:32px;display:flex;align-items:center;gap:8px"><svg class="rta" width="30" height="36" viewBox="0 0 34 40" aria-hidden="true"><path d="M17 37V5M5 17L17 5l12 12" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
    <span class="big rtv" style="font-size:52px">0%</span></div>
  <div class="muted rtp" style="position:absolute;left:24px;bottom:14px;font-size:11.5px"></div></div><div class="rim"></div>`;
function updateRet(){const s=cur();
  tween(ret.querySelector('.rtv'),s.roi*100,v=>v.toFixed(0)+'%');
  ret.querySelector('.rtc').textContent=(s.net_profit>=0?'+':'')+money(s.net_profit,{compact:true});
  ret.querySelector('.rta').style.transform=s.net_profit<0?'rotate(180deg)':'none';
  ret.querySelector('.rtp').textContent='Net profit / input cost · normal scenario'}
cards.push(updateRet);

/* ---- KPI: budget headroom with usage ticks ---- */
const cash=$id('cash');
cash.innerHTML=`<div class="in-c"><div class="row" style="justify-content:space-between"><div class="cap">Budget headroom</div><span class="muted">Used</span></div>
  <div class="row" style="margin-top:14px;align-items:baseline;justify-content:space-between"><span class="big csv" style="font-size:38px">0</span><span class="mono" style="font-size:20px;font-weight:500"><span class="crw">0</span><span class="muted" style="font-size:12px"> %</span></span></div>
  <svg class="cst" width="100%" height="22" style="position:absolute;left:24px;right:24px;bottom:22px;width:calc(100% - 48px)" aria-hidden="true"></svg></div>`;
function updateCash(){const s=cur(),used=clamp(s.total_cost/(s.budget||1));
  tween(cash.querySelector('.csv'),s.budget-s.total_cost,x=>money(x));tween(cash.querySelector('.crw'),used*100,x=>x.toFixed(0));
  const svg=cash.querySelector('.cst'),W=svg.getBoundingClientRect().width||220,n=36;let h='';
  for(let i=0;i<n;i++){const x=1+i*(W-2)/(n-1),on=i/(n-1)<=used;h+=`<line x1="${x}" x2="${x}" y1="${i%6===0?2:8}" y2="20" stroke="${on?ACC:'rgba(255,255,255,.28)'}" stroke-width="1.6" stroke-linecap="round" style="transition:stroke .2s ${i*14}ms"/>`}
  svg.innerHTML=h+`<text x="${W}" y="0" dy="-4" text-anchor="end" font-size="10" fill="${T3}" font-family="Geist Mono">${money(s.budget,{compact:true})}</text>`}
cards.push(updateCash);

/* ---- KPI: largest input costs ---- */
const pay=$id('pay');
function updatePay(){const s=cur(),C=s.costs.slice(0,3);
  pay.innerHTML=`<div class="in-c" style="padding-bottom:14px"><div class="row" style="justify-content:space-between"><div class="cap">Input costs</div><span class="mono muted">${money(s.total_cost)}</span></div>
  <div style="margin-top:10px">${C.map((c,i)=>`<div class="row" style="height:34px;${i?'border-top:1px solid rgba(255,255,255,.08)':''}"><i style="width:24px;height:24px;border-radius:8px;background:rgba(255,255,255,.1);display:grid;place-items:center;font:600 11px Geist;font-style:normal">${esc(c.name.charAt(0))}</i><span style="flex:1;min-width:0;font-size:12.5px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(c.name)}</span><span class="muted mono" style="font-size:11px">${pct(c.value/(s.total_cost||1))}</span><span class="mono" style="width:60px;text-align:right;font-size:13px">${money(c.value)}</span></div>`).join('')}</div></div>`}
cards.push(updatePay);

/* ---- KPI: resources (water, soil) ---- */
const goals=$id('goals');
function updateGoals(){const s=cur(),G=[['Water used',clamp(s.water_use/(s.water_avail||1)),` of ${kfmt(s.water_avail)} m³`],['Soil health',clamp(s.soil/100),` ${s.soil_delta>=0?'+':''}${s.soil_delta.toFixed(1)}`]];
  goals.innerHTML=`<div class="in-c"><div class="row" style="justify-content:space-between"><div class="cap">Resources</div><span class="muted">Normal scenario</span></div>
  ${G.map(([n,f,v],k)=>`<div style="margin-top:${k?14:16}px"><div class="row" style="justify-content:space-between;font-size:13px;font-weight:600"><span>${n}</span><span class="mono" style="font-weight:500">${k?s.soil.toFixed(1):pct(f)}<span class="muted">${esc(v)}</span></span></div>
    <svg width="100%" height="12" style="margin-top:8px;display:block" class="gl" data-f="${f}" aria-hidden="true"></svg></div>`).join('')}</div>`;
  RAF(()=>goals.querySelectorAll('.gl').forEach((svg,k)=>{const W=svg.getBoundingClientRect().width,n=40,f=+svg.dataset.f;let h='';
    for(let i=0;i<n;i++){const x=1+i*(W-2)/(n-1),on=i/(n-1)<=f;h+=`<line x1="${x}" x2="${x}" y1="${i%8===0?0:4}" y2="12" stroke="${on?ACC:'rgba(255,255,255,.28)'}" stroke-width="1.6" stroke-linecap="round" style="opacity:0;animation:tk2 .3s ${300+k*150+i*12}ms forwards"/>`}
    svg.innerHTML='<style>@keyframes tk2{to{opacity:1}}</style>'+h}))}
cards.push(updateGoals);

/* ---- Scenario stress test: mirrored waves, revenue above, costs below; other strategies faded ---- */
const flow=$id('flow');
flow.innerHTML=`${bg(GR.pink)}<div class="in-c">
  <div class="row" style="justify-content:space-between"><div><div class="ttl">Scenario stress test</div><div class="muted flw" style="margin-top:4px"></div></div>
    <div class="legend" style="flex-direction:column;gap:4px;align-items:flex-end"><span><i style="background:#fff"></i>Revenue</span><span><i style="background:#FFD0E6"></i>Input costs</span></div></div>
  <svg class="fls" style="position:absolute;left:0;bottom:12px" aria-hidden="true"></svg></div><div class="rim"></div>`;
let flowRaf=0;
function updateFlow(instant){
  const s=cur(),SC=s.scenarios,others=ST.filter((x,i)=>i!==S.rank).slice(0,2),lines=[s,...others];
  const worst=SC.reduce((a,b)=>b.profit<a.profit?b:a,SC[0]);
  flow.querySelector('.flw').innerHTML=`Worst case <span class="mono" style="color:${worst.profit>=0?ACC:'#fff'}">${money(worst.profit)}</span> · ${esc(worst.name)}`;
  const svg=flow.querySelector('.fls'),W=flow.clientWidth,Hh=246,L=44,R=W-52,mid=Hh/2,lab=16,amp=mid-lab-8,n=SC.length;
  const max=Math.max(1,...lines.flatMap(x=>x.scenarios.flatMap(c=>[c.revenue,c.cost])))*1.08,step=Math.max(1000,Math.ceil(max/3/1000)*1000);
  svg.setAttribute('width',W);svg.setAttribute('height',Hh);svg.setAttribute('viewBox',`0 0 ${W} ${Hh}`);
  const X=i=>n>1?L+i/(n-1)*(R-L):(L+R)/2;
  cancelAnimationFrame(flowRaf);const t0=instant?-1e6:performance.now();
  const frame=now=>{const g=ease(reduce?1:Math.min(1,(now-t0)/1200));
    const path=(arr,dir)=>{const P=arr.map((v,i)=>[X(i),mid+dir*(lab+v/max*amp*g)]);return smoothPath(P.length>1?P:[[L,P[0][1]],[R,P[0][1]]])};
    let h='';
    for(let v=0;v<=max;v+=step){const yT=mid-lab-v/max*amp,yB=mid+lab+v/max*amp;
      h+=`<line x1="${L}" x2="${R}" y1="${yT}" y2="${yT}" stroke="${HAIR}"/><line x1="${L}" x2="${R}" y1="${yB}" y2="${yB}" stroke="${HAIR}"/>
        <text x="${L-12}" y="${yT+3.5}" text-anchor="end" font-size="10" fill="${T3}" font-family="Geist Mono">${v?'$'+kfmt(v):'0'}</text><text x="${L-12}" y="${yB+3.5}" text-anchor="end" font-size="10" fill="${T3}" font-family="Geist Mono">${v?'$'+kfmt(v):'0'}</text>`}
    SC.forEach((c,i)=>h+=`<text x="${X(i)}" y="${mid+4}" text-anchor="middle" font-size="10.5" font-weight="500" fill="rgba(255,255,255,.75)" font-family="Geist Mono">${esc(c.short)}</text>`);
    lines.slice().reverse().forEach((x,k)=>{const j=lines.length-1-k,o=[1,.55,.3][j],w=j?1.6:2.4;
      h+=`<path d="${path(x.scenarios.map(c=>c.revenue),-1)}" fill="none" stroke="#fff" stroke-opacity="${o}" stroke-width="${w}" stroke-linecap="round"/>`;
      h+=`<path d="${path(x.scenarios.map(c=>c.cost),1)}" fill="none" stroke="#FFD0E6" stroke-opacity="${o}" stroke-width="${w}" stroke-linecap="round"/>`});
    h+=`<line class="hl" y1="10" y2="${Hh-10}" stroke="#fff" stroke-opacity=".5" opacity="0"/><rect class="hit" x="${L-10}" width="${R-L+20}" height="${Hh}" fill="transparent"/>`;
    svg.innerHTML=h;
    const hit=svg.querySelector('.hit'),hl=svg.querySelector('.hl');
    hit.onpointermove=e=>{const r=svg.getBoundingClientRect(),z=r.width/W,x=(e.clientX-r.left)/z,i=n>1?Math.max(0,Math.min(n-1,Math.round((x-L)/(R-L)*(n-1)))):0,c=SC[i];
      hl.setAttribute('x1',X(i));hl.setAttribute('x2',X(i));hl.setAttribute('opacity',1);
      showTip(r.left+X(i)*z,r.top+(mid-lab-c.revenue/max*amp)*z,c.name+' · '+s.label,[['Revenue',money(c.revenue),'#fff'],['Input costs',money(c.cost),'#FFD0E6'],['Net profit',money(c.profit)],['Yield',c.yield_t.toFixed(1)+' t']])};
    hit.onpointerleave=()=>{hl.setAttribute('opacity',0);hideTip()};
    if(g<1)flowRaf=RAF(frame)};
  flowRaf=RAF(frame);
}
cards.push(()=>updateFlow());

/* ---- Crops: total yield, revenue split and per-crop sparklines ---- */
const cr=$id('crypto');
cr.innerHTML=`${bg(GR.copper)}<div class="in-c"><div class="row" style="justify-content:space-between"><div class="ttl">Crops</div><span class="muted">Normal scenario</span></div>
  <div class="row" style="margin-top:14px;align-items:flex-end;justify-content:space-between"><span class="big crv">0</span><span style="padding-bottom:4px"><span class="delta crd"></span><span class="muted"> of potential</span></span></div>
  <div class="crb" style="margin-top:16px"></div>
  <div class="crl" style="position:absolute;left:24px;right:24px;bottom:14px"></div></div><div class="rim"></div>`;
function spark(vals,key){const d=vals.length>1?vals:[vals[0]||0,vals[0]||0],W=96,H=30,lo=Math.min(...d),hi=Math.max(...d),pad=(hi-lo)*.15||1,Y=v=>H-3-(v-lo+pad)/(hi-lo+2*pad)*(H-6);
  const P=d.map((v,i)=>[2+i/(d.length-1)*(W-6),Y(v)]),e=P[P.length-1],up=d[d.length-1]>=d[0],gid='sg'+key;
  return `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true"><defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>
    <path d="${smoothPath(P)}L${e[0]},${H}L${P[0][0]},${H}Z" fill="url(#${gid})"/><path d="${smoothPath(P)}" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${e[0]}" cy="${e[1]}" r="3" fill="${up?ACC:'#fff'}" stroke="rgba(0,0,0,.35)" stroke-width="1"/></svg>`}
function updateCrops(){const s=cur(),CA=s.crops.slice(0,3),tot=s.crops.reduce((a,c)=>a+c.revenue,0)||1;
  tween(cr.querySelector('.crv'),s.yield_t,x=>x.toFixed(1)+' t');cr.querySelector('.crd').textContent=pct(s.yield_ach);
  cr.querySelector('.crb').innerHTML=`<div style="display:flex;gap:3px;height:6px">${CA.map((c,i)=>`<div style="flex:0 0 calc(${c.revenue/tot*100}% - 2px);border-radius:3px;background:rgba(255,255,255,${[.95,.6,.32][i]});transform-origin:left;transform:scaleX(0);transition:transform .8s var(--ease) ${.1+i*.1}s" class="crs"></div>`).join('')}</div>
    <div style="display:flex;gap:3px;margin-top:7px">${CA.map(c=>`<span class="mono muted" style="flex:0 0 calc(${c.revenue/tot*100}% - 2px);font-size:11px;white-space:nowrap;overflow:hidden">${esc(c.name)} ${pct(c.revenue/tot)}</span>`).join('')}</div>`;
  RAF(()=>RAF(()=>cr.querySelectorAll('.crs').forEach(b=>b.style.transform='scaleX(1)')));
  cr.querySelector('.crl').innerHTML=CA.map((c,i)=>`<div class="row" style="height:50px;${i?'border-top:1px solid rgba(255,255,255,.1)':''}">
    <div style="flex:1;min-width:0"><div style="font-size:13.5px;font-weight:600">${esc(c.name)}</div><div class="mono muted" style="font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(c.where)}</div></div>${spark(c.series,S.rank+'_'+i)}
    <div style="width:80px;text-align:right"><div class="mono" style="font-size:13px">${money(c.revenue)}</div><div class="mono" style="font-size:11px;color:${c.profit>=0?ACC:T3}">${c.yield_t.toFixed(1)} t</div></div></div>`).join('')}
cards.push(updateCrops);

/* ---- Irrigation: water per season as capsule columns, value labels on top ---- */
const st=$id('stocks');
st.innerHTML=`${bg(GR.green)}<div class="in-c"><div class="ttl">Irrigation</div>
  <div style="margin-top:14px"><span class="big stv" style="font-size:34px">0</span></div><div class="row" style="margin-top:6px;gap:8px"><span class="delta std"></span><span class="muted"> of available water</span></div>
  <svg class="sts" style="position:absolute;left:18px;bottom:14px" aria-hidden="true"></svg></div><div class="rim"></div>`;
function updateStocks(instant){const s=cur(),WS=s.water;
  if(!instant){tween(st.querySelector('.stv'),s.water_use,x=>kfmt(x)+' m³');st.querySelector('.std').textContent=pct(clamp(s.water_use/(s.water_avail||1),0,9))}
  const svg=st.querySelector('.sts'),W=Math.max(120,st.clientWidth-36),Hh=160,pb=18,pt=16,n=Math.max(1,WS.length),bw=Math.min(26,(W-30)/n*.55),gap=n>1?(W-30-bw*n)/(n-1):0;
  svg.setAttribute('width',W);svg.setAttribute('height',Hh);
  const max=Math.max(1,...ST.flatMap(x=>x.water.map(w=>w.m3)))*1.05,Y=x=>pt+(Hh-pb-pt)*(1-x/max),peak=WS.reduce((a,w,i)=>w.m3>WS[a].m3?i:a,0);let h='';
  [0,max/2].forEach(t=>h+=`<text x="0" y="${Y(t)+3.5}" font-size="9.5" fill="${T3}" font-family="Geist Mono">${kfmt(t)}</text>`);
  WS.forEach((w,i)=>{const X=(n>1?30:W/2-bw/2)+i*(bw+gap),hot=i===peak;
    h+=`<rect x="${X}" y="${Y(max)}" width="${bw}" height="${Hh-pb-Y(max)}" rx="${bw/2}" fill="rgba(0,0,0,.28)"/>
      <rect class="sb" x="${X}" y="${Hh-pb}" width="${bw}" height="0" rx="${bw/2}" fill="${hot?ACC:'#fff'}" data-y="${Y(w.m3)}" data-h="${Hh-pb-Y(w.m3)}" style="transition:y .8s var(--ease) ${i*70}ms,height .8s var(--ease) ${i*70}ms"/>
      <text x="${X+bw/2}" y="${Math.max(10,Y(w.m3)-5)}" text-anchor="middle" font-size="9.5" fill="#fff" font-family="Geist Mono">${kfmt(w.m3)}</text>
      <text x="${X+bw/2}" y="${Hh-3}" text-anchor="middle" font-size="10" fill="${hot?'#fff':T3}" font-family="Geist Mono">${esc(w.short)}</text>
      <rect class="hit" x="${X-4}" y="0" width="${bw+8}" height="${Hh}" fill="transparent" data-i="${i}"/>`});
  svg.innerHTML=h;
  RAF(()=>RAF(()=>svg.querySelectorAll('.sb').forEach(b=>{b.setAttribute('y',b.dataset.y);b.setAttribute('height',b.dataset.h)})));
  svg.querySelectorAll('.hit').forEach(x=>{x.onpointermove=e=>{const w=WS[+x.dataset.i];showTip(e.clientX,e.clientY,w.season+' · irrigation',[['Water',num(w.m3)+' m³','#fff'],['Share of plan',pct(w.m3/(s.water_use||1))]])};x.onpointerleave=hideTip});
}
cards.push(updateStocks);

/* ---------- controls ---------- */
const rk=$id('rank');
if(rk){rk.innerHTML=ST.map((s,i)=>`<button type="button" aria-pressed="${i===S.rank}" title="Strategy ${esc(s.label)}">${esc(s.label)}</button>`).join('');
  rk.querySelectorAll('button').forEach((b,i)=>b.onclick=()=>{S.rank=i;rk.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',x===b));updateAll()})}
function updateAll(){cards.forEach(f=>f())}
let rz;const ro=new ResizeObserver(()=>{clearTimeout(rz);rz=setTimeout(()=>{if(!alive)return;cancelAnimationFrame(nwRaf);nwGrow=1;drawNW();updateFlow(true);updateStocks(true);updateCash();updateGoals()},120)});
['nw','flow','stocks','cash'].forEach(id=>ro.observe($id(id)));
return boot(()=>{ro.disconnect();clearTimeout(rz)});

/* ---------- shared start / teardown ---------- */
function boot(extra){
  const vbm=$id('vbm'),ON=new Set(['0,0','4,0','1,1','3,1','2,2']);
  if(vbm)for(let i=0;i<15;i++){const x=i%5,y=Math.floor(i/5),e=document.createElement('i');if(ON.has(x+','+y))e.className='on';e.style.setProperty('--x',x);vbm.appendChild(e)}
  const go=()=>{if(!alive)return;$id('grid').classList.add('in');root.querySelectorAll('.card').forEach((c,i)=>c.style.transitionDelay=(i*60)+'ms');updateAll()};
  Promise.race([document.fonts?document.fonts.ready:Promise.resolve(),new Promise(r=>setTimeout(r,600))]).then(go);
  return ()=>{alive=false;frames.forEach(f=>cancelAnimationFrame(f));hideTip();extra&&extra()};
}

/* ---------- before the first evolution: the farm profile in the same bento ---------- */
function emptyMode(){
  const f=data.farm,SE=f.seasons,rain=SE.reduce((a,s)=>a+s.rain,0)||1;
  const nwE=$id('nw');
  nwE.innerHTML=`${bg(GR.blue)}<div class="in-c"><div class="row" style="justify-content:space-between"><div class="ttl">Seasonal budget</div><span class="chip">${esc(f.status)}</span></div>
    <div class="row" style="margin-top:16px;align-items:flex-end;gap:16px"><div class="nwn"></div><div style="padding-bottom:6px"><div class="muted">${esc(f.name)} · ${num(f.area,1)} ha · ${f.plots} plots</div></div></div>
    <div class="empty"><div class="muted" style="font-size:13px;max-width:460px;margin-bottom:14px">${esc(f.hint)}</div><span class="cta">${esc(f.cta)}</span></div></div><div class="rim"></div>`;
  const dn=DotNumber(nwE.querySelector('.nwn'),innerWidth<520?5.4:7);
  const alE=$id('alloc'),cols=['#FFFFFF','#A9B2FF','#FFB37A','rgba(255,255,255,.35)'];
  alE.innerHTML=`${bg(GR.graph)}<div class="in-c"><div class="row" style="justify-content:space-between"><div class="ttl">Rainfall by season</div><span class="chip">${num(rain)} mm</span></div>
    <svg class="alg" width="300" height="168" viewBox="-150 -150 300 168" style="position:absolute;left:50%;margin-left:-150px;top:70px" aria-hidden="true"></svg>
    <div class="all" style="position:absolute;left:24px;right:24px;bottom:20px">${SE.slice(0,3).map((s,i)=>`<div class="row" style="height:30px;${i?'border-top:1px solid rgba(255,255,255,.1)':''}"><i style="width:8px;height:8px;border-radius:50%;background:${cols[i]}"></i><span style="flex:1;font-size:13px;font-weight:600">${esc(s.name)}</span><span class="mono muted" style="width:44px;text-align:right">${pct(s.rain/rain)}</span><span class="mono" style="width:86px;text-align:right;font-size:13px">${num(s.rain)} mm</span></div>`).join('')}</div></div><div class="rim"></div>`;
  const tile=(id,cap,val,sub,glass)=>{$id(id).innerHTML=`${glass?'':bg(GR.lime)}<div class="in-c"><div class="cap">${cap}</div><div class="big" style="position:absolute;left:22px;bottom:34px;font-size:${glass?38:52}px">${esc(val)}</div><div class="muted" style="position:absolute;left:24px;bottom:14px;font-size:11.5px">${esc(sub)}</div></div>${glass?'':'<div class="rim"></div>'}`};
  tile('ret','Land',num(f.area,1)+' ha',`${f.plots} plots · ${esc(f.soil_type)}`);
  tile('cash','Plots',String(f.plots),`${num(f.plots?f.area/f.plots:0,2)} ha each`,1);
  tile('pay','Water',kfmt(f.water)+' m³','Available for irrigation',1);
  tile('goals','Soil health',num(f.soil_health)+'/100',`pH ${num(f.ph,1)}`,1);
  const upd=()=>{dn.count(f.budget);let n=56,acc=[],t=0,s2='';SE.forEach(s=>{t+=s.rain/rain;acc.push(t)});
    for(let i=0;i<=n;i++){const q=i/n,a=180+q*180;let j=acc.findIndex(v=>q<=v+1e-9);if(j<0)j=SE.length-1;const [x1,y1]=P2(136,a),[x2,y2]=P2(i%7===0?112:118,a);
      s2+=`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${cols[Math.min(j,3)]}" stroke-width="3.2" stroke-linecap="round" style="opacity:0;animation:tk .4s ${i*12}ms forwards"/>`}
    s2+=`<text y="-22" text-anchor="middle" font-family="Geist" font-weight="200" font-size="52" fill="#fff" letter-spacing="-2">${SE.length}</text><text y="0" text-anchor="middle" font-size="12" font-weight="500" fill="${T3}" font-family="Geist">seasons planned</text>`;
    alE.querySelector('.alg').innerHTML='<style>@keyframes tk{to{opacity:1}}</style>'+s2};
  updateAll=upd;return boot();
}
}

export default function (component) {
  const { data, parentElement } = component;
  loadFonts();
  const key = JSON.stringify(data);
  if (parentElement.__fpbKey === key && parentElement.__fpbStop) return parentElement.__fpbStop;
  if (parentElement.__fpbStop) parentElement.__fpbStop();
  let host = parentElement.querySelector(".fpb");
  if (!host) { host = document.createElement("div"); host.className = "fpb"; parentElement.appendChild(host); }
  host.innerHTML = markup(data);
  const stop = mount(host, data);
  parentElement.__fpbKey = key;
  parentElement.__fpbStop = () => { stop(); parentElement.__fpbKey = null; parentElement.__fpbStop = null; };
  return parentElement.__fpbStop;
}
