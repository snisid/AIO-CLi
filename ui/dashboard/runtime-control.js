/* AIO-CLi runtime control bridge: Cloud, SSH, Remote Control, Marketplace, Connectors. */
(function(){
  const $=s=>document.querySelector(s); const $$=s=>[...document.querySelectorAll(s)];
  const setText=(s,v)=>{const e=$(s);if(e)e.textContent=v;return e};
  const json=async(r)=>{const d=await r.json();if(!r.ok)throw Error(d.detail||d.message||'Request failed');return d};
  function addRuntimeControls(){
    const modal=$('[data-modal-panel="environment"]'); if(!modal)return;
    if($('#runtime-control-extra'))return;
    const extra=document.createElement('div'); extra.id='runtime-control-extra'; extra.className='runtime-extra';
    extra.innerHTML=`<div class="subhead"><span>Runtime control</span><span id="runtime-target-status">Ready</span></div>
      <div class="form-grid"><label>Cloud endpoint<input id="cloud-endpoint" placeholder="https://runtime.example.com"></label>
      <label>SSH host<input id="ssh-host" placeholder="server.example.com"></label>
      <label>SSH user<input id="ssh-user" placeholder="ubuntu"></label><label>SSH port<input id="ssh-port" type="number" min="1" max="65535" value="22"></label></div>
      <div class="runtime-actions"><button class="soft-btn" id="cloud-check">Check Cloud</button><button class="soft-btn" id="cloud-save">Save Cloud</button><button class="soft-btn" id="ssh-save">Save SSH</button><button class="soft-btn" id="ssh-check">Check SSH</button></div>
      <div class="result-box" id="runtime-control-result">Choisissez une cible et vérifiez sa connectivité.</div>`;
    modal.append(extra);
    $('#cloud-save')?.addEventListener('click',async()=>{try{const d=await json(fetch('/api/runtime/cloud/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({endpoint:$('#cloud-endpoint').value})}));setText('#environment-chip',d.name);setText('#environment-state',d.name);setText('#runtime-control-result','Cloud configuré.');}catch(e){setText('#runtime-control-result',e.message)}});
    $('#cloud-check')?.addEventListener('click',async()=>{try{const d=await json(fetch('/api/runtime/cloud/check',{method:'POST'}));setText('#runtime-control-result',d.reachable?'Cloud joignable ✓':(d.message||'Cloud indisponible'));}catch(e){setText('#runtime-control-result',e.message)}});
    $('#ssh-save')?.addEventListener('click',async()=>{try{const d=await json(fetch('/api/runtime/ssh/configure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({host:$('#ssh-host').value,user:$('#ssh-user').value,port:Number($('#ssh-port').value)})}));setText('#runtime-control-result',`SSH configuré : ${d.command}`);}catch(e){setText('#runtime-control-result',e.message)}});
    $('#ssh-check')?.addEventListener('click',async()=>{try{const d=await json(fetch('/api/runtime/ssh/check',{method:'POST'}));setText('#runtime-control-result',d.target?.status==='ready'?'SSH connecté ✓':(d.error||'SSH indisponible'));}catch(e){setText('#runtime-control-result',e.message)}});
  }
  function addDispatchControls(){
    const modal=$('[data-modal-panel="dispatch"]'); if(!modal||$('#remote-target'))return;
    const actions=modal.querySelector('.dispatch-actions');
    const select=document.createElement('select'); select.id='remote-target'; select.innerHTML='<option value="cloud">Cloud</option><option value="ssh">SSH</option><option value="wsl">WSL</option>';
    actions?.prepend(select);
    $('#dispatch-run')?.addEventListener('click',async()=>{try{const d=await json(fetch('/api/runtime/remote/dispatch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:$('#remote-target').value,task:$('#dispatch-task')?.value||''})}));setText('#dispatch-result',`Remote job ${d.id} créé sur ${d.target} : ${d.status}`);}catch(e){setText('#dispatch-result',e.message)}});
  }
  function wireMarketplace(){
    $$('.plugin-install').forEach(btn=>{if(btn.dataset.runtimeBound)return;btn.dataset.runtimeBound='1';btn.addEventListener('click',async()=>{const card=btn.closest('article');const name=card?.querySelector('b')?.textContent||'Plugin';const id=name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');try{const d=await json(fetch('/api/extensions/install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,name,kind:'plugin',version:'1.0.0',source:'builtin-marketplace'})}));btn.textContent='Installé ✓';btn.disabled=true;setText('#github-message',`${d.name} installé dans le runtime.`);}catch(e){btn.textContent='Erreur';setText('#github-message',e.message)}})});
  }
  async function refreshConnectors(){try{const items=await json(fetch('/api/connectors',{cache:'no-store'}));items.forEach(item=>{const el=document.querySelector(`[data-connector-id="${item.id}"]`);if(el)el.textContent=item.configured?'Configured':'Needs setup';});}catch(_){} }
  function wireConnectors(){
    $$('.connector-card').forEach(card=>{const name=card.querySelector('b')?.textContent?.trim()||'';const id={GitLab:'gitlab',Slack:'slack',Notion:'notion','Linear / Jira':'linear',Figma:'figma'}[name];if(!id)return;const state=card.querySelector('span');if(state){state.dataset.connectorId=id;state.id='connector-'+id;}const button=card.querySelector('button');if(button&&!button.dataset.bound){button.dataset.bound='1';button.addEventListener('click',async()=>{try{const d=await json(fetch(`/api/connectors/${id}/check`,{method:'POST'}));if(state)state.textContent=d.reachable?'Connected ✓':(d.configured?'Configured, unreachable':'Needs setup');}catch(e){if(state)state.textContent=e.message}})}});refreshConnectors();
  }
  function bind(){addRuntimeControls();addDispatchControls();wireMarketplace();wireConnectors();}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();
