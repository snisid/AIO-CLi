const state = {
  mode: localStorage.getItem('aio.mode') || 'Supervised',
  router: localStorage.getItem('aio.router') || 'Intelligent',
  reasoning: localStorage.getItem('aio.reasoning') || 'High',
  shell: localStorage.getItem('aio.shell') || 'Demander avant exécution',
  failover: localStorage.getItem('aio.failover') !== 'false',
  browser: localStorage.getItem('aio.browser') !== 'false',
  mcp: localStorage.getItem('aio.mcp') !== 'false',
  longrun: localStorage.getItem('aio.longrun') !== 'false'
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function saveState() {
  Object.entries(state).forEach(([key, value]) => localStorage.setItem(`aio.${key}`, String(value)));
}

function refreshChips() {
  $('#mode-chip').textContent = `Mode : ${state.mode}`;
  $('#model-chip').textContent = `Router : ${state.router}`;
}

function openModal(name) {
  const backdrop = $('#modal-backdrop');
  backdrop.hidden = false;
  $$('[data-modal-panel]').forEach((panel) => { panel.hidden = panel.dataset.modalPanel !== name; });
  if (name === 'settings') {
    $('#setting-mode').value = state.mode;
    $('#setting-router').value = state.router;
    $('#setting-reasoning').value = state.reasoning;
    $('#setting-shell').value = state.shell;
    $('#setting-failover').checked = state.failover;
    $('#setting-browser').checked = state.browser;
    $('#setting-mcp').checked = state.mcp;
    $('#setting-longrun').checked = state.longrun;
  }
}

function closeModal() { $('#modal-backdrop').hidden = true; }

function addLog(message) {
  const log = $('#runtime-log');
  const row = document.createElement('div');
  row.innerHTML = `<span>•</span> ${message}`;
  log.prepend(row);
  while (log.children.length > 8) log.lastElementChild.remove();
}

function addHistory(prompt) {
  const list = $('#history-list');
  const empty = list.querySelector('.empty');
  if (empty) empty.remove();
  const item = document.createElement('div');
  item.className = 'history-item';
  item.textContent = prompt;
  list.prepend(item);
}

async function checkRuntime() {
  try {
    const [healthRes, statusRes] = await Promise.all([
      fetch('/health', { cache: 'no-store' }),
      fetch('/api/status', { cache: 'no-store' })
    ]);
    if (!healthRes.ok || !statusRes.ok) throw new Error('API unavailable');
    const health = await healthRes.json();
    const status = await statusRes.json();
    $('#global-status').innerHTML = `<span></span>${health.status === 'ok' ? 'Runtime online' : 'Runtime dégradé'}`;
    $('#metric-runtime')?.replaceWith?.($('#metric-runtime'));
    $('#health-api')?.replaceChildren(document.createTextNode('OK'));
    $('#health-dashboard')?.replaceChildren(document.createTextNode('OK'));
    $('#hub-status').textContent = 'READY';
  } catch (error) {
    $('#global-status').innerHTML = '<span></span>Runtime indisponible';
    $('#health-api')?.replaceChildren(document.createTextNode('ERROR'));
    $('#health-dashboard')?.replaceChildren(document.createTextNode('ERROR'));
    $('#hub-status').textContent = 'DEGRADED';
  }
  try {
    const assets = await Promise.all([
      fetch('/assets/logo/ma-cli-animated.svg', { cache: 'no-store' }),
      fetch('/ui/dashboard/dashboard.css', { cache: 'no-store' }),
      fetch('/ui/dashboard/dashboard.js', { cache: 'no-store' })
    ]);
    $('#health-assets')?.replaceChildren(document.createTextNode(assets.every((r) => r.ok) ? 'OK' : 'ERROR'));
  } catch {
    $('#health-assets')?.replaceChildren(document.createTextNode('ERROR'));
  }
}

function updateLineNumbers() {
  const editor = $('#code-editor');
  const count = editor.value.split('\n').length;
  $('#line-numbers').textContent = Array.from({ length: count }, (_, i) => String(i + 1)).join('\n');
}

function updateCursor() {
  const editor = $('#code-editor');
  const before = editor.value.slice(0, editor.selectionStart);
  const line = before.split('\n').length;
  const col = before.length - before.lastIndexOf('\n');
  $('#cursor-info').textContent = `Ln ${line}, Col ${col}`;
}

function configureMultiScreen() {
  const origin = window.location.origin;
  const specs = [
    ['prompt', 'AIO-CLi · Prompt'],
    ['code', 'AIO-CLi · Code'],
    ['hub', 'AIO-CLi · Hub']
  ];
  specs.forEach(([panel, title]) => {
    const popup = window.open(`${origin}/dashboard?panel=${panel}`, `aio-${panel}`, 'width=900,height=900,resizable=yes,scrollbars=yes');
    if (popup) {
      try { popup.document.title = title; } catch {}
      popup.focus();
    }
  });
  addLog('Mode 3 écrans demandé — déplacez chaque fenêtre sur son moniteur.');
}

function applyPanelQuery() {
  const panel = new URLSearchParams(window.location.search).get('panel');
  if (panel && ['prompt', 'code', 'hub'].includes(panel)) {
    document.body.classList.add('single-panel');
    $$('.panel').forEach((el) => { el.classList.toggle('is-selected', el.dataset.role === panel); });
  }
}

function bind() {
  refreshChips();
  applyPanelQuery();
  updateLineNumbers();

  $('#layout-toggle').addEventListener('click', () => {
    document.body.classList.toggle('single-panel');
    $$('.panel').forEach((p) => p.style.display = document.body.classList.contains('single-panel') && !p.classList.contains('is-selected') ? 'none' : 'flex');
  });
  $('#detach-all').addEventListener('click', configureMultiScreen);
  $$('[data-modal]').forEach((button) => button.addEventListener('click', () => openModal(button.dataset.modal)));
  $$('[data-close-modal]').forEach((button) => button.addEventListener('click', closeModal));
  $('#modal-backdrop').addEventListener('click', (event) => { if (event.target === event.currentTarget) closeModal(); });

  $('#save-settings').addEventListener('click', () => {
    state.mode = $('#setting-mode').value;
    state.router = $('#setting-router').value;
    state.reasoning = $('#setting-reasoning').value;
    state.shell = $('#setting-shell').value;
    state.failover = $('#setting-failover').checked;
    state.browser = $('#setting-browser').checked;
    state.mcp = $('#setting-mcp').checked;
    state.longrun = $('#setting-longrun').checked;
    saveState();
    refreshChips();
    $('#settings-saved').textContent = 'Paramètres enregistrés ✓';
    addLog(`Configuration mise à jour : ${state.mode} / ${state.router} / reasoning ${state.reasoning}`);
    setTimeout(closeModal, 300);
  });

  $('#run-task').addEventListener('click', () => {
    const prompt = $('#prompt-input').value.trim();
    if (!prompt) { $('#prompt-input').focus(); return; }
    addHistory(prompt);
    $('#execution-state').textContent = 'RUNNING';
    $('#hub-status').textContent = 'RUNNING';
    $('#progress-bar').style.width = '35%';
    addLog(`Tâche reçue : ${prompt.slice(0, 100)}`);
    setTimeout(() => { $('#progress-bar').style.width = '70%'; addLog('Planner → agents spécialisés → validation'); }, 500);
    setTimeout(() => { $('#progress-bar').style.width = '100%'; $('#execution-state').textContent = 'READY'; $('#hub-status').textContent = 'READY'; addLog('Cycle UI terminé — runtime backend prêt à prendre le relais.'); }, 1100);
  });
  $('#prompt-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('#run-task').click(); }
  });
  $('#clear-prompt').addEventListener('click', () => { $('#prompt-input').value = ''; $('#prompt-input').focus(); });
  $('#clear-history').addEventListener('click', () => { $('#history-list').innerHTML = '<div class="empty">Aucune tâche locale.</div>'; });

  $('#code-editor').addEventListener('input', () => { updateLineNumbers(); $('#save-state').textContent = 'Modifications locales non sauvegardées'; });
  $('#code-editor').addEventListener('keyup', updateCursor);
  $('#code-editor').addEventListener('click', updateCursor);
  $('#save-code').addEventListener('click', () => { $('#save-state').textContent = 'État local enregistré ✓'; addLog('Éditeur : état local enregistré.'); });
  $('#format-code').addEventListener('click', () => { addLog('Éditeur : formatage demandé.'); });

  window.addEventListener('storage', (event) => {
    if (event.key?.startsWith('aio.')) {
      const key = event.key.slice(4);
      if (key in state) state[key] = event.newValue === 'true' ? true : event.newValue === 'false' ? false : event.newValue;
      refreshChips();
    }
  });

  setInterval(checkRuntime, 30000);
  checkRuntime();
  $('#runtime-clock').textContent = new Date().toLocaleTimeString('fr-FR');
  setInterval(() => { $('#runtime-clock').textContent = new Date().toLocaleTimeString('fr-FR'); }, 1000);
}

document.addEventListener('DOMContentLoaded', bind);
