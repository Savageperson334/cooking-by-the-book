'use strict';
const $ = id => document.getElementById(id);
const NS='http://www.w3.org/2000/svg';
const fmt=(n,dec=1)=>Number(n).toLocaleString('en-CA',{maximumFractionDigits:dec,minimumFractionDigits:dec});
const colors={center:'#b3f0b8',mid:'#7ebbe4',surface:'#f4c76b',water:'#7ebbe4',starch:'#c8b3ea',protein:'#f0a4a4',fat:'#f4c76b',sugar:'#d5b2e2',fiber:'#81c9ae',ash:'#a4a6a7'};
const categories=['Grains','Liquids','Fats','Sweeteners','Leavening & salts','Starches & proteins'];
const defaults={oven_c:220,minutes:35,thickness_mm:80,initial_c:22,steam_pct:5,fan:0};
const presets={
  bread:{bread_flour:500,water:340,salt:10,instant_yeast:5,sugar:10},
  rich:{bread_flour:500,milk:270,egg:100,butter:100,sugar:90,salt:9,instant_yeast:8},
  cake:{ap_flour:250,egg:180,milk:140,butter:135,sugar:220,baking_powder:10,salt:2},
  wet:{water:1600,ap_flour:75,salt:9},
  dry:{bread_flour:650,cornstarch:250,sugar:100,salt:10},
  salt:{bread_flour:400,water:240,salt:170,instant_yeast:4},
  oil:{olive_oil:900,ap_flour:80,water:15}
};
const settingDefs=[
  ['oven_c','Oven temperature','°C',-20,400,1],
  ['minutes','Baking time','min',0,300,0.5],
  ['thickness_mm','Slab thickness','mm',2,250,1],
  ['initial_c','Initial dough temperature','°C',-20,100,1],
  ['steam_pct','Oven water vapour level','%*',0,100,1],
  ['fan','Forced-air oven','0 / 1',0,1,1]
];
let catalog=[],amounts={},settings={...defaults},engineReady=false,last=null,requestId=0,renderedId=0,timer=null;
let snapshots={A:null,B:null};
const worker = new Worker('./worker.js');
worker.onmessage = ({data}) => {
  if(data.type==='ready') {
    engineReady=true;$('engine-dot').classList.add('ready');$('engine-status').textContent='Python model ready';$('run').disabled=false;
    queueRun(0);return;
  }
  if(data.type==='error' && !data.id){$('engine-dot').classList.add('failed');$('engine-status').textContent='Engine unavailable';showError(data.error);return;}
  if(data.id !== requestId)return; // a newer slider input has superseded this run
  if(data.type==='error') {showError(data.error);$('run-indicator').textContent='ERROR';return;}
  last={result:data.result,inputs:currentInputs()};renderedId=data.id;
  $('error').hidden=true;$('run-indicator').textContent='MODELLED';$('run').disabled=false;
  $('save-a').disabled=false;$('save-b').disabled=false;$('export').disabled=false;$('csv').disabled=false;
  renderResult();
};
worker.onerror=err=>{showError(String(err.message||'Browser worker failed'));$('engine-status').textContent='Worker error';};
function showError(message){$('error').textContent=message;$('error').hidden=false;}
function currentInputs(){return {amounts:{...amounts},settings:{...settings}};}
function createElement(tag,attrs={},children=[]){const e=document.createElement(tag);for(const [k,v] of Object.entries(attrs)){if(k==='text')e.textContent=v;else if(k==='class')e.className=v;else e.setAttribute(k,String(v));}for(const child of children)e.append(child);return e;}
function loadPreset(id){const initial=presets[id]||presets.bread;for(const item of catalog){amounts[item.id]=Number(initial[item.id]||0);}updateControls();queueRun();}
function updateControls(){for(const item of catalog){const row=document.querySelector(`[data-ingredient="${item.id}"]`);if(!row)continue;row.querySelector('input[type=number]').value=amounts[item.id];row.querySelector('input[type=range]').value=Math.min(amounts[item.id],Number(item.max));}updateMass();}
function updateMass(){const t=Object.values(amounts).reduce((a,b)=>a+Number(b||0),0);$('total-mass').textContent=fmt(t,1)+' g';}
function renderIngredients(){
  const wrapper=$('ingredients');wrapper.replaceChildren();
  for (const category of categories){
    const items=catalog.filter(i=>i.category===category);
    const details=createElement('details',{class:'group'});details.open=category==='Grains'||category==='Liquids'||category==='Leavening & salts';
    details.append(createElement('summary',{text:category}));
    for(const item of items){
      const row=createElement('div',{class:'ingredient','data-ingredient':item.id});
      const id=`item-${item.id}`;
      const label=createElement('label',{for:id,text:item.name});
      const num=createElement('input',{class:'amount',type:'number',min:0,max:100000,step:'0.1',value:item.amount,'aria-label':`${item.name} grams`});
      const slider=createElement('input',{id,type:'range',min:0,max:item.max,step:item.step,value:item.amount,'aria-label':`${item.name} grams slider`});
      slider.addEventListener('input',()=>{amounts[item.id]=Number(slider.value);num.value=slider.value;updateMass();queueRun();});
      num.addEventListener('input',()=>{if(num.value==='')return;const n=Number(num.value);if(!Number.isFinite(n)||n<0)return;amounts[item.id]=Math.min(100000,n);slider.value=String(Math.min(item.max,amounts[item.id]));updateMass();queueRun();});
      num.addEventListener('blur',()=>{num.value=amounts[item.id];});
      row.append(label,num,slider);details.append(row);
    }
    wrapper.append(details);
  }
}
function renderSettings(){const wrapper=$('process-controls');
  for(const [key,label,unit,min,max,step] of settingDefs){
    const row=createElement('div',{class:'setting'});
    const head=createElement('div',{class:'setting-head'});
    const name=createElement('span',{text:label}),val=createElement('strong',{text:fmt(settings[key],step<1?1:0)+' '+unit});
    head.append(name,val);
    const slider=createElement('input',{type:'range',min,max,step,value:settings[key],'aria-label':label});
    slider.addEventListener('input',()=>{settings[key]=Number(slider.value);val.textContent=fmt(settings[key],step<1?1:0)+' '+unit;queueRun();});
    row.append(head,slider);if(key==='thickness_mm')row.append(createElement('div',{class:'subtle',text:'1D slab approximation; effective mass determines area, not heating depth.'}));
    if(key==='steam_pct')row.append(createElement('div',{class:'subtle',text:'* Vapour pressure / water saturation at 100°C; not oven RH.'}));
    wrapper.append(row);
  }
}
function queueRun(delay=360){
  if(!engineReady)return;
  clearTimeout(timer);requestId++;const thisId=requestId;$('run-indicator').textContent='CHANGED';
  $('save-a').disabled=true;$('save-b').disabled=true;
  timer=setTimeout(()=>{$('run-indicator').textContent='SOLVING';$('run').disabled=true;worker.postMessage({id:thisId,payload:{catalog,...currentInputs()}});},delay);
}
function renderResult(){
  if(!last)return;
  const r=last.result,s=r.summary;
  const boxes=$('metrics').children;
  const vals=[[fmt(s.center_c,2),'°C'],[fmt(s.surface_c,2),'°C'],[fmt(s.mass_loss_pct,2),'% of initial mass'],[fmt(s.browning_index,2),'relative; experimental']];
  vals.forEach((pair,i)=>{boxes[i].querySelector('strong').textContent=pair[0];boxes[i].querySelector('small').textContent=pair[1];});
  const segments=['water','starch','protein','fat','sugar','fiber','ash'];
  const comp=r.summary, proportions={water:comp.water_pct,starch:comp.starch_pct,protein:comp.protein_pct,fat:comp.fat_pct,sugar:comp.sugar_pct,fiber:comp.fiber_pct,ash:comp.ash_pct};
  let allocated=0;
  $('components').replaceChildren();const leg=createElement('div',{class:'component-legend'});
  segments.forEach((key,i)=>{let val=key==='ash' ? Math.max(0,100-allocated):Number(proportions[key]||0);allocated+=val;if(val<=0)return;
    const piece=createElement('span',{title:`${key}: ${fmt(val,2)}%`});piece.style.flex=val;piece.style.background=colors[key];$('components').append(piece);
    const item=createElement('span');const dot=createElement('i');dot.style.background=colors[key];item.append(dot,`${key} `);const strong=createElement('b',{text:fmt(val,1)+'%'});item.append(strong);leg.append(item);
  });
  document.querySelectorAll('.component-legend').forEach(n=>n.remove());$('components').after(leg);
  $('computed-note').textContent=`Initial ${fmt(s.total_g,1)} g → estimated ${fmt(s.end_mass_g,1)} g; ${r.metadata.grid_cells} spatial cells; ${r.metadata.steps.toLocaleString()} integration steps. Composition approximate; no measured calibration.`;
  $('warnings').replaceChildren(...r.warnings.map(text=>createElement('li',{text})));drawChart();updateScrub(100);renderComparison();
}
function svgEl(tag,attrs={}){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;}
function drawChart(){
 const svg=$('chart');svg.replaceChildren();if(!last)return;
 const t=last.result.timeline;const maxT=Math.max(1,t.at(-1).minute);const metric=$('metric').value;
 let lines;
 if(metric==='temp')lines=[['center_c','Center',colors.center],['mid_c','Mid-depth',colors.mid],['surface_c','Surface',colors.surface]];
 else if(metric==='moisture')lines=[['center_moisture_pct','Center',colors.center],['surface_moisture_pct','Surface',colors.blue||colors.mid]];
 else if(metric==='mass')lines=[['mass_loss_pct','Water lost',colors.surface]];
 else if(metric==='change')lines=[['starch_progress_pct','Gelatinization proxy',colors.center],['protein_progress_pct','Protein proxy',colors.mid]];
 else lines=[['browning_index','Browning index',colors.surface]];
 const all=lines.flatMap(([key])=>t.map(row=>row[key]));let ymax=Math.max(1,...all);let ymin=Math.min(0,...all);
 const extra=(ymax-ymin)*0.07||1;ymax+=extra;ymin-=extra;
 const left=56,top=15,w=685,h=245;
 for(let i=0;i<=5;i++){
  const y=top+i*h/5;svg.append(svgEl('line',{x1:left,y1:y,x2:left+w,y2:y,stroke:'#304147','stroke-width':1}));
  const l=svgEl('text',{x:left-10,y:y+4,'text-anchor':'end',fill:'#9cafa9','font-size':12});l.textContent=fmt(ymax-(ymax-ymin)*i/5,1);svg.append(l);
 }
 for(let i=0;i<=5;i++){
  const x=left+i*w/5;const l=svgEl('text',{x,y:top+h+23,'text-anchor':'middle',fill:'#9cafa9','font-size':12});l.textContent=fmt(maxT*i/5,1);svg.append(l);
 }
 const xlabel=svgEl('text',{x:left+w/2,y:305,'text-anchor':'middle',fill:'#9cafa9','font-size':12});xlabel.textContent='MINUTES';svg.append(xlabel);
 for(const [key,name,color] of lines){const d=t.map((row,i)=>(i?'L':'M')+(left+w*row.minute/maxT).toFixed(2)+' '+(top+h*(1-(row[key]-ymin)/(ymax-ymin))).toFixed(2)).join(' ');
 svg.append(svgEl('path',{d,fill:'none',stroke:color,'stroke-width':2.7,'stroke-linejoin':'round'}));}
 const leg=$('legend');leg.replaceChildren();for(const [,name,color] of lines){const item=createElement('span');const sw=createElement('i');sw.style.background=color;item.append(sw,name);leg.append(item);}
}
function updateScrub(val){if(!last)return;
 $('scrub').disabled=false;$('scrub').value=val;
 const frames=last.result.timeline;const idx=Math.min(frames.length-1,Math.round((frames.length-1)*val/100));const frame=frames[idx];
 $('scrub-label').textContent=`${fmt(frame.minute,1)} min / ${fmt(last.result.settings.minutes,1)} min`;
 const svg=$('cross-section');svg.replaceChildren();
 const temp=frame.temp_profile||last.result.profile.temp_c;const mn=Math.min(last.result.settings.initial_c,last.result.settings.oven_c,0);const mx=Math.max(last.result.settings.initial_c,last.result.settings.oven_c,100);const n=temp.length;
 for(let i=0;i<n;i++){
   const p=Math.max(0,Math.min(1,(temp[i]-mn)/Math.max(1,mx-mn)));
   const rgb=[Math.round(35+220*p),Math.round(101+120*p-100*p*p),Math.round(194-164*p)];
   svg.append(svgEl('rect',{x:10+i*740/n,y:10,width:740/n+1,height:90,fill:`rgb(${rgb.join(',')})`}));
 }
 svg.append(svgEl('rect',{x:10,y:10,width:740,height:90,rx:3,fill:'none',stroke:'#69807a','stroke-width':1}));
 [['CENTER',frame.center_c,14],['SURFACE',frame.surface_c,620]].forEach((a,i)=>{let text=svgEl('text',{x:a[2],y:119,fill:'#9cafa9','font-size':11});text.textContent=`${a[0]} ${fmt(a[1],1)} °C`;svg.append(text);});
}
function renderComparison(){const a=snapshots.A,b=snapshots.B;if(!a&&!b){$('comparison').textContent='Save snapshots using A and B. The numbers are independent model runs, not measurements.';return;}
 const rows=[['Oven (°C)',x=>x.inputs.settings.oven_c],['Bake (min)',x=>x.inputs.settings.minutes],['Water in mix (%)',x=>x.result.summary.water_pct],['Center (°C)',x=>x.result.summary.center_c],['Surface (°C)',x=>x.result.summary.surface_c],['Mass lost (%)',x=>x.result.summary.mass_loss_pct],['Browning index',x=>x.result.summary.browning_index]];
 const table=createElement('table');const head=createElement('tr');['Metric','A','B','Δ B–A'].forEach(x=>head.append(createElement('th',{text:x})));table.append(head);
 for(const [label,get] of rows){const tr=createElement('tr');tr.append(createElement('td',{text:label}));const av=a?get(a):null,bv=b?get(b):null;[av,bv,av!=null&&bv!=null?bv-av:null].forEach(x=>tr.append(createElement('td',{text:x==null?'—':fmt(x,2)})));table.append(tr);}
 $('comparison').replaceChildren(table);
}
function download(name,text,contentType){const blob=new Blob([text],{type:contentType});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function exportCSV(){if(!last)return;const arr=last.result.timeline;const keys=['minute','center_c','mid_c','surface_c','mass_loss_pct','center_moisture_pct','surface_moisture_pct','starch_progress_pct','protein_progress_pct','browning_index'];const rows=[keys.join(','),...arr.map(o=>keys.map(k=>o[k]).join(','))];download('bakelab-timeseries.csv',rows.join('\n'),'text/csv');}
async function init(){
 try {catalog=await fetch('./ingredients.json').then(r=>{if(!r.ok)throw Error('Cannot load ingredients.json');return r.json();});} catch(e){showError('Could not load ingredients. Serve with python -m http.server or GitHub Pages. '+e.message);return;}
 for(const item of catalog)amounts[item.id]=item.amount;
 renderIngredients();renderSettings();updateMass();
 $('preset').addEventListener('change',e=>loadPreset(e.target.value));
 $('reset').addEventListener('click',()=>{settings={...defaults};$('process-controls').replaceChildren();renderSettings();$('preset').value='bread';loadPreset('bread');});
 $('run').addEventListener('click',()=>queueRun(0));
 $('metric').addEventListener('change',drawChart);
 $('scrub').addEventListener('input',e=>updateScrub(Number(e.target.value)));
 for(const k of ['A','B'])$('save-'+k.toLowerCase()).addEventListener('click',()=>{if(!last||renderedId!==requestId)return;snapshots[k]=structuredClone(last);renderComparison();});
 $('clear-compare').addEventListener('click',()=>{snapshots={A:null,B:null};renderComparison();});
 $('export').addEventListener('click',()=>{if(last)download('bakelab-run.json',JSON.stringify(last,null,2),'application/json');});
 $('csv').addEventListener('click',exportCSV);
}
init();
