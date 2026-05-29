const state = {
  tape: [],
  apiToken: localStorage.getItem('pump_sniper_api_token') || ''
};

const els = {
  mode: document.getElementById('mode'),
  decision: document.getElementById('decision'),
  score: document.getElementById('score'),
  pnl: document.getElementById('pnl'),
  tokenName: document.getElementById('tokenName'),
  connectionStatus: document.getElementById('connectionStatus'),
  signals: document.getElementById('signals'),
  tokenStats: document.getElementById('tokenStats'),
  eventTape: document.getElementById('eventTape'),
  chart: document.getElementById('priceChart'),
  runSetupForm: document.getElementById('runSetupForm'),
  validateSetup: document.getElementById('validateSetup'),
  setupPreview: document.getElementById('setupPreview'),
  apiToken: document.getElementById('apiToken')
};

const ctx = els.chart.getContext('2d');

if (els.apiToken && state.apiToken) {
  els.apiToken.value = state.apiToken;
}

function setStatus(text) {
  els.connectionStatus.textContent = text;
}

function previewConfig(title, payload) {
  if (!els.setupPreview) return;
  els.setupPreview.textContent = `${title}\n${JSON.stringify(payload, null, 2)}`;
}

function getAuthHeaders() {
  const token = els.apiToken?.value?.trim() || state.apiToken;
  const headers = { 'Content-Type': 'application/json' };

  if (token) {
    state.apiToken = token;
    localStorage.setItem('pump_sniper_api_token', token);
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

function readRunConfigForm() {
  return {
    betUsd: Number(document.getElementById('betUsd').value),
    buySol: Number(document.getElementById('buySol').value),
    targetProfitPercent: Number(document.getElementById('targetProfitPercent').value),
    stopLossPercent: Number(document.getElementById('stopLossPercent').value),
    takeProfitPercent: Number(document.getElementById('takeProfitPercent').value),
    slippagePercent: Number(document.getElementById('slippagePercent').value),
    minScore: Number(document.getElementById('minScore').value),
    maxDevWalletPercent: Number(document.getElementById('maxDevWalletPercent').value),
    maxSnipers: Number(document.getElementById('maxSnipers').value),
    maxTopTenPercent: Number(document.getElementById('maxTopTenPercent').value),
    rounds: Number(document.getElementById('rounds').value),
    requestedMode: document.getElementById('requestedMode').value,
    realismMode: document.getElementById('realismMode').value,
    keepSeedOnly: document.getElementById('keepSeedOnly').checked,
    harshMode: document.getElementById('harshMode').checked
  };
}

function fillRunConfigForm(config) {
  if (!config) return;

  Object.entries(config).forEach(([key, value]) => {
    const input = document.getElementById(key);
    if (!input || key === 'updatedAt') return;

    if (input.type === 'checkbox') input.checked = Boolean(value);
    else input.value = value;
  });
}

async function callRunConfig(path, options = {}) {
  const res = await fetch(`/api/protected/run-config${path}`, {
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.headers || {})
    }
  });

  const data = await res.json().catch(() => ({ ok: false, error: 'Invalid JSON response' }));
  if (!res.ok) throw new Error(data?.error || data?.message || `Request failed: ${res.status}`);
  return data;
}

async function loadSavedRunConfig() {
  try {
    const data = await callRunConfig('');
    fillRunConfigForm(data.config);
    previewConfig('Loaded saved run config', data);
  } catch (err) {
    previewConfig('Run config not loaded. Login/API token may be required.', { error: String(err) });
  }
}

async function validateRunConfig() {
  const config = readRunConfigForm();

  try {
    const data = await callRunConfig('/validate', {
      method: 'POST',
      body: JSON.stringify(config)
    });
    previewConfig('Validation passed', data);
    return { ok: true, data };
  } catch (err) {
    previewConfig('Validation failed', { error: String(err), config });
    return { ok: false, error: err };
  }
}

async function saveRunConfig() {
  const config = readRunConfigForm();

  try {
    const data = await callRunConfig('', {
      method: 'POST',
      body: JSON.stringify(config)
    });
    previewConfig('Run config saved', data);
    return { ok: true, data };
  } catch (err) {
    previewConfig('Run config save failed', { error: String(err), config });
    return { ok: false, error: err };
  }
}

function bindControllerControls() {
  els.validateSetup?.addEventListener('click', () => validateRunConfig());

  els.runSetupForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = await saveRunConfig();

    if (result.ok) {
      pushTape({
        token: 'RUN_CONFIG',
        decision: 'SAVED',
        exitReason: 'awaiting runtime pickup',
        score: result.data.config?.minScore ?? '-'
      });
    }
  });
}

function drawChart(pricePath = [], volumePath = []) {
  ctx.clearRect(0, 0, els.chart.width, els.chart.height);

  ctx.strokeStyle = '#4da3ff';
  ctx.lineWidth = 3;
  ctx.beginPath();

  if (!pricePath.length) {
    ctx.fillStyle = '#7f8db3';
    ctx.font = '20px sans-serif';
    ctx.fillText('Waiting for bot telemetry...', 40, 80);
    return;
  }

  const max = Math.max(...pricePath.map(p => p[1]));
  const min = Math.min(...pricePath.map(p => p[1]));

  pricePath.forEach((point, index) => {
    const x = (index / Math.max(1, pricePath.length - 1)) * (els.chart.width - 60) + 30;
    const y = els.chart.height - (((point[1] - min) / ((max - min) || 1)) * 300 + 60);

    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.stroke();

  volumePath.forEach((vol, index) => {
    const x = (index / Math.max(1, volumePath.length)) * (els.chart.width - 60) + 30;
    const h = Math.max(1, Number(vol) * 20);
    ctx.fillStyle = 'rgba(88, 166, 255, 0.35)';
    ctx.fillRect(x, els.chart.height - h - 10, 8, h);
  });
}

function renderSignals(signals = {}) {
  els.signals.innerHTML = '';

  Object.entries(signals).forEach(([k, v]) => {
    const div = document.createElement('div');
    div.innerHTML = `<strong>${k}</strong><br>${v}`;
    els.signals.appendChild(div);
  });
}

function renderTokenStats(data) {
  const stats = {
    pressure: data.pressure,
    score: data.score,
    exitReason: data.exitReason,
    exitMult: data.exitMult,
    activeWallet: data.activeWallet,
    withdrawn: data.withdrawn,
    holders: data.holders,
    snipers: data.snipers,
    devWalletPercent: data.devWalletPercent,
    topTenPercent: data.topTenPercent,
    marketCap: data.marketCap,
    volume: data.volume
  };

  els.tokenStats.innerHTML = '';

  Object.entries(stats).forEach(([k, v]) => {
    const div = document.createElement('div');
    div.innerHTML = `<strong>${k}</strong><br>${v ?? '-'}`;
    els.tokenStats.appendChild(div);
  });
}

function pushTape(entry) {
  state.tape.unshift(entry);
  state.tape = state.tape.slice(0, 40);

  els.eventTape.innerHTML = '';

  state.tape.forEach((item) => {
    const li = document.createElement('li');
    li.textContent = `${item.token} | ${item.decision} | ${item.exitReason || 'monitoring'} | score ${item.score}`;
    els.eventTape.appendChild(li);
  });
}

function updateDashboard(data) {
  setStatus('telemetry online');
  els.mode.textContent = data.mode || '-';
  els.decision.textContent = data.decision || '-';
  els.score.textContent = data.score || '-';
  els.pnl.textContent = data.pnlUsd || '$0';
  els.tokenName.textContent = data.token || 'unknown token';

  renderSignals(data.signals || {});
  renderTokenStats(data);
  drawChart(data.pricePath || [], data.volumePath || []);
  pushTape(data);
}

function connectFeed() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${protocol}://${location.host}/ws`);

  ws.onopen = () => setStatus('connected to websocket');

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'telemetry') updateDashboard(data.payload);
      else pushTape({ token: data.type || 'WS', decision: 'EVENT', exitReason: data.msg || 'message', score: '-' });
    } catch {
      pushTape({ token: 'WS', decision: 'RAW', exitReason: event.data, score: '-' });
    }
  };

  ws.onerror = () => setStatus('websocket unavailable');
  ws.onclose = () => setStatus('websocket closed');
}

bindControllerControls();
loadSavedRunConfig();
connectFeed();
