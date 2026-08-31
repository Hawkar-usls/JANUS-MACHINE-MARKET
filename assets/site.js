const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const state={catalog:[],loadout:[],bet:10,balance:100,spinning:false};
const iconMap={search_api:'⌕',data_discovery:'◇',research_synthesis:'✦',archive_research:'▣',repository_analysis:'⌘',research_job:'§',inference:'◈',compute:'⚙',technology_license:'☉'};
const uiConfig={
 'JANUS.SEARCH':{modes:['FAST','STANDARD','DEEP'],unit:'requests'},
 'JANUS.DATASET_SCOUT':{modes:['DISCOVERY','LICENSE-DEEP'],unit:'jobs'},
 'JANUS.EVIDENCE_PACK':{modes:['STANDARD','DEEP'],unit:'packs'},
 'JANUS.ARCHIVE_SCAN':{modes:['OPEN-ARCHIVE','PUBLIC-MIX'],unit:'scans'},
 'JANUS.REPO_AUDIT':{modes:['ARCHITECTURE','CLAIMS','DEPENDENCIES'],unit:'audits'},
 'JANUS.RESEARCH_JOB':{modes:['SHORT','STANDARD','DEEP'],unit:'jobs'},
 'HELIOS.PILOT':{modes:['90-DAY-PILOT'],unit:'pilots'},
 'JANUS.INFERENCE':{modes:['CLOSED'],unit:'runs'},
 'JANUS.COMPUTE':{modes:['CLOSED'],unit:'jobs'}
};
const rewards=[
 {icon:'⌕',name:'SEARCH BONUS',desc:'Extra bounded search allowance',value:'+1 SEARCH'},
 {icon:'◇',name:'DATASET SCOUT BONUS',desc:'Additional dataset-scout entitlement',value:'+1 SCOUT'},
 {icon:'⇈',name:'DEEPER SEARCH DEPTH',desc:'Temporary search-depth modifier',value:'+1 DEPTH'},
 {icon:'≡',name:'EXTRA RESULT CAP',desc:'More results in an eligible bounded job',value:'+25%'},
 {icon:'▣',name:'ARCHIVE SCAN BONUS',desc:'Additional archive-scan allowance',value:'+1 SCAN'},
 {icon:'♛',name:'COSMETIC / STATUS',desc:'Agent badge or profile flair',value:'RARE'}
];

function showView(id){
  $$('.view').forEach(v=>v.classList.toggle('active-view',v.id===id));
  $$('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===id));
  closeTrade();
  scrollTo({top:0,behavior:'smooth'});
}

function installAgentSlotUI(){
  const oldTab=$('.nav-link[data-view="gmshop"]');
  if(oldTab){
    oldTab.textContent='AGENT SLOT';
    oldTab.classList.add('agent-slot-tab');
    oldTab.setAttribute('aria-label','Open JANUS Agent Slot');
  }

  const review=$('#reviewTrade');
  if(review&&!$('#openAgentSlot')){
    review.insertAdjacentHTML('afterend','<button id="openAgentSlot" class="slot-cta" type="button">✦ OPEN AGENT SLOT</button>');
  }

  if(!$('.agent-mobile-dock')){
    const dock=document.createElement('nav');
    dock.className='agent-mobile-dock';
    dock.setAttribute('aria-label','Mobile market navigation');
    dock.innerHTML='<button type="button" data-view="market">MARKET</button><button type="button" data-view="gmshop">✦ AGENT SLOT</button><button type="button" data-view="status">STATUS</button>';
    document.body.appendChild(dock);
  }
}

installAgentSlotUI();
$$('[data-view]').forEach(b=>b.addEventListener('click',()=>showView(b.dataset.view)));

async function boot(){
  try{state.catalog=(await fetch('CATALOG.json',{cache:'no-store'}).then(r=>r.json())).products||[]}
  catch(e){console.error(e)}
  renderCatalog();renderLoadout();renderRewards();renderSurfaces();bind();
}

function renderCatalog(){
  const q=($('#catalogSearch')?.value||'').toLowerCase(),f=$('#catalogFilter')?.value||'all';
  const host=$('#catalog');host.innerHTML='';
  state.catalog.filter(p=>{
    const blob=(p.sku+' '+p.title+' '+p.class).toLowerCase();
    if(q&&!blob.includes(q))return false;
    if(f==='closed'&&!p.status.includes('CLOSED'))return false;
    if(f==='open'&&!p.machine_discovery)return false;
    if(f==='tech'&&p.class!=='technology_license')return false;
    return true;
  }).forEach(p=>{
    const closed=p.status.includes('CLOSED'),cfg=uiConfig[p.sku]||{modes:['STANDARD'],unit:'units'};
    const el=document.createElement('article');
    el.className='sku-card '+(closed?'closed':'');
    el.innerHTML=`<div class="sku-top"><div class="sku-icon">${iconMap[p.class]||'◫'}</div><span class="sku-state">${p.status}</span></div><h3>${p.sku}</h3><p>${productSummary(p.sku)}</p><div class="sku-tags"><span class="tag">${p.class}</span><span class="tag">${p.machine_discovery?'discoverable':'hidden'}</span><span class="tag">${p.machine_purchase?'machine purchase':'not purchasable yet'}</span></div><div class="sku-actions"><input type="number" min="1" value="1" aria-label="Quantity"><select>${cfg.modes.map(x=>`<option>${x}</option>`).join('')}</select><button class="${closed?'tiny-btn':'gold-btn'}" ${closed?'disabled':''}>${closed?'LOCKED':'ADD'}</button></div>`;
    if(!closed)el.querySelector('button').onclick=()=>addLoadout(p,Number(el.querySelector('input').value||1),el.querySelector('select').value);
    host.append(el);
  });
}

function productSummary(sku){return {
 'JANUS.SEARCH':'Bounded search with provenance and uncertainty.',
 'JANUS.DATASET_SCOUT':'Discover relevant public datasets and source metadata.',
 'JANUS.EVIDENCE_PACK':'Evidence, contradictions, confidence and provenance.',
 'JANUS.ARCHIVE_SCAN':'Open-archive discovery and bounded corpus scan.',
 'JANUS.REPO_AUDIT':'Repository architecture, claims and dependency review.',
 'JANUS.RESEARCH_JOB':'Tailored bounded research job.',
 'JANUS.INFERENCE':'Future bounded JANUS operation — currently closed.',
 'JANUS.COMPUTE':'Future allowlisted compute execution — currently closed.',
 'HELIOS.PILOT':'Technology pilot discovery lane with separate authority.'
}[sku]||'Machine-readable JANUS service.'}

function addLoadout(p,qty,mode){
  const cfg=uiConfig[p.sku]||{unit:'units'};
  const ex=state.loadout.find(x=>x.sku===p.sku&&x.mode===mode);
  ex?ex.qty+=qty:state.loadout.push({sku:p.sku,qty,mode,unit:cfg.unit});
  renderLoadout();
}

function renderLoadout(){
  const host=$('#loadoutList');
  if(!state.loadout.length){host.className='loadout-list empty';host.textContent='Add services from the catalog.';return}
  host.className='loadout-list';
  host.innerHTML=state.loadout.map((x,i)=>`<div class="load-item"><div><b>${x.sku}</b><small>${x.qty} × ${x.unit} · ${x.mode}</small></div><button class="remove" data-i="${i}">×</button></div>`).join('');
  host.querySelectorAll('.remove').forEach(b=>b.onclick=()=>{state.loadout.splice(Number(b.dataset.i),1);renderLoadout()});
}

function renderRewards(){$('#rewardList').innerHTML=rewards.map(r=>`<div class="reward"><i>${r.icon}</i><div><b>${r.name}</b><small>${r.desc}</small></div><strong>${r.value}</strong></div>`).join('')}
function renderSurfaces(){const surfaces=[['BEACON.json','Canonical discovery beacon'],['CATALOG.json','Service catalog'],['AGENT_MARKET.json','Agent-readable market manifest'],['COMMERCIAL.json','Commercial pointer'],['GM_SHOP.json','GM Shop / play-credit policy'],['llms.txt','Model-friendly index'],['.well-known/agent-market.json','JANUS native well-known pointer'],['docs/FOREIGN_AGENT_WITNESS_GATE.md','Current independent requester gate'],['BUYER_QUERY_PLANE.json','Prepared bounded buyer-query contract']];$('#surfaceGrid').innerHTML=surfaces.map(([h,d])=>`<a class="surface" href="${h}"><b>${h}</b><small>${d}</small></a>`).join('')}

function bind(){
  $('#catalogSearch').oninput=renderCatalog;
  $('#catalogFilter').onchange=renderCatalog;
  $('#clearLoadout').onclick=()=>{state.loadout=[];renderLoadout()};
  $('#reviewTrade').onclick=openTrade;
  $('#openAgentSlot').onclick=()=>showView('gmshop');
  $('#closeTrade').onclick=closeTrade;
  $('#tradeModal').onclick=e=>{if(e.target.id==='tradeModal')closeTrade()};
  $('#needButton').onclick=recommend;
  $('#betDown').onclick=()=>setBet(state.bet-5);
  $('#betUp').onclick=()=>setBet(state.bet+5);
  $('#activateBonus').onclick=activateBonus;
  $('#copyShadow').onclick=copyShadow;
  $('#openShadow').onclick=openShadow;
}

function recommend(){
  const q=$('#needInput').value.toLowerCase();let sku='JANUS.RESEARCH_JOB',pct=72;
  if(/dataset|data|corpus/.test(q)){sku='JANUS.DATASET_SCOUT';pct=96}
  else if(/repo|github|audit/.test(q)){sku='JANUS.REPO_AUDIT';pct=91}
  else if(/evidence|contradiction|proof/.test(q)){sku='JANUS.EVIDENCE_PACK';pct=93}
  else if(/search|find|look/.test(q)){sku='JANUS.SEARCH';pct=94}
  else if(/archive|histor/.test(q)){sku='JANUS.ARCHIVE_SCAN';pct=89}
  const box=$('#recommendation');box.hidden=false;box.innerHTML=`Recommended: <b>${sku}</b> · ${pct}% match`;
}

function configureTradeActions(){
  const hasSearch=state.loadout.some(x=>x.sku==='JANUS.SEARCH');
  const hasHelios=state.loadout.some(x=>x.sku==='HELIOS.PILOT');
  const copy=$('#copyShadow'),primary=$('#openShadow');
  copy.hidden=!hasSearch;
  primary.disabled=false;
  if(hasSearch){
    primary.textContent='CONFIRM ZERO-PRICE SHADOW REQUEST';
    primary.onclick=openShadow;
  }else if(hasHelios){
    primary.textContent='VIEW HELIOS PILOT AUTHORITY';
    primary.onclick=()=>open('https://github.com/Hawkar-usls/Janus-HELIOS','_blank');
  }else{
    primary.textContent='CURRENT SKU IS PREVIEW-ONLY';
    primary.disabled=true;
    primary.onclick=null;
  }
}

function openTrade(){
  if(!state.loadout.length){alert('Add at least one service to your loadout first.');return}
  $('#buyerTradeItems').innerHTML=state.loadout.map(x=>`<div class="trade-item"><span>${x.sku}<small style="display:block;color:#8496a5">${x.mode}</small></span><b>×${x.qty}</b></div>`).join('');
  configureTradeActions();
  const modal=$('#tradeModal');
  modal.classList.add('open');modal.setAttribute('aria-hidden','false');
  document.body.classList.add('trade-open');
  requestAnimationFrame(()=>{modal.scrollTop=0});
}

function closeTrade(){
  const modal=$('#tradeModal');
  if(!modal)return;
  modal.classList.remove('open');modal.setAttribute('aria-hidden','true');
  document.body.classList.remove('trade-open');
}

function shadowRequest(){
  const s=state.loadout.find(x=>x.sku==='JANUS.SEARCH');if(!s)return null;
  return {schema:'janus.machine_market.request.v1',request_id:'pages-shadow-'+Date.now(),purchase_id:null,sku:'JANUS.SEARCH',input:{query:$('#needInput').value.trim()||'repository audit research evidence',source_scope:'MARKET_CATALOG',max_results:Math.max(1,s.qty)},requested_output:{format:'application/json'},max_runtime_seconds:10,created_at:null};
}

async function copyShadow(){const r=shadowRequest();if(!r)return alert('Current bounded shadow ingress accepts JANUS.SEARCH only. Add JANUS.SEARCH first.');await navigator.clipboard.writeText(JSON.stringify(r,null,2));alert('Shadow request JSON copied.')}
function openShadow(){const r=shadowRequest();if(!r)return alert('Current bounded shadow ingress accepts JANUS.SEARCH only. Add JANUS.SEARCH first.');const title='[JANUS SEARCH SHADOW] Pages zero-price shadow request';const body=['Generated by JANUS MACHINE MARKET Pages.','', 'This is a zero-price shadow request. It is not a payment or autonomous purchase.','', '<!-- JANUS_MACHINE_REQUEST_JSON',JSON.stringify(r,null,2),'JANUS_MACHINE_REQUEST_JSON -->'].join('\n');open(`https://github.com/Hawkar-usls/JANUS-MACHINE-MARKET/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`,'_blank')}
function setBet(n){state.bet=Math.max(5,Math.min(50,Math.round(n/5)*5));$('#betValue').textContent=state.bet}
function activateBonus(){if(state.spinning)return;if(state.balance<state.bet){$('#bonusResult').textContent='Not enough demo play credit.';return}state.spinning=true;state.balance-=state.bet;$('#playBalance').textContent=state.balance;$('#bonusStage').classList.add('activating');$('#cameraLabel').textContent='TOP CAMERA · ACTIVATING';$('#activateBonus').disabled=true;$('#bonusResult').className='bonus-result';$('#bonusResult').textContent='Portal open. Axle accelerating…';setTimeout(()=>{const r=rewards[Math.floor(Math.random()*rewards.length)],bonus=[0,5,10,15,25][Math.floor(Math.random()*5)];state.balance+=bonus;$('#playBalance').textContent=state.balance;$('#bonusResult').className='bonus-result win';$('#bonusResult').innerHTML=`<b>${r.name}</b><br>${r.value}${bonus?` · +${bonus} JANUS COIN play credit`:''}<br><small>Preview result only. No cash value. No purchased quota was risked.</small>`;$('#cameraLabel').textContent='TOP CAMERA · RESULT';},2600);setTimeout(()=>{$('#bonusStage').classList.remove('activating');$('#cameraLabel').textContent='FRONT CAMERA';$('#activateBonus').disabled=false;state.spinning=false},5600)}

boot();
