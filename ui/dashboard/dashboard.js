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

function setText(selector, value) {
  const element = $(selector);
  if (element) element.textContent = value;
  return element;
}

function saveState() {
  Object.entries(state).forEach(([key, value]) => localStorage.setItem(`aio.${key}`, String(value)));
}

function refreshChips() {
  setText('#mode-chip', `Mode : ${state.mode}`);
  setText('#model-chip', `Router : ${state.router}`);
}

function openModal(name) {
  const backdrop = $('#modal-backdrop');
  if (!backdrop) return;
  backdrop.hidden = false;
  $$('[data-modal-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.modalPanel !== name;
  });
  if (name !== 'settings') return;

  const values = [
    ['#setting-mode', state.mode, 'value'],
    ['#setting-router', state.router, 'value'],
    ['#setting-reasoning', state.reasoning, 'value'],
    ['#setting-shell', state.shell, 'value'],
    ['#setting-failover', state.failover, 'checked'],
    ['#setting-browser', state.browser, 'checked'],
    ['#setting-mcp', state.mcp, 'checked'],
    ['#setting-longrun', state.longrun, 'checked']
  ];
  values.forEach(([selector, value, property]) => {
    const element = $(selector);
    if (element) element[property] = value;
  });
}

function closeModal() {
  const backdrop = $('#modal-backdrop');
  if (backdrop) backdrop.hidden = true;
}

function addLog(message) {
  const log = $('#runtime-log');
  if (!log) return;
  const row = document.createElement('div');
  const marker = document.createElement('span');
  marker.textContent = '•';
  row.append(marker, ` ${message}`);
  log.prepend(row);
  while (log.children.length > 8) log.lastElementChild.remove();
}

function addHistory(prompt) {
  const list = $('#history-list');
  if (!list) return;
  list.querySelector('.empty')?.remove();
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
    const online = health.status === 'ok';

    const statusPill = $('#global-status');
    if (statusPill) {
      statusPill.innerHTML = `<span></span>${online ? 'Runtime online' : 'Runtime dégradé'}`;
    }
    setText('#health-api', 'OK');
    setText('#health-dashboard', 'OK');
    setText('#metric-runtime', online ? 'ONLINE' : 'DEGRADED');
    setText('#metric-deployment', status.deployment || 'vercel');
    setText('#hub-status', online ? 'READY' : 'DEGRADED');
    setText('#execution-state', online ? 'IDLE' : 'DEGRADED');
  } catch (error) {
    const statusPill = $('#global-status');
    if (statusPill) statusPill.innerHTML = '<span></span>Runtime indisponible';
    setText('#health-api', 'ERROR');
    setText('#health-dashboard', 'ERROR');
    setText('#metric-runtime', 'ERROR');
    setText('#hub-status', 'DEGRADED');
    setText('#execution-state', 'ERROR');
  }

  try {
    const assets = await Promise.all([
      fetch('/assets/logo/ma-cli-animated.svg', { cache: 'no-store' }),
      fetch('/ui/dashboard/dashboard.css', { cache: 'no-store' }),
      fetch('/ui/dashboard/dashboard.js', { cache: 'no-store' })
    ]);
    setText('#health-assets', assets.every((res) => res.ok) ? 'OK' : 'ERROR');
  } catch {
    setText('#health-assets', 'ERROR');
  }
}

function updateLineNumbers() {
  const editor = $('#code-editor');
  const numbers = $('#line-numbers');
  if (!editor || !numbers) return;
  numbers.textContent = Array.from(
    { length: editor.value.split('\n').length },
    (_, i) => String(i + 1)
  ).join('\n');
}

function updateCursor() {
  const editor = $('#code-editor');
  const cursor = $('#cursor-info');
  if (!editor || !cursor) return;
  const before = editor.value.slice(0, editor.selectionStart);
  const line = before.split('\n').length;
  const col = before.length - before.lastIndexOf('\n');
  cursor.textContent = `Ln ${line}, Col ${col}`;
}

function setSinglePanel(panel) {
  document.body.classList.add('single-panel');
  $$('.panel').forEach((item) => {
    item.classList.toggle('is-selected', item.dataset.role === panel);
  });
}

function configureMultiScreen() {
  const origin = window.location.origin;
  const opened = [];
  ['prompt', 'code', 'hub'].forEach((panel) => {
    const popup = window.open(
      `${origin}/dashboard?panel=${panel}`,
      `aio-${panel}`,
      'width=1000,height=900,resizable=yes,scrollbars=yes'
    );
    if (popup) {
      popup.focus();
      opened.push(panel);
    }
  });
  addLog(opened.length === 3
    ? 'Mode 3 écrans activé : Prompt / Code / Hub.'
    : 'Mode 3 écrans : certaines fenêtres ont été bloquées par le navigateur.');
}

function applyPanelQuery() {
  const panel = new URLSearchParams(window.location.search).get('panel');
  if (panel && ['prompt', 'code', 'hub'].includes(panel)) setSinglePanel(panel);
}

function bind() {
  refreshChips();
  applyPanelQuery();
  updateLineNumbers();
  updateCursor();

  $('#layout-toggle')?.addEventListener('click', () => {
    if (document.body.classList.contains('single-panel')) {
      document.body.classList.remove('single-panel');
      $$('.panel').forEach((item) => item.classList.remove('is-selected'));
      return;
    }
    setSinglePanel('prompt');
  });

  $('#detach-all')?.addEventListener('click', configureMultiScreen);
  $$('[data-panel]').forEach((button) =>
    button.addEventListener('click', () => setSinglePanel(button.dataset.panel))
  );
  $$('[data-modal]').forEach((button) =>
    button.addEventListener('click', () => openModal(button.dataset.modal))
  );
  $$('[data-close-modal]').forEach((button) =>
    button.addEventListener('click', closeModal)
  );

  $('#modal-backdrop')?.addEventListener('click', (event) => {
    if (event.target === event.currentTarget) closeModal();
  });

  $('#save-settings')?.addEventListener('click', () => {
    const mode = $('#setting-mode');
    const router = $('#setting-router');
    const reasoning = $('#setting-reasoning');
    const shell = $('#setting-shell');
    const failover = $('#setting-failover');
    const browser = $('#setting-browser');
    const mcp = $('#setting-mcp');
    const longrun = $('#setting-longrun');

    if (mode) state.mode = mode.value;
    if (router) state.router = router.value;
    if (reasoning) state.reasoning = reasoning.value;
    if (shell) state.shell = shell.value;
    if (failover) state.failover = failover.checked;
    if (browser) state.browser = browser.checked;
    if (mcp) state.mcp = mcp.checked;
    if (longrun) state.longrun = longrun.checked;

    saveState();
    refreshChips();
    setText('#settings-saved', 'Paramètres enregistrés ✓');
    addLog(`Configuration : ${state.mode} / ${state.router} / reasoning ${state.reasoning}`);
    setTimeout(closeModal, 250);
  });

  $('#run-task')?.addEventListener('click', () => {
    const input = $('#prompt-input');
    const prompt = input?.value.trim() || '';
    if (!prompt) {
      input?.focus();
      return;
    }
    addHistory(prompt);
    setText('#execution-state', 'RUNNING');
    setText('#hub-status', 'RUNNING');
    const progress = $('#progress-bar');
    if (progress) progress.style.width = '25%';
    addLog(`Tâche reçue : ${prompt.slice(0, 100)}`);
    setTimeout(() => {
      if (progress) progress.style.width = '62%';
      addLog('Planner → agents spécialisés → validation');
    }, 500);
    setTimeout(() => {
      if (progress) progress.style.width = '100%';
      setText('#execution-state', 'READY');
      setText('#hub-status', 'READY');
      addLog('Cycle UI terminé.');
    }, 1100);
  });

  $('#prompt-input')?.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      $('#run-task')?.click();
    }
  });

  $('#clear-prompt')?.addEventListener('click', () => {
    const input = $('#prompt-input');
    if (input) {
      input.value = '';
      input.focus();
    }
  });

  $('#clear-history')?.addEventListener('click', () => {
    const list = $('#history-list');
    if (list) list.innerHTML = '<div class="empty">Aucune tâche locale.</div>';
  });

  $('#code-editor')?.addEventListener('input', () => {
    updateLineNumbers();
    setText('#save-state', 'Modifications locales non sauvegardées');
  });
  $('#code-editor')?.addEventListener('keyup', updateCursor);
  $('#code-editor')?.addEventListener('click', updateCursor);
  $('#save-code')?.addEventListener('click', () => {
    setText('#save-state', 'État local enregistré ✓');
    addLog('Éditeur : état local enregistré.');
  });
  $('#format-code')?.addEventListener('click', () => addLog('Éditeur : formatage demandé.'));

  checkRuntime();
  setInterval(checkRuntime, 30000);

  setText('#runtime-clock', new Date().toLocaleTimeString('fr-FR'));
  setInterval(() => {
    setText('#runtime-clock', new Date().toLocaleTimeString('fr-FR'));
  }, 1000);
}

document.addEventListener('DOMContentLoaded', bind);
