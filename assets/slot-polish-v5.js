(() => {
  'use strict';

  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const PHASES = [
    ['CROSSROADS','Choose play-credit stake'],
    ['THRESHOLD','Blue Gate opens'],
    ['OCULUS','Axle resolves the spin'],
    ['REWARD','Buff / credit delivered']
  ];
  let phaseTimers=[];

  function clearPhaseTimers(){ phaseTimers.forEach(clearTimeout); phaseTimers=[]; }
  function later(ms,fn){ const t=setTimeout(fn,ms); phaseTimers.push(t); return t; }

  function mountCrossroads(){
    const scene=$('#bonusStage .scene-camera');
    if(!scene || scene.querySelector('.crossroads-world')) return;
    const world=document.createElement('div');
    world.className='crossroads-world';
    world.setAttribute('aria-hidden','true');
    world.innerHTML=`<div class="crossroads-plane">
      <i class="road-line"></i><i class="road-line vertical"></i><i class="crossroads-sigil"></i>
      <span class="waymark north">DISCOVER</span><span class="waymark south">RETURN</span>
      <span class="waymark west">ARCHIVE</span><span class="waymark east">SEARCH</span>
    </div><div class="gate-ground-shadow"></div>`;
    scene.prepend(world);

    const stage=$('#bonusStage');
    const canon=document.createElement('div');
    canon.className='slot-canon-strip';
    canon.setAttribute('aria-hidden','true');
    canon.innerHTML='<span>CROSSROADS</span><span>THRESHOLD</span><span>AXIS</span><span>LIGHT</span><span>PORTAL</span>';
    stage.appendChild(canon);

    const provenance=document.createElement('div');
    provenance.className='slot-provenance';
    provenance.innerHTML='<b>JANUS GATE · PHYSICAL SOURCE</b>Real <code>JANUS_ARCH_QNAP_A1_ECO</code> photography<br><em>+ canonical digital crossroads composite</em>';
    stage.appendChild(provenance);
  }

  function mountPhaseRail(){
    const stage=$('#bonusStage');
    if(!stage || stage.querySelector('.slot-phase-rail')) return;
    const rail=document.createElement('div');
    rail.className='slot-phase-rail';
    rail.setAttribute('aria-label','Agent Slot activation phases');
    rail.innerHTML=PHASES.map((p,i)=>`<div class="slot-phase ${i===0?'active':''}" data-phase="${i}"><i>${i+1}</i><div><b>${p[0]}</b><small>${p[1]}</small></div></div>`).join('');
    stage.appendChild(rail);
  }

  function setPhase(index){
    $$('.slot-phase').forEach((el,i)=>{
      el.classList.toggle('active',i===index);
      el.classList.toggle('done',i<index);
    });
  }

  function resetPhaseSoon(){
    later(5250,()=>setPhase(0));
  }

  function runPhaseSequence(){
    clearPhaseTimers();
    setPhase(1);
    later(850,()=>setPhase(2));
    later(2600,()=>setPhase(3));
    resetPhaseSoon();
  }

  function setStake(target){
    const value=$('#betValue'), down=$('#betDown'), up=$('#betUp');
    if(!value||!down||!up) return;
    target=Math.max(5,Math.min(50,Math.round(target/5)*5));
    let current=Number(value.textContent)||10;
    let guard=20;
    while(current<target && guard--){ up.click(); current=Number(value.textContent)||current+5; }
    guard=20;
    while(current>target && guard--){ down.click(); current=Number(value.textContent)||current-5; }
    syncQuickStakes();
  }

  function syncQuickStakes(){
    const current=Number($('#betValue')?.textContent||0);
    $$('.quick-stakes button').forEach(b=>b.classList.toggle('active',Number(b.dataset.stake)===current));
  }

  function mountExplainer(){
    const panel=$('#gmshop .reward-panel');
    if(!panel || panel.querySelector('.slot-explainer')) return;
    const h2=panel.querySelector('h2');
    const explain=document.createElement('div');
    explain.className='slot-explainer';
    explain.innerHTML=`
      <div class="slot-step"><span>1</span><b>STAKE</b><small>Choose JANUS COIN play credit only.</small></div>
      <div class="slot-step"><span>2</span><b>ACTIVATE</b><small>The Gate shifts front → top camera.</small></div>
      <div class="slot-step"><span>3</span><b>COLLECT</b><small>A preview buff and possible coin kicker land in the local account.</small></div>`;
    h2?.after(explain);

    const safety=document.createElement('div');
    safety.className='slot-safety-line';
    safety.innerHTML='<span>✓ PURCHASED QUOTA SAFE</span><span>NO CASH-OUT</span><span>NON-TRANSFERABLE</span>';
    explain.after(safety);

    const betRow=panel.querySelector('.bet-row');
    if(betRow){
      const quick=document.createElement('div');
      quick.className='quick-stakes';
      quick.setAttribute('aria-label','Quick play-credit stakes');
      quick.innerHTML=[5,10,25,50].map(n=>`<button type="button" data-stake="${n}">${n} JC</button>`).join('');
      betRow.appendChild(quick);
      quick.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>setStake(Number(b.dataset.stake))));
    }

    const result=panel.querySelector('#bonusResult');
    const caption=document.createElement('div');
    caption.className='slot-result-caption';
    caption.innerHTML='<span>RESULT IS LOCAL PREVIEW STATE</span><b>authoritative: false</b>';
    result?.after(caption);

    const odds=document.createElement('div');
    odds.className='slot-odds';
    odds.innerHTML=`<div class="slot-odds-head"><b>PREVIEW RNG DISCLOSURE</b><span>VISIBLE MATH</span></div>
      <div class="slot-odds-grid">
        <div class="slot-odd"><span>Reward family</span><strong>1 / 6 each</strong></div>
        <div class="slot-odd"><span>Coin kicker values</span><strong>1 / 5 each</strong></div>
        <div class="slot-odd"><span>Kicker set</span><strong>0 · 5 · 10 · 15 · 25</strong></div>
        <div class="slot-odd"><span>Purchased quota risk</span><strong>0</strong></div>
      </div><div class="slot-odds-note"><b>Current public demo implementation:</b> reward family is uniform across six buff classes; the independent JANUS COIN kicker is uniform across the five disclosed values. This is preview UI logic, not certified gambling math.</div>`;
    caption.after(odds);

    const rules=document.createElement('details');
    rules.className='slot-rules';
    rules.id='slotRules';
    rules.innerHTML=`<summary>HOW THE AGENT SLOT WORKS</summary><div class="slot-rules-body">
      <b>1 · Credit boundary.</b> The stake comes only from non-transferable JANUS COIN demo play credit. Purchased quota remains outside the spin.<br><br>
      <b>2 · Gate sequence.</b> The physical Janus Arch photograph is placed in the registered <code>CROSSROADS → THRESHOLD → AXIS → LIGHT → PORTAL</code> scene. Activation switches to the physical top-camera surface and accelerates the Oculus/Axle.<br><br>
      <b>3 · Result.</b> One preview reward family is selected and an independent demo coin kicker may be added. Rewards appear in the local Agent Account inventory/history.<br><br>
      <b>4 · Truth boundary.</b> No cash-out, no transfer, no payment authority, no execution authority, and no claim that the visual portal is a literal physical gateway.
    </div>`;
    odds.after(rules);
    syncQuickStakes();
  }

  function mountRulesTool(){
    const tools=$('.slot-stage-tools');
    if(!tools || tools.querySelector('[data-action="rules"]')) return;
    const btn=document.createElement('button');
    btn.type='button';
    btn.className='slot-stage-tool';
    btn.dataset.action='rules';
    btn.textContent='? RULES';
    btn.setAttribute('aria-label','Open Agent Slot rules');
    btn.addEventListener('click',()=>{
      const rules=$('#slotRules');
      if(!rules) return;
      rules.open=true;
      rules.scrollIntoView({behavior:'smooth',block:'center'});
    });
    tools.appendChild(btn);
  }

  function bindActivation(){
    const btn=$('#activateBonus'), stage=$('#bonusStage');
    if(!btn || !stage || btn.dataset.v5Bound==='1') return;
    btn.dataset.v5Bound='1';
    btn.addEventListener('click',()=>{
      requestAnimationFrame(()=>{
        if(stage.classList.contains('activating')) runPhaseSequence();
      });
    });
    $('#betDown')?.addEventListener('click',()=>setTimeout(syncQuickStakes,0));
    $('#betUp')?.addEventListener('click',()=>setTimeout(syncQuickStakes,0));
  }

  function observeResult(){
    const result=$('#bonusResult');
    if(!result || result.dataset.v5Observed==='1') return;
    result.dataset.v5Observed='1';
    new MutationObserver(()=>{
      if(result.classList.contains('win')) setPhase(3);
    }).observe(result,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class']});
  }

  function mount(){
    if(document.documentElement.dataset.slotPolishV5==='1') return;
    document.documentElement.dataset.slotPolishV5='1';
    mountCrossroads();
    mountPhaseRail();
    mountExplainer();
    bindActivation();
    observeResult();
    mountRulesTool();
    /* V4 creates stage tools/account UI synchronously, but keep one retry for slow startup/cache races. */
    setTimeout(mountRulesTool,450);
    setTimeout(syncQuickStakes,500);
  }

  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',mount,{once:true});
  else mount();
})();
