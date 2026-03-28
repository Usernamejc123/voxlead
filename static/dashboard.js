// ─── State ───────────────────────────────────────────────────────────────────
let allCampaigns = [];
let activeFilter = 'all';
let _authToken   = null; // base64(user:pass) set on login

const STATUS_MAP  = {0:'Draft', 1:'Active', 2:'Paused', 3:'Completed', 4:'Error'};
const STATUS_CLS  = {0:'badge-draft', 1:'badge-active', 2:'badge-paused', 3:'badge-completed', 4:'badge-error'};

// ─── Toast ───────────────────────────────────────────────────────────────────
function toast(msg, type='info') {
  const c = document.getElementById('toastContainer');
  const icons = {success:'✅', error:'❌', info:'💬'};
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.innerHTML = `<span class="toast-icon">${icons[type]||'ℹ️'}</span><span class="toast-msg">${msg}</span>`;
  c.appendChild(t);
  setTimeout(() => {
    t.style.cssText += 'opacity:0;transform:translateX(12px);transition:all .3s';
    setTimeout(() => t.remove(), 300);
  }, 3500);
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
function showLogin(msg) {
  const ov = document.getElementById('loginOverlay');
  ov.style.display = 'flex';
  if (msg) {
    const e = document.getElementById('loginErr');
    e.textContent = msg; e.style.display = 'block';
  }
  setTimeout(() => document.getElementById('loginPass').focus(), 80);
}
function hideLogin() {
  document.getElementById('loginOverlay').style.display = 'none';
}

async function login() {
  const u    = document.getElementById('loginUser').value.trim();
  const p    = document.getElementById('loginPass').value;
  const errEl = document.getElementById('loginErr');
  const btn  = document.getElementById('loginBtn');
  errEl.style.display = 'none';
  if (!u || !p) { errEl.textContent = 'Enter username and password.'; errEl.style.display='block'; return; }
  btn.textContent = 'Signing in…'; btn.disabled = true;
  try {
    const token = btoa(u + ':' + p);
    const r = await fetch('/api/campaigns', {headers:{'Authorization':'Basic ' + token}});
    if (r.status === 401) {
      errEl.textContent = 'Invalid credentials — check your password.';
      errEl.style.display = 'block';
    } else {
      _authToken = token;
      hideLogin();
      const data = await r.json();
      allCampaigns = data.items || [];
      updateStats(allCampaigns);
      renderCampaigns();
      populateSelector(allCampaigns);
      checkStatus();
    }
  } catch(e) {
    errEl.textContent = 'Connection error: ' + e.message;
    errEl.style.display = 'block';
  } finally {
    btn.textContent = 'Sign In'; btn.disabled = false;
  }
}

// ─── API ─────────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const headers = {'Content-Type':'application/json'};
  if (_authToken) headers['Authorization'] = 'Basic ' + _authToken;
  const opts = {method, headers};
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  if (r.status === 401) { showLogin('Session expired — please sign in again.'); throw new Error('401 Unauthorized'); }
  return r.json();
}

// ─── Health check ─────────────────────────────────────────────────────────────
async function checkStatus() {
  try {
    const r = await fetch('/api/health');
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (r.ok) {
      dot.style.cssText = 'background:#10b981;box-shadow:0 0 6px #10b981';
      txt.textContent = 'All systems go';
    } else {
      dot.style.cssText = 'background:#f59e0b';
      txt.textContent = 'Degraded';
    }
  } catch(e) {
    document.getElementById('statusDot').style.cssText = 'background:#ef4444;box-shadow:none';
    document.getElementById('statusText').textContent = 'Offline';
  }
}

// ─── Load campaigns ───────────────────────────────────────────────────────────
async function loadCampaigns() {
  document.getElementById('campaignsBody').innerHTML =
    '<tr><td colspan="4"><div class="empty-state"><span class="empty-icon">⏳</span><div class="empty-title">Loading…</div></div></td></tr>';
  try {
    const data = await api('GET', '/api/campaigns');
    allCampaigns = data.items || [];
    updateStats(allCampaigns);
    renderCampaigns();
    populateSelector(allCampaigns);
  } catch(e) {
    document.getElementById('campaignsBody').innerHTML =
      `<tr><td colspan="4"><div class="empty-state"><span class="empty-icon">⚠️</span><div class="empty-title">Failed to load</div><div class="empty-text">${esc(e.message)}</div></div></td></tr>`;
  }
}

function updateStats(c) {
  document.getElementById('statTotal').textContent  = c.length;
  document.getElementById('statActive').textContent = c.filter(x=>x.status===1).length;
  document.getElementById('statDraft').textContent  = c.filter(x=>x.status===0).length;
  document.getElementById('statPaused').textContent = c.filter(x=>x.status===2).length;
}

function renderCampaigns() {
  const tbody  = document.getElementById('campaignsBody');
  const q      = document.getElementById('searchInput').value.toLowerCase();
  let items    = allCampaigns;

  if (activeFilter==='active')  items = items.filter(c=>c.status===1);
  else if (activeFilter==='draft')   items = items.filter(c=>c.status===0);
  else if (activeFilter==='paused')  items = items.filter(c=>c.status===2);
  if (q) items = items.filter(c=>(c.name||'').toLowerCase().includes(q));

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">
      <span class="empty-icon">📭</span>
      <div class="empty-title">No campaigns found</div>
      <div class="empty-text">Create a new campaign or adjust your filter.</div>
    </div></td></tr>`;
    return;
  }

  tbody.innerHTML = items.map(c => {
    const status  = STATUS_MAP[c.status] ?? 'Unknown';
    const cls     = STATUS_CLS[c.status] ?? 'badge-draft';
    const date    = c.timestamp_created
      ? new Date(c.timestamp_created).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})
      : '—';
    const launch  = c.status===0 ? `<button class="btn btn-sm btn-green" onclick="launchCampaign('${c.id}')">▶ Launch</button>` : '';
    const pause   = c.status===1 ? `<button class="btn btn-sm btn-orange" onclick="pauseCampaign('${c.id}')">⏸ Pause</button>` : '';
    const copy    = `<button class="btn btn-sm btn-ghost" onclick="copyId('${c.id}','${esc(c.name)}')" title="Copy ID">⎘ ID</button>`;
    return `<tr>
      <td style="font-weight:500">${esc(c.name)}</td>
      <td><span class="badge ${cls}"><span class="badge-dot"></span>${status}</span></td>
      <td class="text-muted">${date}</td>
      <td><div class="actions-cell">${launch}${pause}${copy}</div></td>
    </tr>`;
  }).join('');
}

function populateSelector(campaigns) {
  const sel = document.getElementById('uploadCampaignId');
  sel.innerHTML = campaigns.length
    ? campaigns.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')
    : '<option value="">No campaigns — create one first</option>';
}

// ─── Filter ───────────────────────────────────────────────────────────────────
function filterTable(f, el) {
  activeFilter = f;
  document.querySelectorAll('#filterTabs .tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  renderCampaigns();
}

// ─── Campaign actions ─────────────────────────────────────────────────────────
async function launchCampaign(id) {
  if (!confirm('Launch this campaign? Emails will start sending immediately.')) return;
  try {
    const r = await api('POST', `/api/campaigns/${id}/launch`);
    if (r.error||r._error) { toast('Launch failed: '+(r.error||JSON.stringify(r.detail)), 'error'); return; }
    toast('Campaign launched! 🚀 Emails are sending.', 'success');
    await loadCampaigns();
  } catch(e) { toast(e.message, 'error'); }
}

async function pauseCampaign(id) {
  try {
    const r = await api('POST', `/api/campaigns/${id}/pause`);
    if (r.error||r._error) { toast('Pause failed: '+(r.error||JSON.stringify(r.detail)), 'error'); return; }
    toast('Campaign paused.', 'info');
    await loadCampaigns();
  } catch(e) { toast(e.message, 'error'); }
}

async function copyId(id, name) {
  try { await navigator.clipboard.writeText(id); } catch(e) {}
  toast(`Copied ID for "${name}"`, 'info');
}

// ─── Modal ────────────────────────────────────────────────────────────────────
function openModal(e) {
  if(e) e.preventDefault();
  document.getElementById('newCampaignModal').classList.add('open');
  document.getElementById('modalStatus').style.display='none';
  document.getElementById('createBtn').textContent='Create Campaign';
  document.getElementById('createBtn').disabled=false;
  setTimeout(()=>document.getElementById('newCampaignName').focus(), 60);
}
function closeModal() {
  document.getElementById('newCampaignModal').classList.remove('open');
  document.getElementById('newCampaignName').value='';
}

async function createCampaign() {
  const name = document.getElementById('newCampaignName').value.trim();
  if (!name) { toast('Enter a campaign name', 'error'); return; }

  const btn    = document.getElementById('createBtn');
  const status = document.getElementById('modalStatus');
  btn.textContent = 'Creating…'; btn.disabled = true;
  status.style.display = 'none';

  try {
    const r = await api('POST', '/api/campaigns', {name});
    if (r.error||r._error) {
      status.textContent = 'Error: '+(r.error||JSON.stringify(r));
      status.style.display = 'block';
      btn.textContent='Create Campaign'; btn.disabled=false;
      return;
    }
    closeModal();
    toast(`Campaign "${name}" created! 🎉`, 'success');
    await loadCampaigns();
  } catch(e) {
    status.textContent = e.message; status.style.display='block';
    btn.textContent='Create Campaign'; btn.disabled=false;
  }
}

// ─── File upload ──────────────────────────────────────────────────────────────
function onFileSelect(input) {
  const f = input.files[0];
  document.getElementById('fileName').textContent = f
    ? `📄 ${f.name} · ${(f.size/1024).toFixed(1)} KB`
    : '';
}

// Drag-and-drop
const dz = document.getElementById('dropZone');
['dragenter','dragover'].forEach(e => dz.addEventListener(e, ev => {
  ev.preventDefault(); dz.classList.add('dragover');
}));
['dragleave','drop'].forEach(e => dz.addEventListener(e, ev => {
  ev.preventDefault(); dz.classList.remove('dragover');
}));
dz.addEventListener('drop', ev => {
  const file = ev.dataTransfer.files[0];
  if (file && file.name.endsWith('.csv')) {
    const dt = new DataTransfer();
    dt.items.add(file);
    document.getElementById('csvFile').files = dt.files;
    onFileSelect(document.getElementById('csvFile'));
  } else {
    toast('Please drop a .csv file', 'error');
  }
});

async function uploadLeads() {
  const campaignId = document.getElementById('uploadCampaignId').value;
  const file       = document.getElementById('csvFile').files[0];
  const statusEl   = document.getElementById('uploadStatus');
  const btn        = document.getElementById('uploadBtn');
  const bar        = document.getElementById('progressBar');
  const fill       = document.getElementById('progressFill');

  if (!campaignId) { toast('Select a campaign first', 'error'); return; }
  if (!file)       { toast('Select a CSV file first', 'error'); return; }

  btn.disabled=true; bar.style.display='block'; fill.style.width='8%';
  statusEl.textContent = 'Reading CSV…';

  const csv = await file.text();
  statusEl.textContent = '✨ Generating icebreakers with Claude…';
  fill.style.width = '45%';

  try {
    fill.style.width = '75%';
    const r = await api('POST', '/api/upload-leads', {campaign_id:campaignId, csv});
    fill.style.width = '100%';

    if (r.error||r._error) {
      toast('Upload failed: '+(r.error||JSON.stringify(r.detail)), 'error');
      statusEl.textContent = '';
    } else {
      toast(`✨ ${r.leads_processed} leads uploaded with AI icebreakers!`, 'success');
      statusEl.textContent = `${r.leads_processed} leads uploaded successfully`;
      document.getElementById('csvFile').value='';
      document.getElementById('fileName').textContent='';
      await loadCampaigns();
    }
  } catch(e) {
    toast(e.message, 'error');
    statusEl.textContent='';
  } finally {
    btn.disabled = false;
    setTimeout(()=>{ bar.style.display='none'; fill.style.width='0%'; }, 1600);
  }
}

// ─── Nav helpers ──────────────────────────────────────────────────────────────
function scrollTop(e){ if(e)e.preventDefault(); window.scrollTo({top:0,behavior:'smooth'}); }
function scrollToUpload(e){ if(e)e.preventDefault(); document.getElementById('uploadCard').scrollIntoView({behavior:'smooth'}); }
function scrollToCampaigns(e){ if(e)e.preventDefault(); document.getElementById('campaignsCard').scrollIntoView({behavior:'smooth'}); }

function refreshAll() {
  loadCampaigns();
  checkStatus();
  toast('Refreshed', 'info');
}

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Close modal on backdrop click ────────────────────────────────────────────
document.getElementById('newCampaignModal').addEventListener('click', function(e){
  if(e.target===this) closeModal();
});

// ─── Init ─────────────────────────────────────────────────────────────────────
// Always show login first — login() will authenticate and load data on success
showLogin();
