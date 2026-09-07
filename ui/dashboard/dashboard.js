async function checkRuntime(){
  const statusText=document.getElementById('global-status');
  const dot=statusText.querySelector('span');
  try{
    const [healthRes,statusRes]=await Promise.all([fetch('/health',{cache:'no-store'}),fetch('/api/status',{cache:'no-store'})]);
    if(!healthRes.ok||!statusRes.ok) throw new Error('API unavailable');
    const health=await healthRes.json();
    const status=await statusRes.json();
    document.getElementById('metric-runtime').textContent=health.status==='ok'?'ONLINE':'DEGRADED';
    document.getElementById('metric-deployment').textContent=status.deployment||'vercel';
    document.getElementById('health-api').textContent='OK';
    document.getElementById('health-dashboard').textContent='OK';
    statusText.lastChild.textContent=' Runtime online';
    dot.style.background='#42e695';
    document.getElementById('health-tag').textContent='HEALTHY';
  }catch(error){
    document.getElementById('metric-runtime').textContent='ERROR';
    document.getElementById('health-api').textContent='ERROR';
    document.getElementById('health-dashboard').textContent='ERROR';
    statusText.lastChild.textContent=' Runtime unavailable';
    dot.style.background='#ff6b6b';
    document.getElementById('health-tag').textContent='DEGRADED';
  }
  try{
    const asset=await fetch('/assets/logo/ma-cli-animated.svg',{cache:'no-store'});
    document.getElementById('health-assets').textContent=asset.ok?'OK':'ERROR';
  }catch{document.getElementById('health-assets').textContent='ERROR';}
}
checkRuntime();
setInterval(checkRuntime,30000);
