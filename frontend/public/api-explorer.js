let _abort = null;
let _coPage = 1, _coQ = '';
let _cosPage = 1, _cosQ = '';
let _fiPage = 1;
let _fsPage = 1, _fsEntity = '', _fsQ = '', _fsForm = '', _fsFrom = '', _fsTo = '';
document.getElementById('agg-to').value = new Date().toISOString().slice(0,10);

function base() { return document.getElementById('base-input').value.trim().replace(/\/$/,''); }
function U(p)   { const b = base(); return b ? b+p : p; }

function chip(ms) {
  const c = ms<300?'chip-fast':ms<1000?'chip-mid':'chip-slow';
  return `<span style="font-size:11px;padding:4px 8px;border-radius:9999px;font-family:'JetBrains Mono',monospace;display:inline-flex;align-items:center;gap:4px" class="${c}">⚡ ${ms}ms</span>`;
}
function meta(ms, label) {
  return `<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">${chip(ms)}<span style="font-size:.75rem;color:#71717a">${label}</span></div>`;
}
function errBox(msg) {
  const net = msg.includes('fetch')||msg.includes('Failed')||msg.includes('Load');
  return `<div class="err-box">${net?'⚠️ Network error — backend may be sleeping (Cloud Run scales to zero). Try again.':`Error: ${msg}`}</div>`;
}
function errWithRetry(msg, retryExpr) {
  const net = msg.includes('fetch')||msg.includes('Failed')||msg.includes('Load')||msg.includes('NetworkError');
  const cleaned = String(msg).replace(/\s*For more information check:[^\n]*/i, '').trim();
  const text = net ? '⚠️ Network error — backend may be sleeping (Cloud Run scales to zero).' : `Error: ${esc(cleaned)}`;
  const btn = `<button class="run-btn" style="padding:3px 10px;font-size:.7rem;flex-shrink:0" onclick="${retryExpr}"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10M23 14l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>Retry</button>`;
  return `<div class="err-box" style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">${text}${btn}</div>`;
}
function spin() { return `<div style="display:flex;align-items:center;gap:8px;font-size:.75rem;color:#52525b"><div class="spinner"></div>Sending request…</div>`; }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function paginator(page, total, pageSize, prevExpr, nextExpr) {
  const totalPages = Math.max(Math.ceil(total/pageSize), 1);
  if (totalPages <= 1) return '';
  const hasPrev = page > 1, hasNext = page < totalPages;
  const on  = 'display:inline-flex;align-items:center;padding:4px 12px;border-radius:6px;font-size:.72rem;font-weight:600;border:1px solid rgba(139,92,246,0.4);color:#c4b5fd;cursor:pointer;background:rgba(139,92,246,0.15)';
  const off = 'display:inline-flex;align-items:center;padding:4px 12px;border-radius:6px;font-size:.72rem;font-weight:600;border:1px solid rgba(255,255,255,0.08);color:#3f3f46;cursor:not-allowed';
  const prev = hasPrev ? `<button style="${on}" onclick="${prevExpr}">← Prev</button>` : `<button disabled style="${off}">← Prev</button>`;
  const next = hasNext ? `<button style="${on}" onclick="${nextExpr}">Next →</button>` : `<button disabled style="${off}">Next →</button>`;
  return `<div style="display:flex;align-items:center;gap:12px;margin-top:12px">${prev}<span style="font-size:.72rem;color:#71717a">Page ${page} of ${totalPages}</span>${next}</div>`;
}

function rawJson(d) {
  const enc = esc(JSON.stringify(d,null,2));
  return `<div class="mt-3"><button onclick="var p=this.nextElementSibling;p.hidden=!p.hidden;this.style.color=p.hidden?'':'#a1a1aa'" style="display:flex;align-items:center;gap:6px;font-size:11px;user-select:none;color:#52525b;background:none;border:none;cursor:pointer"><span style="font-size:.55rem">▶</span>View raw JSON</button><pre class="rj mt-2" hidden>${enc}</pre></div>`;
}

function tog(id) {
  const b = document.getElementById('bdy-'+id);
  const c = document.getElementById('chv-'+id);
  const h = b.classList.toggle('hidden');
  h ? c.classList.remove('open') : c.classList.add('open');
}

const TH = s => `<th style="text-align:left;padding:8px 12px;font-weight:500;white-space:nowrap;color:#71717a;border-bottom:1px solid rgba(255,255,255,0.06);font-size:.75rem">${s}</th>`;
const TD = (s,m,c) => `<td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.04);color:${c||'#d4d4d8'};font-size:.72rem${m?';font-family:\'JetBrains Mono\',monospace':''}">${s}</td>`;

function filingTable(items) {
  if (!items.length) return '<p style="font-size:.75rem;color:#71717a">No results.</p>';
  const rows = items.map((f,i) =>
    `<tr>${TD(i+1,false,'#71717a')}${TD(esc(f.entity_name||'—'),true)}${TD(`<span style="padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600;background:rgba(129,140,248,0.12);border:1px solid rgba(129,140,248,0.3);color:#a5b4fc">${esc(f.form_type||'—')}</span>`,false)}${TD(esc(f.period_of_report||'—'),true,'#a1a1aa')}${TD(esc(f.file_date||'—'),true,'#71717a')}${TD(esc(f.cik||'—'),true,'#52525b')}</tr>`
  ).join('');
  return `<div style="overflow-x:auto;border-radius:.75rem;border:1px solid rgba(255,255,255,0.06)"><table style="width:100%;border-collapse:collapse"><thead><tr>${[['#'],['Entity'],['Form'],['Period'],['Filed'],['CIK']].map(([h])=>TH(h)).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function companyTable(items) {
  if (!items.length) return '<p style="font-size:.75rem;color:#71717a">No results.</p>';
  const rows = items.map((c,i) =>
    `<tr>${TD(i+1,false,'#71717a')}${TD(esc(c.entity_name||'—'),true)}${TD(esc(c.cik||'—'),true,'#a1a1aa')}${TD(esc(c.biz_location||'—'),false,'#71717a')}${TD(esc(c.inc_states||'—'),true,'#52525b')}</tr>`
  ).join('');
  return `<div style="overflow-x:auto;border-radius:.75rem;border:1px solid rgba(255,255,255,0.06)"><table style="width:100%;border-collapse:collapse"><thead><tr>${[['#'],['Company'],['CIK'],['Location'],['State']].map(([h])=>TH(h)).join('')}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function initPagedResult(id) {
  document.getElementById('res-'+id).innerHTML =
    `<div id="res-${id}-meta"></div><div id="res-${id}-body">${spin()}</div><div id="res-${id}-pager"></div><div id="res-${id}-raw"></div>`;
}
function setPagedResult(id, metaHtml, bodyHtml, pagerHtml, rawHtml) {
  document.getElementById('res-'+id+'-meta').innerHTML  = metaHtml;
  document.getElementById('res-'+id+'-body').innerHTML  = bodyHtml;
  document.getElementById('res-'+id+'-pager').innerHTML = pagerHtml;
  document.getElementById('res-'+id+'-raw').innerHTML   = rawHtml;
}

async function runCo(page) {
  if (page === undefined) {
    _coQ = document.getElementById('co-q').value.trim();
    if (!_coQ) { document.getElementById('res-companies').innerHTML='<p style="font-size:.75rem;color:#52525b">Enter a company name above.</p>'; return; }
    _coPage = 1;
    initPagedResult('companies');
  } else {
    _coPage = page;
    document.getElementById('res-companies-body').innerHTML = spin();
  }
  const btn = document.getElementById('co-btn'); btn.disabled=true;
  const t0=performance.now();
  try {
    const r=await fetch(U(`/companies?q=${encodeURIComponent(_coQ)}&page=${_coPage}&pageSize=10`));
    const ms=Math.round(performance.now()-t0);
    if(!r.ok){const err=await r.json().catch(()=>({detail:r.statusText}));document.getElementById('res-companies-body').innerHTML=errWithRetry(err.detail||r.statusText,'runCo(_coPage)');return;}
    const j=await r.json(); const items=j.items||[]; const total=Number(j.total||0); const pg=_coPage;
    setPagedResult('companies',
      meta(ms,`${total.toLocaleString()} compan${total!==1?'ies':'y'} found`),
      companyTable(items),
      paginator(pg,total,10,`runCo(${pg-1})`,`runCo(${pg+1})`),
      rawJson(j));
  } catch(e){document.getElementById('res-companies-body').innerHTML=errWithRetry(e.message,'runCo(_coPage)');}
  finally{btn.disabled=false;}
}

async function runCoSearch(page) {
  if (page === undefined) {
    _cosQ = document.getElementById('cos-q').value.trim();
    if (!_cosQ) { document.getElementById('res-cosearch').innerHTML='<p style="font-size:.75rem;color:#52525b">Enter a search term above.</p>'; return; }
    _cosPage = 1;
    initPagedResult('cosearch');
  } else {
    _cosPage = page;
    document.getElementById('res-cosearch-body').innerHTML = spin();
  }
  const btn = document.getElementById('cos-btn'); btn.disabled=true;
  const t0=performance.now();
  try {
    const r=await fetch(U(`/companies/search?q=${encodeURIComponent(_cosQ)}&page=${_cosPage}&pageSize=10`));
    const ms=Math.round(performance.now()-t0);
    if(!r.ok){const err=await r.json().catch(()=>({detail:r.statusText}));document.getElementById('res-cosearch-body').innerHTML=errWithRetry(err.detail||r.statusText,'runCoSearch(_cosPage)');return;}
    const j=await r.json(); const items=j.items||[]; const total=Number(j.total||0); const pg=_cosPage;
    setPagedResult('cosearch',
      meta(ms,`${total.toLocaleString()} filer${total!==1?'s':''} whose 10-K mentions "${_cosQ}"`),
      companyTable(items),
      paginator(pg,total,10,`runCoSearch(${pg-1})`,`runCoSearch(${pg+1})`),
      rawJson(j));
  } catch(e){document.getElementById('res-cosearch-body').innerHTML=errWithRetry(e.message,'runCoSearch(_cosPage)');}
  finally{btn.disabled=false;}
}

async function runFi(page) {
  if (page === undefined) {
    _fiPage = 1;
    initPagedResult('filings');
  } else {
    _fiPage = page;
    document.getElementById('res-filings-body').innerHTML = spin();
  }
  const btn=document.getElementById('fi-btn'); btn.disabled=true;
  const t0=performance.now();
  try {
    const r=await fetch(U(`/filings?form=10-K&pageSize=10&page=${_fiPage}`));
    const ms=Math.round(performance.now()-t0);
    if(!r.ok){const err=await r.json().catch(()=>({detail:r.statusText}));document.getElementById('res-filings-body').innerHTML=errWithRetry(err.detail||r.statusText,'runFi(_fiPage)');return;}
    const j=await r.json(); const items=j.items||[]; const total=Number(j.total||0); const pg=_fiPage;
    setPagedResult('filings',
      meta(ms,`${total.toLocaleString()} total 10-K filings`),
      filingTable(items),
      paginator(pg,total,10,`runFi(${pg-1})`,`runFi(${pg+1})`),
      rawJson(j));
  } catch(e){document.getElementById('res-filings-body').innerHTML=errWithRetry(e.message,'runFi(_fiPage)');}
  finally{btn.disabled=false;}
}

async function runFc() {
  const entity=document.getElementById('fc-entity').value.trim();
  const q=document.getElementById('fc-q').value.trim();
  const form=document.getElementById('fc-form').value.trim();
  const from=document.getElementById('fc-from').value;
  const to=document.getElementById('fc-to').value;
  const btn=document.getElementById('fc-btn'); btn.disabled=true;
  document.getElementById('res-fcount').innerHTML=spin();
  const t0=performance.now();
  try {
    const p=new URLSearchParams();
    if(entity)p.set('entity',entity); if(q)p.set('q',q); if(form)p.set('form',form);
    if(from)p.set('from',from); if(to)p.set('to',to);
    const r=await fetch(U(`/filings/count?${p}`));
    const ms=Math.round(performance.now()-t0);
    if(!r.ok){const err=await r.json().catch(()=>({detail:r.statusText}));document.getElementById('res-fcount').innerHTML=errWithRetry(err.detail||r.statusText,'runFc()');return;}
    const j=await r.json();
    document.getElementById('res-fcount').innerHTML=
      meta(ms,'filing count')+
      `<div class="stat-card" style="display:inline-block"><p style="font-size:10px;font-weight:500;letter-spacing:.05em;text-transform:uppercase;margin-bottom:4px;color:#52525b">Total</p><p style="font-size:1.5rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:#f4f4f5">${Number(j.total||0).toLocaleString()}</p></div>`+rawJson(j);
  } catch(e){document.getElementById('res-fcount').innerHTML=errWithRetry(e.message,'runFc()');}
  finally{btn.disabled=false;}
}

async function runFs(page) {
  if (page === undefined) {
    _fsEntity=document.getElementById('fs-entity').value.trim();
    _fsQ=document.getElementById('fs-q').value.trim();
    _fsForm=document.getElementById('fs-form').value.trim();
    _fsFrom=document.getElementById('fs-from').value;
    _fsTo=document.getElementById('fs-to').value;
    if (!_fsEntity&&!_fsQ){document.getElementById('res-fsearch').innerHTML='<p style="font-size:.75rem;color:#52525b">Enter an entity name or search term above.</p>';return;}
    _fsPage=1;
    initPagedResult('fsearch');
  } else {
    _fsPage=page;
    document.getElementById('res-fsearch-body').innerHTML = spin();
  }
  const btn=document.getElementById('fs-btn'); btn.disabled=true;
  const t0=performance.now();
  try {
    const p=new URLSearchParams({pageSize:'10',page:String(_fsPage)});
    if(_fsEntity)p.set('entity',_fsEntity); if(_fsQ)p.set('q',_fsQ); if(_fsForm)p.set('form',_fsForm);
    if(_fsFrom)p.set('from',_fsFrom); if(_fsTo)p.set('to',_fsTo);
    const r=await fetch(U(`/filings?${p}`));
    const ms=Math.round(performance.now()-t0);
    if(!r.ok){const err=await r.json().catch(()=>({detail:r.statusText}));document.getElementById('res-fsearch-body').innerHTML=errWithRetry(err.detail||r.statusText,'runFs(_fsPage)');return;}
    const j=await r.json(); const items=j.items||[]; const total=Number(j.total||0); const pg=_fsPage;
    const label=_fsEntity?`"${_fsEntity}"`:`"${_fsQ}"`;
    setPagedResult('fsearch',
      meta(ms,`${total.toLocaleString()} match${total!==1?'es':''} for ${label}`),
      items.length?filingTable(items):'<p style="font-size:.75rem;color:#71717a">No results.</p>',
      paginator(pg,total,10,`runFs(${pg-1})`,`runFs(${pg+1})`),
      rawJson(j));
  } catch(e){document.getElementById('res-fsearch-body').innerHTML=errWithRetry(e.message,'runFs(_fsPage)');}
  finally{btn.disabled=false;}
}

async function runAgg() {
  const from=document.getElementById('agg-from').value;
  const to=document.getElementById('agg-to').value;
  const q=document.getElementById('agg-q').value.trim();
  if(!from||!to){document.getElementById('res-agg').innerHTML='<p style="font-size:.75rem;color:#52525b">Set from and to dates.</p>';return;}
  const btn=document.getElementById('agg-btn'); btn.disabled=true;
  document.getElementById('res-agg').innerHTML=spin();
  const t0=performance.now();
  try {
    const form=document.getElementById('agg-form').value.trim();
    const p=new URLSearchParams({from,to}); if(form)p.set('form',form); if(q)p.set('q',q);
    const r=await fetch(U(`/aggregates?${p}`));
    const ms=Math.round(performance.now()-t0);
    if(!r.ok){const err=await r.json().catch(()=>({detail:r.statusText}));document.getElementById('res-agg').innerHTML=errWithRetry(err.detail||r.statusText,'runAgg()');return;}
    const j=await r.json();
    const data=j.data||[]; const total=j.totalFilings||0;
    const mx=Math.max(...data.map(d=>d.count),1);
    const n=data.length;
    const bars=n?data.map((d,i)=>{
      const x=(i/n)*600,bw=600/n,h=Math.max(2,(d.count/mx)*56);
      return `<rect x="${x.toFixed(1)}" y="${(60-h).toFixed(1)}" width="${Math.max(bw-.5,.5).toFixed(1)}" height="${h.toFixed(1)}" fill="#818cf8" rx="1"/>`;
    }).join(''):'';
    const chart=n?`<svg viewBox="0 0 600 60" width="100%" height="60" preserveAspectRatio="none" style="display:block;border-radius:6px;margin-bottom:12px">${bars}</svg>`:'';
    const stats=`<div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-bottom:16px">${[
      {l:'Total Filings',v:Number(total).toLocaleString(),c:'#f4f4f5'},
      {l:'Months Returned',v:String(n),c:'#f4f4f5'},
      {l:'Date Range',v:`${from} → ${to}`,c:'#818cf8'},
    ].map(s=>`<div class="stat-card"><p style="font-size:10px;font-weight:500;letter-spacing:.05em;text-transform:uppercase;margin-bottom:4px;color:#52525b">${s.l}</p><p style="font-size:1rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:${s.c}">${s.v}</p></div>`).join('')}</div>`;
    const trows=data.slice(0,12).map(d=>
      `<tr>${TD(esc(d.date),true,'#a1a1aa')}${TD(d.count.toLocaleString(),false)}<td style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.04);width:120px"><div style="background:rgba(129,140,248,0.6);height:4px;border-radius:2px;width:${Math.round((d.count/mx)*100)}%"></div></td></tr>`
    ).join('');
    const tbl=n?`<div style="overflow-x:auto;border-radius:.75rem;border:1px solid rgba(255,255,255,0.06)"><table style="width:100%;border-collapse:collapse"><thead><tr>${TH('Month')}${TH('Filings')}<th style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.06);width:120px"></th></tr></thead><tbody>${trows}</tbody></table></div>`:'<p style="font-size:.75rem;color:#71717a">No data for this range.</p>';
    document.getElementById('res-agg').innerHTML=
      meta(ms,`${n} month${n!==1?'s':''} · ${from} → ${to}`)+(n?stats+chart+tbl:tbl)+rawJson(j);
  } catch(e){document.getElementById('res-agg').innerHTML=errWithRetry(e.message,'runAgg()');}
  finally{btn.disabled=false;}
}

async function runBounds() {
  document.getElementById('res-bounds').innerHTML=spin();
  const t0=performance.now();
  try {
    const r=await fetch(U('/dataset-bounds'));
    const ms=Math.round(performance.now()-t0);
    if(!r.ok){const err=await r.json().catch(()=>({detail:r.statusText}));document.getElementById('res-bounds').innerHTML=errWithRetry(err.detail||r.statusText,'runBounds()');return;}
    const j=await r.json();
    document.getElementById('res-bounds').innerHTML=
      meta(ms,'EDGAR full-text search date range')+
      `<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px">${[{l:'Earliest filing',v:j.from||'—',c:'#818cf8'},{l:'Latest filing',v:j.to||'—',c:'#34d399'}].map(s=>`<div class="stat-card"><p style="font-size:10px;font-weight:500;letter-spacing:.05em;text-transform:uppercase;margin-bottom:4px;color:#52525b">${s.l}</p><p style="font-size:1rem;font-weight:700;font-family:'JetBrains Mono',monospace;color:${s.c}">${esc(s.v)}</p></div>`).join('')}</div>`+rawJson(j);
  } catch(e){document.getElementById('res-bounds').innerHTML=errWithRetry(e.message,'runBounds()');}
}

async function runHealth() {
  document.getElementById('res-health').innerHTML=spin();
  const t0=performance.now();
  try {
    const r=await fetch(U('/health'));
    const j=await r.json(); const ms=Math.round(performance.now()-t0);
    document.getElementById('res-health').innerHTML=
      meta(ms,r.ok?'backend is up':'backend error')+
      (r.ok?`<div class="ok-box">✓ ${j.status}</div>`:errWithRetry(JSON.stringify(j),'runHealth()'));
  } catch(e){document.getElementById('res-health').innerHTML=errWithRetry(e.message,'runHealth()');}
}

function setSample(el){document.getElementById('chat-msg').value=el.textContent.trim();}

async function runChat() {
  const msg=document.getElementById('chat-msg').value.trim();
  const sid=document.getElementById('chat-sid').value.trim();
  if(!msg){document.getElementById('res-chat').innerHTML='<div class="err-box">Enter a message first.</div>';return;}
  if(_abort)_abort.abort();
  _abort=new AbortController();
  document.getElementById('chat-btn').disabled=true;
  document.getElementById('chat-stop').style.display='';
  const el=document.createElement('div'); el.className='sse-stream';
  document.getElementById('res-chat').innerHTML='';
  document.getElementById('res-chat').appendChild(el);
  let toolsHtml='',ans='',gotSid='';
  const t0=performance.now();

  function render(cur){
    el.innerHTML=
      (toolsHtml||'')+
      (ans?`<div class="sse-answer mt-2">${esc(ans)}${cur?'<span class="sse-cur"></span>':''}</div>`:'')+
      (gotSid?`<div class="sse-sid">session_id: ${gotSid} <button onclick="useSid('${gotSid}')" style="margin-left:8px;padding:1px 7px;border-radius:4px;font-size:.63rem;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.25);color:#818cf8;cursor:pointer">Use</button></div>`:'');
  }

  try {
    const r=await fetch(U('/chat'),{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:msg,...(sid?{session_id:sid}:{})}),signal:_abort.signal});
    if(!r.ok){
      const err=await r.json().catch(()=>({detail:r.statusText}));
      document.getElementById('res-chat').innerHTML=meta(Math.round(performance.now()-t0),'error')+errWithRetry(err.detail||JSON.stringify(err),'runChat()');
      return;
    }
    const reader=r.body.getReader(),dec=new TextDecoder(); let buf='';
    render(true);
    while(true){
      const{done,value}=await reader.read(); if(done)break;
      buf+=dec.decode(value,{stream:true});
      const lines=buf.split('\n'); buf=lines.pop();
      for(const line of lines){
        if(!line.startsWith('data: '))continue;
        let ev; try{ev=JSON.parse(line.slice(6));}catch{continue;}
        if(ev.type==='tool_call'){
          toolsHtml+=`<div class="sse-tool"><span style="color:#fbbf24;font-size:.7rem;font-weight:700;flex-shrink:0;margin-top:1px">⚙</span><div><div style="color:#fbbf24;font-family:'JetBrains Mono',monospace;font-weight:600;font-size:.7rem">${esc(ev.tool)}</div><div style="color:#78716c;font-family:'JetBrains Mono',monospace;font-size:.66rem;line-height:1.5;white-space:pre-wrap">${esc(JSON.stringify(ev.input,null,2))}</div></div></div>`;
          render(true);
        } else if(ev.type==='token'){ans+=ev.text;render(true);}
        else if(ev.type==='session_id'){
          gotSid=ev.session_id;
          document.getElementById('chat-sid').value=ev.session_id;
          document.getElementById('hist-sid').value=ev.session_id;
          render(true);
        } else if(ev.type==='done'){
          const ms=Math.round(performance.now()-t0); render(false);
          const m=document.createElement('div');
          m.innerHTML=meta(ms,`${(ev.messages||[]).length} messages in session`);
          document.getElementById('res-chat').insertBefore(m,el);
        }
      }
    }
  } catch(e){if(e.name!=='AbortError')document.getElementById('res-chat').innerHTML=errWithRetry(e.message,'runChat()');}
  finally{
    document.getElementById('chat-btn').disabled=false;
    document.getElementById('chat-stop').style.display='none';
    _abort=null; render(false);
  }
}

function stopChat(){if(_abort)_abort.abort();}
function useSid(id){document.getElementById('chat-sid').value=id;document.getElementById('hist-sid').value=id;}

async function runHistory(){
  const sid=document.getElementById('hist-sid').value.trim();
  if(!sid){document.getElementById('res-history').innerHTML='<div class="err-box">Enter a session_id. Run /chat first to get one.</div>';return;}
  document.getElementById('res-history').innerHTML=spin();
  const t0=performance.now();
  try {
    const r=await fetch(U(`/sessions/${encodeURIComponent(sid)}/history`));
    const j=await r.json(); const ms=Math.round(performance.now()-t0);
    if(!r.ok){document.getElementById('res-history').innerHTML=meta(ms,'error')+errWithRetry(j.detail||JSON.stringify(j),'runHistory()');return;}
    const msgs=j.messages||[];
    const rows=msgs.map(m=>{
      const role=m.role||'?';
      const content=typeof m.content==='string'?m.content:JSON.stringify(m.content);
      const rc=role==='user'?'#a5b4fc':role==='assistant'?'#34d399':'#fbbf24';
      return `<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04)"><span style="font-size:.67rem;font-family:'JetBrains Mono',monospace;font-weight:600;color:${rc}">${role}</span><p style="font-size:.75rem;color:#d4d4d8;line-height:1.55;margin-top:3px;white-space:pre-wrap">${esc(content.slice(0,600)+(content.length>600?'…':''))}</p></div>`;
    }).join('');
    document.getElementById('res-history').innerHTML=
      meta(ms,`${msgs.length} message${msgs.length!==1?'s':''}`)+
      `<div style="border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:8px 14px;max-height:300px;overflow-y:auto">${rows||'<p style="color:#52525b;font-size:.75rem">No messages found.</p>'}</div>`+
      rawJson(j);
  } catch(e){document.getElementById('res-history').innerHTML=errBox(e.message);}
}

document.getElementById('chat-msg').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.metaKey||e.ctrlKey))runChat();});
