'use strict';
const $ = id => document.getElementById(id);
const NS='http://www.w3.org/2000/svg';
const fmt=(n,dec=1)=>Number(n).toLocaleString('en-CA',{maximumFractionDigits:dec,minimumFractionDigits:dec});
const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
const colors={center:'#b3f0b8',mid:'#7ebbe4',surface:'#f4c76b',water:'#7ebbe4',starch:'#c8b3ea',protein:'#f0a4a4',fat:'#f4c76b',sugar:'#d5b2e2',fiber:'#81c9ae',ash:'#a4a6a7',steam:'#dcebe8',dark:'#203236'};
const ingredientVisuals={
  bread_flour:'#d7c3a0',ap_flour:'#ddd1b8',whole_wheat:'#a57e55',rye_flour:'#876547',oats:'#ccb48b',
  water:'#86c9ff',milk:'#f1efe6',egg:'#f1bd57',banana:'#d8c15f',olive_oil:'#98a35b',butter:'#f4d779',
  sugar:'#f5f2fb',honey:'#d9942f',salt:'#f2eee4',instant_yeast:'#b39263',baking_powder:'#e8edf1',baking_soda:'#eef3f6',
  cornstarch:'#ece9dd',vital_gluten:'#d9c7a0',cocoa:'#5c3b2a'
};
const categories=['Grains','Liquids','Fats','Sweeteners','Leavening & salts','Starches & proteins'];
const defaults={oven_c:220,minutes:35,thickness_mm:80,initial_c:22,steam_pct:5,fan:0,proof_minutes:60,proof_c:26};
const cToF=c=>c*9/5+32;
const fToC=f=>(f-32)*5/9;
const bothTemps=c=>`${fmt(c,1)} °C / ${fmt(cToF(c),1)} °F`;
let temperatureUnit='C';
const temperatureKeys=new Set(['oven_c','initial_c','proof_c']);
const presets={
  bread:{bread_flour:500,water:340,salt:10,instant_yeast:5,sugar:10},
  rich:{bread_flour:500,milk:270,egg:100,butter:100,sugar:90,salt:9,instant_yeast:8},
  cake:{ap_flour:250,egg:180,milk:140,butter:135,sugar:220,baking_powder:10,salt:2},
  wet:{water:1600,ap_flour:75,salt:9},
  dry:{bread_flour:650,cornstarch:250,sugar:100,salt:10},
  salt:{bread_flour:400,water:240,salt:170,instant_yeast:4},
  oil:{olive_oil:900,ap_flour:80,water:15},
  purewater:{water:1000},
  puremilk:{milk:1000},
  watermilk:{water:500,milk:500},
  oilwater:{water:500,olive_oil:500},
  syrup:{sugar:1000,water:220},
  pureoil:{olive_oil:1000},
  bananadry:{water:500,banana:250},
  oatporridge:{water:600,oats:200}
};
const settingDefs=[
  ['proof_minutes','Proofing duration','min',0,720,1],
  ['proof_c','Proofing temperature','°C',-10,55,0.5],
  ['oven_c','Oven temperature','°C',-20,600,1],
  ['minutes','Baking time','min',0,1440,1],
  ['thickness_mm','Initial sample depth','mm',2,250,1],
  ['initial_c','Initial dough temperature','°C',-20,100,1],
  ['steam_pct','Oven water vapour level','%*',0,100,1],
  ['fan','Forced-air oven','0 / 1',0,1,1]
];
let catalog=[],amounts={},settings={...defaults},engineReady=false,last=null,requestId=0,renderedId=0,timer=null;
let snapshots={A:null,B:null};
let playing=false,playHandle=0,playStart=0,playOrigin=0,playValue=100;
const BAKE_PLAY_DURATION=16000; // milliseconds for 0..100 at 1x
const worker = new Worker('./worker.js',{type:'module'});
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
  $('scene-play').disabled=false;$('scene-reset').disabled=false;
  renderResult();
};
worker.onerror=err=>{showError(String(err.message||'Browser worker failed'));$('engine-status').textContent='Worker error';};
function showError(message){$('error').textContent=message;$('error').hidden=false;}
function currentInputs(){return {amounts:{...amounts},settings:{...settings}};}
function createElement(tag,attrs={},children=[]){const e=document.createElement(tag);for(const [k,v] of Object.entries(attrs)){if(k==='text')e.textContent=v;else if(k==='class')e.className=v;else e.setAttribute(k,String(v));}for(const child of children)e.append(child);return e;}
function loadPreset(id){
 const initial=presets[id]||presets.bread;
 for(const item of catalog){amounts[item.id]=Number(initial[item.id]||0);}
 // Demo presets provide controlled thin-pan conditions; other presets keep
 // whatever temperature and duration the user last selected.
 if(id==='bananadry'||id==='oatporridge'){
   settings={...settings,oven_c:260,minutes:240,thickness_mm:15,initial_c:22};
   $('process-controls').replaceChildren();renderSettings();
 }
 updateControls();queueRun();
}
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
      const amountWrap=createElement('div',{class:'amount-wrap'});
      const num=createElement('input',{class:'amount',type:'number',min:0,max:100000,step:String(item.step||0.1),value:item.amount,'aria-label':`${item.name} grams`,inputmode:'decimal'});
      const unit=createElement('span',{class:'unit-chip',text:'g'});
      amountWrap.append(num,unit);
      const slider=createElement('input',{id,type:'range',min:0,max:item.max,step:item.step,value:item.amount,'aria-label':`${item.name} grams slider`});
      slider.addEventListener('input',()=>{amounts[item.id]=Number(slider.value);num.value=slider.value;updateMass();queueRun();});
      num.addEventListener('input',()=>{if(num.value==='')return;const n=Number(num.value);if(!Number.isFinite(n)||n<0)return;amounts[item.id]=Math.min(100000,n);slider.value=String(Math.min(item.max,amounts[item.id]));updateMass();queueRun();});
      num.addEventListener('blur',()=>{num.value=amounts[item.id];});
      row.append(label,amountWrap,slider);details.append(row);
    }
    wrapper.append(details);
  }
}
function renderSettings(){
 const wrapper=$('process-controls');
 const unitPicker=createElement('div',{class:'unit-picker'});
 unitPicker.append(createElement('span',{text:'Temperature controls · also shown in both units'}));
 const switcher=createElement('button',{class:'secondary unit-switch',type:'button',text:`Adjust in °${temperatureUnit} · switch to °${temperatureUnit==='C'?'F':'C'}`,'aria-label':'Switch temperature slider units'});
 switcher.addEventListener('click',()=>{temperatureUnit=temperatureUnit==='C'?'F':'C';wrapper.replaceChildren();renderSettings();renderResult();});
 unitPicker.append(switcher);wrapper.append(unitPicker);
 for(const [key,label,unit,min,max,step] of settingDefs){
    const temperature=temperatureKeys.has(key);
    const row=createElement('div',{class:'setting'});
    const head=createElement('div',{class:'setting-head'});
    const name=createElement('span',{text:label}),val=createElement('strong');
    const present=()=>{
      if(temperature){
        const active=temperatureUnit==='C'?settings[key]:cToF(settings[key]);
        const alternate=temperatureUnit==='C'?cToF(settings[key]):settings[key];
        val.textContent=`${fmt(active,1)} °${temperatureUnit} · ${fmt(alternate,1)} °${temperatureUnit==='C'?'F':'C'}`;
      }else val.textContent=`${fmt(settings[key],step<1?1:0)} ${unit}`;
    };
    present();head.append(name,val);
    const displayMin=temperature&&temperatureUnit==='F'?cToF(min):min;
    const displayMax=temperature&&temperatureUnit==='F'?cToF(max):max;
    const displayStep=temperature&&temperatureUnit==='F'?1:step;
    const displayValue=temperature&&temperatureUnit==='F'?cToF(settings[key]):settings[key];
    const slider=createElement('input',{type:'range',min:displayMin,max:displayMax,step:displayStep,value:displayValue,'aria-label':`${label} (${temperature?'°'+temperatureUnit:unit})`});
    slider.addEventListener('input',()=>{
      const selected=Number(slider.value);
      settings[key]=temperature&&temperatureUnit==='F'?fToC(selected):selected;
      present();queueRun();
    });
    row.append(head,slider);
    if(key==='thickness_mm')row.append(createElement('div',{class:'subtle',text:'For liquids, the starting depth in an open pan; for dough, the initial slab thickness before proof.'}));
    if(key==='minutes')row.append(createElement('div',{class:'subtle',text:'Extended to 24 hours for stress testing; extreme durations are not safe-cooking recommendations.'}));
    if(key==='oven_c')row.append(createElement('div',{class:'subtle',text:'Extended to 600°C / 1112°F. Beyond ordinary ovens, these are numerical stress tests only.'}));
    if(key==='steam_pct')row.append(createElement('div',{class:'subtle',text:'* Vapour pressure / water saturation at 100°C; not oven RH.'}));
    if(key==='proof_minutes')row.append(createElement('div',{class:'subtle',text:'Pre-bake fermentation. Empirical CO₂ rates only; no measured calibration.'}));
    wrapper.append(row);
 }
}
function queueRun(delay=360){
  if(!engineReady)return;
  setPlaying(false);
  clearTimeout(timer);requestId++;const thisId=requestId;$('run-indicator').textContent='CHANGED';
  $('save-a').disabled=true;$('save-b').disabled=true;$('scene-play').disabled=true;
  timer=setTimeout(()=>{$('run-indicator').textContent='SOLVING';$('run').disabled=true;worker.postMessage({id:thisId,payload:{catalog,...currentInputs()}});},delay);
}
function renderResult(){
  if(!last)return;
  const r=last.result,s=r.summary;
  const boxes=$('metrics').children;
  const vals=[[bothTemps(s.center_c),'Centre temperature'],[bothTemps(s.surface_c),'Surface temperature'],[fmt(s.mass_loss_pct,2)+' %','Of initial mass'],[fmt(s.browning_index,2),'Relative index · uncalibrated'],[fmt(s.rise_pct,2)+' %','Volume proxy · uncalibrated'],[fmt(s.co2_generated_g,3)+' g','CO₂ potential estimate']];
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
  const fluid=Boolean(s.liquid_mode);
  $('fluid-stats').hidden=!fluid;
  if(fluid){
    $('fluid-depth').textContent=fmt(s.liquid_depth_mm,2)+' mm';
    $('fluid-volume').textContent=fmt(s.liquid_volume_ml,1)+' mL';
    $('fluid-water').textContent=fmt(s.water_remaining_g,1)+' g';
    $('fluid-mode').textContent=s.residue_state||({aqueous:'Water-rich',biphasic:'Oil + water',syrup:'Sugar-rich',oil:'Oil-rich',suspension:'Fruit/grain slurry'})[s.liquid_mode]||s.liquid_mode;
    $('computed-note').textContent=`Initial ${fmt(s.total_g,1)} g → ${fmt(s.end_mass_g,1)} g remaining (water-only loss). Open pan: estimated footprint ${fmt(s.pan_area_cm2,1)} cm², starting depth ${fmt(r.settings.thickness_mm,1)} mm; remaining solids ${fmt(s.solids_fraction_pct,1)}% by mass. Water and heat use a well-mixed approximation; banana/oat hydration, crust darkening and scorching are uncalibrated indices.`;
  } else {
    $('computed-note').textContent=`Initial ${fmt(s.total_g,1)} g → estimated ${fmt(s.end_mass_g,1)} g water-loss-only; effective slab thickness ${fmt(s.thickness_mm_est,1)} mm. Proof-only rise ${fmt(s.proof_rise_pct,1)}%; retention factor ${fmt(s.gas_retention_factor,3)}. ${r.metadata.grid_cells} spatial cells, ${r.metadata.steps.toLocaleString()} steps. Gas chemistry is uncalibrated and CO₂ venting is excluded from mass totals.`;
  }
  $('warnings').replaceChildren(...r.warnings.map(text=>createElement('li',{text})));drawChart();updateScrub(100);renderComparison();
}
function svgEl(tag,attrs={}){const e=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,String(v));return e;}

function svgText(svg, attrs, value){const node=svgEl('text',attrs);node.textContent=value;svg.append(node);}
function blendColor(a,b,t){const pa=colorToRgb(a),pb=colorToRgb(b);return rgbToCss(pa.map((v,i)=>v+(pb[i]-v)*clamp(t,0,1)));}

function colorToRgb(color){
  if(color.startsWith('#')) return [parseInt(color.slice(1,3),16),parseInt(color.slice(3,5),16),parseInt(color.slice(5,7),16)];
  const nums=(color.match(/\d+/g)||[]).map(Number);return nums.length>=3?nums.slice(0,3):[180,180,180];
}
function rgbToCss(rgb){return `rgb(${rgb.map(v=>Math.round(clamp(v,0,255))).join(',')})`;}
function mixManyColor(weighted, fallback='#c9b28e'){
  let total=0, sum=[0,0,0];
  for(const [color,weight] of weighted){ if(!(weight>0)) continue; const rgb=colorToRgb(color); total+=weight; sum=sum.map((v,i)=>v+rgb[i]*weight); }
  if(total<=0) return fallback; return rgbToCss(sum.map(v=>v/total));
}
function toneColor(color,target,amt){return blendColor(color,target,clamp(amt,0,1));}
function mixtureVisual(frame,d){
  const weighted=[];
  for(const item of catalog){
    const amt=Number(amounts[item.id]||0); if(!(amt>0)) continue;
    const color=ingredientVisuals[item.id] || (item.category==='Liquids' ? '#b8d7ea' : item.category==='Fats' ? '#d2bb69' : '#ccb08a');
    const waterLeft=frame.water_remaining_g;
    const initWater=last.result.summary.total_g*last.result.summary.water_pct/100;
    const retainedRatio=Number.isFinite(waterLeft)?clamp(waterLeft/Math.max(1e-6,initWater),0,1):1;
    let weight=amt*(1-Number(item.water||0)*(1-retainedRatio));
    if(item.id==='water') weight*=0.55;
    if(item.id==='olive_oil') weight*=1.15;
    if(item.id==='salt') weight*=0.55;
    weighted.push([color, weight]);
  }
  const raw = mixManyColor(weighted, '#c9b28e');
  const dairyShare = (ingredientAmount('milk')+ingredientAmount('butter')*0.25)/Math.max(1,last.result.summary.total_g||1);
  const waterShare = ingredientAmount('water')/Math.max(1,last.result.summary.total_g||1);
  const oilShare = ingredientAmount('olive_oil')/Math.max(1,last.result.summary.total_g||1);
  const sugarShare=(ingredientAmount('sugar')+ingredientAmount('honey'))/Math.max(1,last.result.summary.total_g||1);
  let interior=raw;
  if(d.liquidish && waterShare>0.55) interior=toneColor(raw,'#83c8ff',0.24+waterShare*0.16);
  if(d.liquidish && dairyShare>0.08) interior=toneColor(interior,'#f1efe5',0.20+Math.min(.24,dairyShare*0.9));
  if(oilShare>0.45) interior=toneColor(interior,'#b7ab59',0.28);
  if(sugarShare>0.45 && d.liquidish) interior=toneColor(interior,'#c37d2e',0.32);
  const heatedMilk=clamp((frame.milk_skin_index_pct||0)/100,0,1);
  const heatedSyrup=clamp((frame.syrup_thickening_index_pct||0)/100,0,1);
  if(d.liquidMode==='aqueous' && dairyShare>.1) interior=toneColor(interior,'#d3be91',heatedMilk*0.30);
  if(d.sugary) interior=toneColor(interior,'#ad632a',heatedSyrup*0.60);
  const heatAmt=d.liquidMode?clamp(d.brown/100,0,1):clamp((d.brown/100)+(d.surface-125)/170,0,1);
  const top=d.liquidish ? toneColor(interior,'#fff6da',0.10+heatedMilk*0.36) : toneColor(interior, d.burnt ? '#23120c' : '#8a532f', heatAmt*0.86);
  const side=d.liquidish ? toneColor(interior,'#1b2430',0.08) : toneColor(interior,'#271810',heatAmt*0.67);
  return {base:interior, top, side, glaze:toneColor(top,'#fff9e6',0.28), shadow:toneColor(side,'#1a1110',0.35)};
}
function ingredientAmount(id){return Number(amounts[id]||0);} 
function totalFlourMass(){return ingredientAmount('bread_flour')+ingredientAmount('ap_flour')+ingredientAmount('whole_wheat_flour')+ingredientAmount('rye_flour')+ingredientAmount('rice_flour')+ingredientAmount('cornstarch')+ingredientAmount('potato_starch')+ingredientAmount('cocoa_powder')*0.5;}
function visualDescriptor(frame){
  const s=last.result.summary;
  const total=Math.max(1,s.total_g||1), flour=Math.max(1,totalFlourMass());
  const water=s.water_pct/100, fat=s.fat_pct/100, protein=s.protein_pct/100, sugar=s.sugar_pct/100, starch=s.starch_pct/100;
  const saltRatio=ingredientAmount('salt')/total, yeastRatio=(ingredientAmount('instant_yeast')+ingredientAmount('active_dry_yeast'))/flour;
  const bpRatio=(ingredientAmount('baking_powder')+ingredientAmount('baking_soda'))/flour;
  const rise=frame.rise_pct||0, brown=frame.browning_index||0, center=frame.center_c||0, surface=frame.surface_c||0, massLoss=frame.mass_loss_pct||0;
  const wetness=clamp((water-0.18)/0.45,0,1), richness=clamp((fat*0.9+sugar*0.65),0,1), dryness=clamp(1-wetness*0.9-massLoss/40,0,1);
  const liquidMode=s.liquid_mode||null;
  const residueState=frame.residue_state||'';
  const isResidue=Boolean(liquidMode && ['paste','concentrate','dry residue','scorched'].includes(residueState));
  const isDryResidue=Boolean(liquidMode && ['dry residue','scorched'].includes(residueState));
  const liquidish=liquidMode ? !isResidue&&liquidMode!=='oil' : (wetness>0.72 && protein<0.1 && starch<0.3);
  const oily=liquidMode ? liquidMode==='oil' : fat>0.50;
  const sugary=liquidMode ? liquidMode==='syrup' : (sugar>0.58 && water>0.10 && fat<0.4);
  const biphasic = liquidMode==='biphasic';
  const powdery = (!liquidMode && water<0.12 && rise<8 && !oily && !sugary) || (isDryResidue && ingredientAmount('oats')>0 && !oily);
  const salty = saltRatio>0.16; 
  const cakey = richness>0.16 && bpRatio>0.012 && protein<0.12;
  const domed = rise>12 && !liquidish;
  const overexpanded = rise>60 && (protein<0.11 || wetness>0.68);
  const collapsed = overexpanded && (surface>165 || frame.co2_retained_g < frame.co2_generated_g*0.55 || massLoss>12);
  const cracked = (massLoss>8 && surface>135 && !liquidish) || powdery;
  const burnt = liquidMode ? brown>78 : brown>78 || surface>215;
  const underbaked = center<86 && surface<140;
  const boiling = liquidish && frame.water_remaining_g>0 && surface>=96;
  let label='Setting loaf';
  if(oily) label = 'Oil-rich pool (smoke not modeled)';
  else if(biphasic) label = 'Oil + water: separating layers';
  else if(sugary) label = 'Sugar-rich syrup / mass (unsupported)';
  else if(liquidish) label = boiling ? 'Boiling open-pan liquid' : 'Open-pan liquid';
  else if(salty) label = 'Salt-heavy matrix (unsupported)';
  else if(powdery) label='Dry, crumbly mass';
  else if(collapsed) label='Overexpanded then sagging';
  else if(burnt) label='Aggressive browning';
  else if(cakey) label='Cake-like crumb setting';
  else if(domed) label='Rising and doming';
  else if(underbaked) label='Early bake / structure not set';
  if(fat>0.32 && !oily && !liquidish) label += ' · fatty';
  if(liquidMode && frame.water_remaining_g===0 && s.water_pct>0){
    if(fat>0.10) label='Water gone · oil remains';
    else if(s.sugar_pct>15) label='Water gone · sugar residue';
    else if(Number(frame.liquid_depth_mm||0)<0.02) label='Water evaporated · empty pan';
    else label='Water gone · concentrated residue';
  }
  if(liquidMode==='suspension'){
    const material=ingredientAmount('banana')>ingredientAmount('oats')?'banana':'oats';
    label=residueState==='scorched'?`${material} · scorched residue`:residueState==='dry residue'?`${material} · drying/toasting`:residueState==='paste'?`${material} · thickening paste`:`${material} · soaking slurry`;
  }
  let note=`Surface ${bothTemps(surface)} · centre ${bothTemps(center)} · water loss ${fmt(massLoss,1)}%`;
  if(oily) note='Oil-rich pan: temperature is modeled; oil smoking, ignition and oxidation are not.';
  else if(biphasic) note='Added oil may separate and float over the aqueous phase. Layer timing is illustrative.';
  else if(sugary) note='The sugar mass fraction rises as water evaporates. Viscosity, crystallization and colour remain illustrative.';
  else if(salty) note='Large salt fraction: dissolution/crystal behaviour is unsupported; no loaf shape prediction.';
  else if(collapsed) note='Gas generation outruns structure in this proxy; sagging is illustrative only.';
  else if(liquidMode==='suspension') note=`${residueState}: remaining solids ${fmt(frame.solids_fraction_pct,1)}%, residue browning ${fmt(frame.residue_browning_index,1)}% (experimental).`;
  else if(liquidish) note='High free-water formula: the viewport stays shallow and glossy, and the pool visibly recedes as evaporation increases.';
  else if(powdery) note='Low-water extreme: poor cohesion, little expansion and a rough, cracked top.';
  else if(burnt) note='The browning index is high, so the viewport darkens and exaggerates crust contrast.';
  return {water,fat,protein,sugar,starch,wetness,richness,dryness,liquidMode,residueState,isResidue,isDryResidue,biphasic,liquidish,powdery,oily,sugary,salty,cakey,domed,overexpanded,collapsed,cracked,burnt,underbaked,boiling,label,note,saltRatio,yeastRatio,bpRatio,rise,brown,surface,center,massLoss};
}
function drawBakeScene(frame){
  const svg=$('bake-scene'); if(!svg || !last) return; svg.replaceChildren();
  const compactScene=window.matchMedia('(max-width:920px)').matches;
  svg.setAttribute('viewBox',compactScene?'115 75 530 200':'0 0 760 300');
  const d=visualDescriptor(frame), s=last.result.summary, t=last.result.timeline.at(-1).minute || 1;
  $('scene-state').textContent=d.label; $('scene-caption').textContent=d.note;
  const w=760,h=300, panL=154, panR=568, panTop=170, panDepth=48, panHeight=78;
  // Deliberately non-physical shading for the 2.5D projection. The underlying
  // kinetics remain in Python; these gradients are not synthetic solver fields.
  const defs=svgEl('defs');
  const addGradient=(id,stops)=>{const gradient=svgEl('linearGradient',{id,x1:'0%',y1:'0%',x2:'25%',y2:'100%'});for(const [offset,color,opacity] of stops){gradient.append(svgEl('stop',{offset,'stop-color':color,'stop-opacity':opacity}));}defs.append(gradient);};
  addGradient('scenePanGradient',[['0%','#718890',1],['55%','#4f646c',1],['100%','#2e4148',1]]);
  addGradient('scenePanSideGradient',[['0%','#71828a',1],['100%','#23363c',1]]);
  svg.append(defs);
  const progress=clamp(frame.minute/Math.max(1,last.result.settings.minutes),0,1);
  const ovenGlow=clamp((last.result.settings.oven_c-70)/260,0,1);
  svg.append(svgEl('rect',{x:0,y:0,width:w,height:h,fill:'#0e161a'}));
  svg.append(svgEl('ellipse',{cx:380,cy:46,rx:228,ry:34,fill:`rgba(245,205,116,${0.08+0.15*ovenGlow})`}));
  svg.append(svgEl('rect',{x:42,y:32,width:676,height:230,rx:18,fill:'rgba(24,37,42,.94)',stroke:'#34474d','stroke-width':2}));
  svg.append(svgEl('rect',{x:72,y:61,width:616,height:168,rx:10,fill:'rgba(9,15,18,.98)',stroke:'#223139','stroke-width':1.2}));
  svg.append(svgEl('ellipse',{cx:380,cy:236,rx:242,ry:18,class:'scene-shadow'}));
  const rackY=220;
  svg.append(svgEl('line',{x1:120,y1:rackY,x2:640,y2:rackY,stroke:'#53686d','stroke-width':3,'stroke-linecap':'round'}));
  for(let i=0;i<7;i++) svg.append(svgEl('line',{x1:130+i*78,y1:rackY-5,x2:150+i*78,y2:rackY+5,stroke:'#495b61','stroke-width':2,'stroke-linecap':'round'}));
  const fillBase=clamp(0.10+0.72*last.result.settings.thickness_mm/160,0.16,0.84);
  const riseFactor=frame.thickness_mm_est/Math.max(4,last.result.settings.thickness_mm);
  let topY=panTop+panHeight*(1-fillBase*clamp(riseFactor,0.35,2.6));
  topY=clamp(topY,85,panTop+panHeight-8);
  let crown=clamp((d.rise*0.36)+(d.cakey?8:0)+(d.liquidish?-10:0)-(d.powdery?6:0),0,50);
  const visual=mixtureVisual(frame,d);
  if(d.collapsed) crown*=0.22;
  if(d.liquidMode || d.oily || d.sugary) crown=0;
  const spill=Math.max(0, 128-topY);
  const crust=d.liquidMode ? (d.liquidish?toneColor(visual.top,'#fefefe',0.05):toneColor(visual.top, d.burnt?'#1b0e09':'#8b512e',clamp(d.brown/100,0,1)*0.92)) : toneColor(visual.top, d.burnt?'#261713':'#8f5831',clamp((d.brown/100)+(d.surface-120)/150,0,1)*0.45);
  const crumb=(d.oily?toneColor(visual.base,'#715428',0.18):d.liquidish?toneColor(visual.base,'#ece1bf',0.04):d.sugary?toneColor(visual.base,'#8a552b',0.12):toneColor(visual.base,'#c79162', clamp((d.brown/140)+d.fat*0.55,0,1)*0.25));
  const panTopFace=`${panL},${panTop} ${panR},${panTop} ${panR+panDepth},${panTop-panDepth} ${panL+panDepth},${panTop-panDepth}`;
  const panFront=`${panL},${panTop} ${panR},${panTop} ${panR},${panTop+panHeight} ${panL},${panTop+panHeight}`;
  const panSide=`${panR},${panTop} ${panR+panDepth},${panTop-panDepth} ${panR+panDepth},${panTop+panHeight-panDepth} ${panR},${panTop+panHeight}`;
  svg.append(svgEl('polygon',{points:panTopFace,class:'scene-pan-metal scene-outline'}));
  svg.append(svgEl('polygon',{points:panSide,fill:'url(#scenePanSideGradient)',class:'scene-outline'}));
  svg.append(svgEl('polygon',{points:panFront,fill:'url(#scenePanGradient)',class:'scene-outline'}));
  svg.append(svgEl('line',{x1:panL+12,y1:panTop-panDepth+4,x2:panR+panDepth-12,y2:panTop-panDepth+4,class:'scene-pan-rim scene-outline'}));
  const leftInner=panL+18,rightInner=panR-18, backLift=panDepth-8;
  if(d.liquidMode){
    // Absolute starting depth drives pan footprint in Python. The display
    // uses the *same* remaining-depth ratio; no minimum liquid-height floor.
    const depthRatio=clamp(Number(frame.liquid_depth_mm||0)/Math.max(1e-9,last.result.settings.thickness_mm),0,1);
    const drawFill=fillBase*depthRatio;
    topY=panTop+panHeight-9-(panHeight-8)*drawFill;
  }
  const topBase = topY;
  let cp1=leftInner+(rightInner-leftInner)*0.27, cp2=leftInner+(rightInner-leftInner)*0.73;
  let sag = d.collapsed ? 18+0.18*d.rise : 0;
  let ripple = d.liquidish ? 4+2*Math.sin(frame.minute*0.35) : 0;
  let topPath=`M ${leftInner} ${topBase} C ${cp1} ${topBase-crown+ripple} ${cp2} ${topBase-crown+ripple+sag} ${rightInner} ${topBase}`;
  if(d.liquidish || d.oily || (d.sugary&&!d.isResidue)) topPath=`M ${leftInner} ${topBase} C ${cp1} ${topBase+ripple} ${cp2} ${topBase-ripple} ${rightInner} ${topBase}`;
  if(d.isDryResidue || d.powdery) topPath=`M ${leftInner} ${topBase+3} C ${cp1} ${topBase-crown*0.2-4} ${cp2} ${topBase-crown*0.15+9} ${rightInner} ${topBase+1}`;
  const frontPath=`${topPath} L ${rightInner} ${panTop+panHeight-9} L ${leftInner} ${panTop+panHeight-9} Z`;
  const backPath=`M ${leftInner+backLift} ${topBase-backLift} C ${cp1+backLift} ${topBase-crown+ripple-backLift} ${cp2+backLift} ${topBase-crown+ripple+sag-backLift} ${rightInner+backLift} ${topBase-backLift} L ${rightInner+backLift} ${panTop+panHeight-9-backLift} L ${leftInner+backLift} ${panTop+panHeight-9-backLift} Z`;
  const containsMaterial = !d.liquidMode || Number(frame.liquid_depth_mm||0)>0.01;
  if(containsMaterial){
  svg.append(svgEl('path',{d:backPath,fill:blendColor(crumb,'#ffffff',0.12),opacity:0.42}));
  svg.append(svgEl('path',{d:frontPath,fill:crumb,class:'scene-outline'}));
  const crustTop = `${topPath} L ${rightInner+backLift} ${topBase-backLift} C ${cp2+backLift} ${topBase-crown+ripple+sag-backLift} ${cp1+backLift} ${topBase-crown+ripple-backLift} ${leftInner+backLift} ${topBase-backLift} Z`;
  svg.append(svgEl('path',{d:crustTop,fill:crust,class:'scene-outline'}));
  if(d.liquidMode){
    // These visual cues are qualitative and do NOT model fluid dynamics.
    const phaseFraction=clamp(Number(frame.separation_index_pct||0)/100,0,1);
    const liquidDepth=Math.max(1e-9,Number(frame.liquid_depth_mm||0));
    const oilFrac=clamp(Number(frame.oil_layer_mm||0)/liquidDepth,0,1);
    if(d.biphasic && oilFrac>0.005){
      const oilTint=ingredientVisuals.olive_oil;
      const bandPx=(panTop+panHeight-9-topBase)*oilFrac;
      const bandTop=Math.max(topBase,panTop+panHeight-9-bandPx);
      svg.append(svgEl('path',{d:`M ${leftInner} ${topBase} Q ${(leftInner+rightInner)/2} ${topBase-2} ${rightInner} ${topBase} L ${rightInner} ${bandTop+bandPx} L ${leftInner} ${bandTop+bandPx} Z`,fill:oilTint,opacity:clamp(phaseFraction*0.7,0,0.7)}));
      svg.append(svgEl('path',{d:crustTop,fill:oilTint,opacity:clamp(phaseFraction*0.82,0,0.82)}));
    }
    const skin=clamp(Number(frame.milk_skin_index_pct||0)/100,0,1);
    if(skin>0.08 && !d.oily){
      svg.append(svgEl('path',{d:crustTop,fill:'#f4e3bb',opacity:0.25*skin}));
      for(let i=0;i<4;i++){
        const x=leftInner+30+i*79;
        svg.append(svgEl('path',{d:`M ${x} ${topBase-9} q 9 -4 17 -1 q 8 3 16 -2`,fill:'none',stroke:'#e8cda0','stroke-width':1.4,opacity:0.70*skin}));
      }
    }
    if(d.isResidue){
      const roughness=clamp((frame.solids_fraction_pct||0)/100,0,1);
      const darkness=clamp((frame.residue_browning_index||0)/100,0,1);
      const dots=Math.round(12+roughness*25);
      for(let i=0;i<dots;i++){
        const x=leftInner+14+(i*67)%Math.max(80,rightInner-leftInner-28);
        const y=topBase-4-(i*13)%Math.max(5,Math.round(8+roughness*13));
        svg.append(svgEl('ellipse',{cx:x,cy:y,rx:2.1+(i%3),ry:1.0+(i%2),fill:darkness>.7?'#120a08':'#6c4e2b',opacity:0.12+roughness*0.34}));
      }
    }
    const thick=clamp(Number(frame.syrup_thickening_index_pct||0)/100,0,1);
    if(thick>0.04){
      for(let i=0;i<5;i++){
        const x=leftInner+26+i*68;
        svg.append(svgEl('path',{d:`M ${x} ${topBase-6} q 12 ${-5-4*thick} 24 -1`,fill:'none',stroke:'#f6d7a0','stroke-width':1+thick*2.4,opacity:0.18+thick*0.45}));
      }
    }
  }
  } // containsMaterial

  if(spill>0 && !d.powdery && !d.liquidish && !d.oily && !d.sugary){
    const muffin=`M ${leftInner-10} ${topBase+5} C ${cp1-35} ${topBase-crown-10} ${cp2+35} ${topBase-crown-6+sag} ${rightInner+10} ${topBase+6} L ${rightInner+6} ${topBase+14} C ${cp2+16} ${topBase-crown*0.45+sag+10} ${cp1-16} ${topBase-crown*0.55+12} ${leftInner-6} ${topBase+13} Z`;
    svg.append(svgEl('path',{d:muffin,fill:blendColor(crust, crumb, 0.45),opacity:0.92,class:'scene-outline'}));
  }
  // The only spatially resolved state available is center→surface. Show a
  // deliberately stylized small window into this calculated temperature field;
  // this is NOT a 3D finite element solution or a predicted crumb pattern.
  if(!d.liquidish && !d.oily && !d.sugary && !d.powdery && frame.temp_profile?.length>1){
    const prof=frame.temp_profile, waterProf=frame.water_profile||[];
    const bandCount=Math.min(6,prof.length);
    for(let i=0;i<bandCount;i++){
      const j=Math.round(i*(prof.length-1)/(bandCount-1));
      const tt=clamp((prof[j]-35)/120,0,1);
      const mo=clamp((waterProf[j]||0)/65,0,1);
      const bx=leftInner+13+i*17;
      const by=panTop+panHeight-16-i*2.2;
      svg.append(svgEl('rect',{x:bx,y:by,width:12,height:7,rx:2,fill:blendColor('#f0d9b3','#aa623b',tt),opacity:0.15+0.34*(1-mo)}));
    }
  }
  // Deterministic granular details; the texture is aesthetic and not a pore simulation.
  if(d.powdery || d.salty){
    for(let i=0;i<38;i++){
      const x=leftInner+15+(i*67)%Math.max(70,rightInner-leftInner-30);
      const y=topBase-5-(i*19)%Math.max(7,Math.round(crown+16));
      svg.append(svgEl('circle',{cx:x,cy:y,r:d.salty?1.6:2.5,fill:d.salty?'#f2e9d8':'#ead7b9',opacity:.38}));
    }
  }
  if(d.sugary){
    for(let i=0;i<8;i++){
      const x=leftInner+18+i*45, y=topBase-2-(i%3)*2;
      svg.append(svgEl('path',{d:`M ${x} ${y} q 11 -8 24 -2`,class:'scene-gloss','stroke-width':2}));
    }
  }
  if(d.oily){
    svg.append(svgEl('path',{d:`M ${leftInner+8} ${topBase+2} Q ${leftInner+80} ${topBase-15} ${rightInner-10} ${topBase+1}`,fill:'none',stroke:visual.glaze,'stroke-opacity':.52,'stroke-width':3}));
  }
  if(d.oily){
    for(let i=0;i<4;i++) svg.append(svgEl('path',{d:`M ${leftInner+35+i*78} ${topBase+4+(i%2)*2} q 18 -4 36 0`,stroke:visual.glaze,fill:'none','stroke-width':3,'stroke-linecap':'round',opacity:'0.9'}));
  }
  if(d.cracked && !d.liquidMode){
    const crackCount=d.powdery?5:3;
    for(let i=0;i<crackCount;i++){
      const x=leftInner+50+i*(rightInner-leftInner-100)/Math.max(1,crackCount-1);const y=topBase-crown*0.35 + (i%2)*6;
      svg.append(svgEl('path',{d:`M ${x} ${y} q -8 7 -14 16 q 10 6 4 15`,class:'scene-crack','stroke-width':2.2}));
    }
  }
  if(!d.liquidMode && (d.cakey || (d.rise>18 && !d.liquidish))){
    const bubbleCount=Math.round(clamp(d.rise/16 + (d.cakey?2:0),2,8));
    for(let i=0;i<bubbleCount;i++){
      const bx=leftInner+35+(i*61)%Math.max(80,(rightInner-leftInner-70)); const by=panTop+panHeight-22-((i*19)%36); const rr=clamp(3 + d.rise*0.04 + (i%3),2,8);
      svg.append(svgEl('circle',{cx:bx,cy:by,r:rr,class:'scene-bubble'}));
    }
  }
  if((d.liquidMode && frame.water_remaining_g>0 && d.massLoss>0.02) || (!d.liquidMode && (d.liquidish || d.massLoss>0.5))){
    const steamN = Math.round(clamp(1 + d.massLoss/2 + (d.boiling?3:0),1,8));
    for(let i=0;i<steamN;i++){
      const sx=260+i*34+(i%2)*18, sy=topBase-18-(i%3)*3;
      svg.append(svgEl('path',{d:`M ${sx} ${sy} C ${sx-8} ${sy-18} ${sx+10} ${sy-28} ${sx+2} ${sy-44} C ${sx-10} ${sy-56} ${sx+18} ${sy-68} ${sx+8} ${sy-84}`,class:'scene-steam','stroke-width':2.3-(i%2)*0.4}));
    }
  }
  if(d.boiling && frame.water_remaining_g>0){
    for(let i=0;i<4;i++){
      const bx=leftInner+60+i*82, by=topBase-2+(i%2)*2;
      svg.append(svgEl('ellipse',{cx:bx,cy:by,rx:5+i%3,ry:2.5,fill:'rgba(255,255,255,.25)'}));
    }
  }
  if(!compactScene){
  svgText(svg,{x:97,y:84,class:'scene-label'},'ANGLED PAN · ILLUSTRATIVE');
  svgText(svg,{x:97,y:101,class:'scene-subtle'},`t = ${fmt(frame.minute,1)} min · oven ${bothTemps(last.result.settings.oven_c)}`);
  svgText(svg,{x:97,y:118,class:'scene-subtle'},`effective thickness ${fmt(frame.thickness_mm_est,1)} mm · rise ${fmt(frame.rise_pct,1)}%`);
  if(last.result.warnings.length){
    svgText(svg,{x:540,y:84,class:'scene-warning','text-anchor':'start'},'⚠ model boundary');
    svgText(svg,{x:540,y:101,class:'scene-subtle'},last.result.warnings[0].slice(0,42));
  }
  }
}
function drawChart(){
 const svg=$('chart');svg.replaceChildren();if(!last)return;
 const t=last.result.timeline;const maxT=Math.max(1,t.at(-1).minute);const metric=$('metric').value;
 let lines;
 if(metric==='temp')lines=[['center_c','Center (°'+temperatureUnit+')',colors.center],['mid_c','Mid-depth (°'+temperatureUnit+')',colors.mid],['surface_c','Surface (°'+temperatureUnit+')',colors.surface]];
 else if(metric==='moisture')lines=[['center_moisture_pct','Center',colors.center],['surface_moisture_pct','Surface',colors.blue||colors.mid]];
 else if(metric==='mass')lines=[['mass_loss_pct','Water lost',colors.surface]];
 else if(metric==='rise')lines=[['rise_pct','Estimated expansion',colors.center]];
 else if(metric==='gas')lines=[['co2_generated_g','CO₂ generated, g',colors.surface],['co2_retained_g','CO₂ retained, g',colors.mid]];
 else if(['liquid','concentration','hydration','residue'].includes(metric)){
   if(!last.result.summary.liquid_mode){svgText(svg,{x:380,y:150,'text-anchor':'middle',fill:'#9cafa9','font-size':16},'Fluid-only measurement; select a liquid preset.');$('legend').replaceChildren();return;}
   lines=metric==='liquid'?[['liquid_depth_mm','Depth · mm',colors.mid]]:metric==='concentration'?[['sugar_concentration_pct','Sugar fraction · %',colors.surface]]:metric==='hydration'?[['oat_hydration_index_pct','Hydration proxy · %',colors.center]]:[['residue_browning_index','Residue browning · %',colors.surface]];
 }
 else if(metric==='change')lines=[['starch_progress_pct','Gelatinization proxy',colors.center],['protein_progress_pct','Protein proxy',colors.mid]];
 else lines=[['browning_index','Browning index',colors.surface]];
 const displayed=(key,raw)=>metric==='temp'&&temperatureUnit==='F'?cToF(raw):raw;
 const all=lines.flatMap(([key])=>t.map(row=>displayed(key,row[key])));let ymax=Math.max(1,...all);let ymin=Math.min(0,...all);
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
 for(const [key,name,color] of lines){const d=t.map((row,i)=>(i?'L':'M')+(left+w*row.minute/maxT).toFixed(2)+' '+(top+h*(1-(displayed(key,row[key])-ymin)/(ymax-ymin))).toFixed(2)).join(' ');
 svg.append(svgEl('path',{d,fill:'none',stroke:color,'stroke-width':2.7,'stroke-linejoin':'round'}));}
 const leg=$('legend');leg.replaceChildren();for(const [,name,color] of lines){const item=createElement('span');const sw=createElement('i');sw.style.background=color;item.append(sw,name);leg.append(item);}
}

function setPlaying(active){
  playing=active;
  if(!active && playHandle){cancelAnimationFrame(playHandle);playHandle=0;}
  const button=$('scene-play');
  button.textContent=active?'Ⅱ Pause':'▶ Replay bake';
  button.setAttribute('aria-label',active?'Pause bake animation':'Play bake animation');
}
function stepPlayback(now){
  if(!playing||!last)return;
  const speed=Number($('scene-speed').value)||1;
  const position=clamp(playOrigin+(now-playStart)*100*speed/BAKE_PLAY_DURATION,0,100);
  updateScrub(position);
  if(position>=100){setPlaying(false);return;}
  playHandle=requestAnimationFrame(stepPlayback);
}
function startPlayback(){
  if(!last)return;
  if(playing){setPlaying(false);return;}
  if(playValue>99.8)updateScrub(0);
  playOrigin=playValue;
  playStart=performance.now();
  setPlaying(true);
  playHandle=requestAnimationFrame(stepPlayback);
}

function updateScrub(val){if(!last)return;
 playValue=clamp(Number(val),0,100);
 $('scrub').disabled=false;$('scrub').value=playValue;
 $('scrub-scene').disabled=false;$('scrub-scene').value=playValue;
 const frames=last.result.timeline;const idx=Math.min(frames.length-1,Math.round((frames.length-1)*val/100));const frame=frames[idx];
 $('scrub-label').textContent=`${fmt(frame.minute,1)} min / ${fmt(last.result.settings.minutes,1)} min`;
 $('scene-clock').textContent=`${fmt(frame.minute,1)} / ${fmt(last.result.settings.minutes,1)} min`;
 const materialNote=$('scene-material-note');
 if(last.result.summary.liquid_mode){
   materialNote.hidden=false;
   const sugar=Number(frame.sugar_concentration_pct||0);
   const details=[`${fmt(frame.liquid_depth_mm,2)} mm deep`,`${fmt(frame.liquid_volume_ml,1)} mL left`];
   if(Number(frame.oil_layer_mm||0)>0.1)details.push(`oil layer ~${fmt(frame.oil_layer_mm,1)} mm`);
   if(last.result.summary.liquid_mode==='suspension'){
     details.push(`${frame.residue_state||'slurry'}`);
     details.push(`solids ${fmt(frame.solids_fraction_pct,1)}%`);
     details.push(`darkening ${fmt(frame.residue_browning_index,1)} / 100 (estimated)`);
   }else if(sugar>25)details.push(`sugar ${fmt(sugar,1)}% of sugar+water`);
   materialNote.textContent=details.join(' · ');
   // Colour swatch makes a sub-millimetre residue visible without falsely
   // inflating its calculated height in the pan drawing.
   materialNote.style.borderLeft=`7px solid ${mixtureVisual(frame,visualDescriptor(frame)).top}`;
 }else{materialNote.hidden=true;materialNote.textContent='';}
 drawBakeScene(frame);
 const svg=$('cross-section');svg.replaceChildren();
 const temp=frame.temp_profile||last.result.profile.temp_c;const mn=Math.min(last.result.settings.initial_c,last.result.settings.oven_c,0);const mx=Math.max(last.result.settings.initial_c,last.result.settings.oven_c,100);const n=temp.length;
 for(let i=0;i<n;i++){
   const p=Math.max(0,Math.min(1,(temp[i]-mn)/Math.max(1,mx-mn)));
   const rgb=[Math.round(35+220*p),Math.round(101+120*p-100*p*p),Math.round(194-164*p)];
   svg.append(svgEl('rect',{x:10+i*740/n,y:10,width:740/n+1,height:90,fill:`rgb(${rgb.join(',')})`}));
 }
 svg.append(svgEl('rect',{x:10,y:10,width:740,height:90,rx:3,fill:'none',stroke:'#69807a','stroke-width':1}));
 [['CENTER',frame.center_c,14],['SURFACE',frame.surface_c,620]].forEach((a,i)=>{let text=svgEl('text',{x:a[2],y:119,fill:'#9cafa9','font-size':11});text.textContent=`${a[0]} ${fmt(a[1],1)} °C / ${fmt(cToF(a[1]),1)} °F`;svg.append(text);});
}
function renderComparison(){const a=snapshots.A,b=snapshots.B;if(!a&&!b){$('comparison').textContent='Save snapshots using A and B. The numbers are independent model runs, not measurements.';return;}
 const rows=[['Oven (°C)',x=>x.inputs.settings.oven_c],['Bake (min)',x=>x.inputs.settings.minutes],['Proof (min)',x=>x.inputs.settings.proof_minutes],['Water in mix (%)',x=>x.result.summary.water_pct],['Center (°C)',x=>x.result.summary.center_c],['Surface (°C)',x=>x.result.summary.surface_c],['Mass lost (%)',x=>x.result.summary.mass_loss_pct],['Liquid depth (mm)',x=>x.result.summary.liquid_depth_mm??null],['Remaining volume (mL)',x=>x.result.summary.liquid_volume_ml??null],['Water remaining (g)',x=>x.result.summary.water_remaining_g??null],['Rise proxy (%)',x=>x.result.summary.rise_pct],['CO₂ formed (g)',x=>x.result.summary.co2_generated_g],['Browning index',x=>x.result.summary.browning_index],['Residue browning proxy',x=>x.result.summary.residue_browning_index??null]];
 const table=createElement('table');const head=createElement('tr');['Metric','A','B','Δ B–A'].forEach(x=>head.append(createElement('th',{text:x})));table.append(head);
 for(const [label,get] of rows){const tr=createElement('tr');tr.append(createElement('td',{text:label}));const av=a?get(a):null,bv=b?get(b):null;[av,bv,av!=null&&bv!=null?bv-av:null].forEach(x=>tr.append(createElement('td',{text:x==null?'—':fmt(x,2)})));table.append(tr);}
 $('comparison').replaceChildren(table);
}
function download(name,text,contentType){const blob=new Blob([text],{type:contentType});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function exportCSV(){if(!last)return;const arr=last.result.timeline;const keys=['minute','center_c','mid_c','surface_c','mass_loss_pct','center_moisture_pct','surface_moisture_pct','starch_progress_pct','protein_progress_pct','browning_index','rise_pct','thickness_mm_est','co2_generated_g','co2_retained_g','liquid_depth_mm','liquid_volume_ml','water_remaining_g','sugar_concentration_pct','milk_skin_index_pct','oil_layer_mm','separation_index_pct','solids_fraction_pct','free_water_g','bound_water_proxy_g','oat_hydration_index_pct','residue_browning_index','residue_state'];const rows=[keys.join(','),...arr.map(o=>keys.map(k=>o[k]??'').join(','))];download('bakelab-timeseries.csv',rows.join('\n'),'text/csv');}
function drawPlaceholderScene(){const svg=$('bake-scene'); if(!svg) return; svg.setAttribute('viewBox',window.matchMedia('(max-width:920px)').matches?'115 75 530 200':'0 0 760 300'); svg.replaceChildren(); svg.append(svgEl('rect',{x:0,y:0,width:760,height:300,fill:'#10181c'})); svg.append(svgEl('rect',{x:52,y:36,width:656,height:228,rx:18,fill:'rgba(18,27,31,.98)',stroke:'#34474d','stroke-width':2})); svgText(svg,{x:380,y:138,'text-anchor':'middle',class:'scene-label'},'Run a formula to render the bake viewport'); svgText(svg,{x:380,y:160,'text-anchor':'middle',class:'scene-subtle'},'The pan, loaf/batter shape, crust colour and warning behaviour update with the simulation.');}


// The bake scene lives outside the tabpanels and is never torn down or hidden.
function setupTabs(){
 const tabs=Array.from(document.querySelectorAll('[role="tab"][data-tab]'));
 const shell=document.querySelector('.lab-shell');
 function activate(id,focus=false){
   if(!tabs.some(tab=>tab.dataset.tab===id))return;
   for(const tab of tabs){
     const on=tab.dataset.tab===id;
     tab.setAttribute('aria-selected',String(on));
     tab.tabIndex=on?0:-1;
     const panel=$('panel-'+tab.dataset.tab);
     panel.hidden=!on;
     if(on&&focus)tab.focus({preventScroll:true});
   }
   // Switching from a long ingredients list to a short results panel should
   // reveal the top of the new panel, not leave the user below its content.
   const top=shell.getBoundingClientRect().top+window.scrollY;
   if(window.scrollY>top+8)window.scrollTo({top,behavior:'instant'});
 }
 tabs.forEach((tab,index)=>{
   tab.addEventListener('click',()=>activate(tab.dataset.tab));
   tab.addEventListener('keydown',event=>{
     let next=index;
     if(event.key==='ArrowRight')next=(index+1)%tabs.length;
     else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
     else if(event.key==='Home')next=0;
     else if(event.key==='End')next=tabs.length-1;
     else return;
     event.preventDefault();activate(tabs[next].dataset.tab,true);
   });
 });
 activate('ingredients');
}

async function init(){
 try {catalog=await fetch('./ingredients.json').then(r=>{if(!r.ok)throw Error('Cannot load ingredients.json');return r.json();});} catch(e){showError('Could not load ingredients. Serve with python -m http.server or GitHub Pages. '+e.message);return;}
 for(const item of catalog)amounts[item.id]=item.amount;
 setupTabs();renderIngredients();renderSettings();updateMass();drawPlaceholderScene();
 window.addEventListener('resize',()=>{if(last)updateScrub(playValue);else drawPlaceholderScene();});
 $('preset').addEventListener('change',e=>loadPreset(e.target.value));
 $('reset').addEventListener('click',()=>{settings={...defaults};$('process-controls').replaceChildren();renderSettings();$('preset').value='bread';loadPreset('bread');});
 $('run').addEventListener('click',()=>queueRun(0));
 $('metric').addEventListener('change',drawChart);
 $('scrub').addEventListener('input',e=>{setPlaying(false);updateScrub(Number(e.target.value));});
 $('scrub-scene').addEventListener('input',e=>{setPlaying(false);updateScrub(Number(e.target.value));});
 $('scene-play').addEventListener('click',startPlayback);
 $('scene-reset').addEventListener('click',()=>{setPlaying(false);updateScrub(0);});
 $('scene-speed').addEventListener('change',()=>{if(playing){playOrigin=playValue;playStart=performance.now();}});
 for(const k of ['A','B'])$('save-'+k.toLowerCase()).addEventListener('click',()=>{if(!last||renderedId!==requestId)return;snapshots[k]=structuredClone(last);renderComparison();});
 $('clear-compare').addEventListener('click',()=>{snapshots={A:null,B:null};renderComparison();});
 $('export').addEventListener('click',()=>{if(last)download('bakelab-run.json',JSON.stringify(last,null,2),'application/json');});
 $('csv').addEventListener('click',exportCSV);
}
init();
