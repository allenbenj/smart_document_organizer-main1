#!/usr/bin/env python3
"""Standalone Organization Console.
Run: python tools/org_console/app.py
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_BASE = "http://127.0.0.1:8000/api"
HOST, PORT = "127.0.0.1", 8010

INDEX_HTML = """<!doctype html><html><head><meta charset='utf-8'/><title>Organization Console</title>
<style>
body{font-family:Arial;margin:14px}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px}
.grid{display:grid;grid-template-columns:1.3fr 1fr;gap:10px}.panel{border:1px solid #ddd;border-radius:8px;padding:10px}
small,.muted{color:#666} table{width:100%;border-collapse:collapse}th,td{border:1px solid #ddd;padding:5px;font-size:12px}
tr:hover{background:#f7f7f7;cursor:pointer} input,textarea,select{width:100%}
pre{white-space:pre-wrap;font-size:12px;max-height:200px;overflow:auto;background:#fafafa;padding:8px}
</style></head><body>
<h2>Organization Console</h2>
<div class='row'>
  <button onclick='loadAll()'>Refresh All</button>
  <button onclick='loadStartup()'>Refresh Startup Diagnostics</button>
  <button onclick='gen()'>Generate Proposals</button>
  <button onclick='clearScoped()'>Clear Scoped Proposals</button>
  <button onclick='dryApply()'>Dry Apply (10)</button>
  <button onclick='realApply()'>Real Apply (10)</button>
  <label>Status <select id='status' onchange='loadProposals()'><option>proposed</option><option>approved</option><option>rejected</option><option>applied</option></select></label>
  <label>Root scope (optional) <input id='rootprefix' placeholder='/mnt/e/.../Final Products' style='min-width:360px'/></label>
  <label>Bulk approve conf >= <input id='minconf' value='0.8' style='width:80px'/></label>
  <button onclick='bulkApprove()'>Bulk Approve</button>
</div>
<div class='row muted' id='stats'>stats loading...</div>
<div class='grid'>
  <div class='panel'>
    <h3>Proposals</h3>
    <table><thead><tr><th>ID</th><th>Conf</th><th>From</th><th>Folder</th><th>Name</th><th>Src</th></tr></thead><tbody id='tb'></tbody></table>
  </div>
  <div class='panel'>
    <h3>Selected</h3><div id='sel' class='muted'>none</div>
    <label>Proposed folder</label><input id='folder'/>
    <label>Proposed filename</label><input id='fname'/>
    <label>Note</label><textarea id='note' rows='3'></textarea>
    <div class='row'><button onclick='approve()'>Approve</button><button onclick='reject()'>Reject</button><button onclick='editApprove()'>Edit+Approve</button></div>
    <pre id='out'></pre>
  </div>
</div>
<div class='grid' style='margin-top:10px'>
  <div class='panel'><h3>Recent Feedback</h3><pre id='feedback'></pre></div>
  <div class='panel'><h3>Recent Actions</h3><pre id='actions'></pre></div>
</div>
<div class='grid' style='margin-top:10px'>
  <div class='panel'><h3>Startup Steps (real state)</h3><pre id='startupSteps'></pre></div>
  <div class='panel'><h3>Service + Environment Snapshot</h3><pre id='startupSvcEnv'></pre></div>
</div>
<div class='grid' style='margin-top:10px'>
  <div class='panel'><h3>Admin Awareness Monitor</h3><pre id='startupAware'></pre></div>
  <div class='panel'><h3>Service Latency Watch</h3><pre id='latencyWatch'></pre></div>
</div>
<script>
let selected=null, cache=[];
const latencyHistory={};
async function api(path,method='GET',body=null){const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):null});const t=await r.text();let d={};try{d=JSON.parse(t)}catch{d={raw:t}};if(!r.ok)throw new Error(d.detail||d.error||t);return d;}
function esc(s){return String(s||'').replaceAll("'","&#39;")}
function pick(id){const p=cache.find(x=>x.id===id);if(!p)return;selected=p;sel.textContent=`id=${p.id} conf=${p.confidence} file_id=${p.file_id}`;folder.value=p.proposed_folder||'';fname.value=p.proposed_filename||'';}
async function loadProposals(){const st=status.value;const d=await api(`/proxy/organization/proposals?status=${encodeURIComponent(st)}&limit=250&offset=0`);cache=d.items||[];const rp=(rootprefix.value||'').trim().replaceAll('\\\\','/');if(rp){cache=cache.filter(p=>String(p.current_path||'').replaceAll('\\\\','/').startsWith(rp));}tb.innerHTML=cache.map(p=>`<tr onclick='pick(${p.id})'><td>${p.id}</td><td>${Number(p.confidence||0).toFixed(2)}</td><td title='${esc(p.current_path)}'>${(p.current_path||'').slice(0,56)}</td><td>${p.proposed_folder||''}</td><td>${p.proposed_filename||''}</td><td>${(p.metadata||{}).decision_source||''}</td></tr>`).join(''); if(cache.length)pick(cache[0].id)}
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
    stats.textContent=`API stats endpoint unavailable (restart API). Showing current list size: ${ (p.items||[]).length }`;
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
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, ctype: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/":
            return self._send(200, INDEX_HTML.encode(), "text/html; charset=utf-8")
        if self.path.startswith('/proxy/'):
            target = API_BASE + self.path[len('/proxy'):]
            try:
                with urllib.request.urlopen(target, timeout=60) as r:
                    return self._send(r.status, r.read(), r.headers.get_content_type())
            except urllib.error.HTTPError as e:
                return self._send(e.code, e.read())
            except Exception as e:
                return self._send(500, json.dumps({'error': str(e)}).encode())
        return self._send(404, b'not found', 'text/plain')

    def do_POST(self):  # noqa: N802
        if not self.path.startswith('/proxy/'):
            return self._send(404, b'not found', 'text/plain')
        raw = self.rfile.read(int(self.headers.get('Content-Length', '0') or 0)) or b'{}'
        target = API_BASE + self.path[len('/proxy'):]
        req = urllib.request.Request(target, data=raw, method='POST')
        req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return self._send(r.status, r.read(), r.headers.get_content_type())
        except urllib.error.HTTPError as e:
            return self._send(e.code, e.read())
        except Exception as e:
            return self._send(500, json.dumps({'error': str(e)}).encode())


def main() -> None:
    print(f'Organization Console running at http://{HOST}:{PORT}')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

if __name__ == '__main__':
    main()
