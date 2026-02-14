let selected=null, cache=[];
const latencyHistory={};

async function api(path,method='GET',body=null){
  const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null});
  const t=await r.text();
  let d={};
  try{d=JSON.parse(t)}catch{d={raw:t}};
  if(!r.ok)throw new Error(d.detail||d.error||t);
  return d;
}

function esc(s){return String(s||'').replaceAll("'","&#39;")}
function pick(id){const p=cache.find(x=>x.id===id);if(!p)return;selected=p;sel.textContent=`id=${p.id} conf=${p.confidence} file_id=${p.file_id}`;folder.value=p.proposed_folder||'';fname.value=p.proposed_filename||'';}

async function loadProposals(){
  const st=status.value;
  const d=await api(`/proxy/organization/proposals?status=${encodeURIComponent(st)}&limit=250&offset=0`);
  cache=d.items||[];
  const rp=(rootprefix.value||'').trim().replaceAll('\\\\','/');
  if(rp){cache=cache.filter(p=>String(p.current_path||'').replaceAll('\\\\','/').startsWith(rp));}
  tb.innerHTML=cache.map(p=>`<tr onclick='pick(${p.id})'><td>${p.id}</td><td>${Number(p.confidence||0).toFixed(2)}</td><td title='${esc(p.current_path)}'>${(p.current_path||'').slice(0,56)}</td><td>${p.proposed_folder||''}</td><td>${p.proposed_filename||''}</td><td>${(p.metadata||{}).decision_source||''}</td></tr>`).join('');
  if(cache.length)pick(cache[0].id)
}

async function loadAudit(){
  try {
    const f=await api('/proxy/organization/feedback?limit=25&offset=0');
    const a=await api('/proxy/organization/actions?limit=25&offset=0');
    feedback.textContent=JSON.stringify((f.items||[]).map(x=>({id:x.id,proposal_id:x.proposal_id,action:x.action,note:x.note,at:x.created_at})),null,2);
    actions.textContent=JSON.stringify((a.items||[]).map(x=>({id:x.id,proposal_id:x.proposal_id,type:x.action_type,ok:!!x.success,rollback_group:x.rollback_group,from:x.from_path,to:x.to_path,at:x.created_at})),null,2);
  } catch (e) {
    feedback.textContent='(feedback endpoint unavailable until API restart)';
    actions.textContent='(actions endpoint unavailable until API restart)';
  }
}

async function loadStats(){
  try {
    const s=await api('/proxy/organization/stats');
    stats.textContent=`proposals=${s.proposals_total} by_status=${JSON.stringify(s.proposals_by_status)} feedback=${s.feedback_total} actions=${s.actions_total}`;
  } catch {
    const p=await api(`/proxy/organization/proposals?status=${encodeURIComponent(status.value)}&limit=250&offset=0`);
    stats.textContent=`API stats endpoint unavailable (restart API). Showing current list size: ${(p.items||[]).length}`;
  }
}

async function loadStartup(){
  try {
    const st=await api('/proxy/startup/steps');
    const sv=await api('/proxy/startup/services');
    const env=await api('/proxy/startup/environment');
    const ctl=await api('/proxy/startup/control');
    startupSteps.textContent=JSON.stringify((st.items||[]).map(s=>({name:s.name,status:s.status,elapsed_ms:s.elapsed_ms,error:s.error,traceback:s.traceback})),null,2);
    startupSvcEnv.textContent=JSON.stringify({services:sv.items||[],environment:env.snapshot||{},controls:ctl},null,2);

    const svcItems=sv.items||[];
    for(const s of svcItems){
      if(typeof s.latency_ms==='number'){
        latencyHistory[s.service]=latencyHistory[s.service]||[];
        latencyHistory[s.service].push({at:new Date().toISOString(),latency_ms:s.latency_ms,status:s.status});
        latencyHistory[s.service]=latencyHistory[s.service].slice(-10);
      }
    }
    latencyWatch.textContent=JSON.stringify(latencyHistory,null,2);
  } catch (e) {
    startupSteps.textContent='Startup diagnostics unavailable: '+String(e);
    startupSvcEnv.textContent='(check /api/startup/* endpoints and API restart)';
    latencyWatch.textContent='(latency watch unavailable)';
  }
}

async function loadAwareness(){
  try {
    const a=await api('/proxy/startup/awareness?limit=40');
    startupAware.textContent=JSON.stringify({
      level:a.level,
      uptime_seconds:a.uptime_seconds,
      failed_services:(a.failed_services||[]).map(x=>({service:x.service,error:x.error,latency_ms:x.latency_ms})),
      slow_services:(a.slow_services||[]).map(x=>({service:x.service,latency_ms:x.latency_ms})),
      recent_events:(a.events||[]).slice(-15)
    },null,2);
  } catch(e){
    startupAware.textContent='Awareness endpoint unavailable: '+String(e);
  }
}

async function loadAll(){await loadStats(); await loadProposals(); await loadAudit(); await loadStartup(); await loadAwareness();}
async function gen(){out.textContent=JSON.stringify(await api('/proxy/organization/proposals/generate','POST',{limit:200,root_prefix:(rootprefix.value||'').trim()||null}),null,2);await loadAll();}
async function clearScoped(){if(!confirm('Clear (reject) proposals in current scope/status?'))return;out.textContent=JSON.stringify(await api('/proxy/organization/proposals/clear','POST',{status:status.value||'proposed',root_prefix:(rootprefix.value||'').trim()||null,note:'gui_clear'}),null,2);await loadAll();}
async function approve(){if(!selected)return;out.textContent=JSON.stringify(await api(`/proxy/organization/proposals/${selected.id}/approve`,'POST',{}),null,2);await loadAll();}
async function reject(){if(!selected)return;out.textContent=JSON.stringify(await api(`/proxy/organization/proposals/${selected.id}/reject`,'POST',{note:note.value||null}),null,2);await loadAll();}
async function editApprove(){if(!selected)return;out.textContent=JSON.stringify(await api(`/proxy/organization/proposals/${selected.id}/edit`,'POST',{proposed_folder:folder.value,proposed_filename:fname.value,note:note.value||null}),null,2);await loadAll();}
async function dryApply(){out.textContent=JSON.stringify(await api('/proxy/organization/apply','POST',{limit:10,dry_run:true}),null,2);await loadAll();}
async function realApply(){if(!confirm('Real apply for approved items (limit 10)?'))return;out.textContent=JSON.stringify(await api('/proxy/organization/apply','POST',{limit:10,dry_run:false}),null,2);await loadAll();}
async function bulkApprove(){const m=parseFloat(minconf.value||'0.8');const items=cache.filter(p=>Number(p.confidence||0)>=m);let n=0;for(const p of items){await api(`/proxy/organization/proposals/${p.id}/approve`,'POST',{});n++;}out.textContent=`Bulk approved ${n} proposals (conf>=${m})`;await loadAll();}

loadAll().catch(e=>out.textContent=String(e));
setInterval(()=>loadStats().catch(()=>{}),5000);
setInterval(()=>loadStartup().catch(()=>{}),10000);
setInterval(()=>loadAwareness().catch(()=>{}),10000);
