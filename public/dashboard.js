const state = {
  tape: []
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
  chart: document.getElementById('priceChart')
};

const ctx = els.chart.getContext('2d');

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
    const x = (index / (pricePath.length - 1)) * (els.chart.width - 60) + 30;
    const y = els.chart.height - (((point[1] - min) / ((max - min) || 1)) * 300 + 60);

    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });

  ctx.stroke();

  volumePath.forEach((vol, index) => {
    const x = (index / volumePath.length) * (els.chart.width - 60) + 30;
    const h = vol * 20;
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
    withdrawn: data.withdrawn
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
  els.connectionStatus.textContent = 'telemetry online';
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

function simulateFeed() {
  const ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = () => {
    els.connectionStatus.textContent = 'connected to websocket';
  };

  ws.onmessage = () => {
    const fake = {
      mode: 'READ ONLY',
      decision: Math.random() > 0.5 ? 'BUY' : 'SKIP',
      token: 'PUMP_' + Math.floor(Math.random() * 9999),
      score: Math.floor(Math.random() * 40) + 60,
      pressure: ['weak','moderate','strong','viral'][Math.floor(Math.random() * 4)],
      pnlUsd: ((Math.random() - 0.5) * 40).toFixed(2),
      withdrawn: (Math.random() * 200).toFixed(2),
      activeWallet: (100 + Math.random() * 500).toFixed(2),
      exitReason: ['TRAIL_STOP','MOONSHOT_EXIT','TIME_EXIT','LOSS_CUT'][Math.floor(Math.random() * 4)],
      exitMult: (1 + Math.random() * 3).toFixed(2),
      signals: {
        dev: 'dynamic analysis',
        snipe: 'wallet cluster monitoring',
        momentum: 'volume acceleration',
        hype: 'social pressure rising',
        curve: 'bonding curve healthy'
      },
      pricePath: Array.from({ length: 24 }, (_, i) => [i * 5, 1 + Math.sin(i / 4) + Math.random()]),
      volumePath: Array.from({ length: 24 }, () => Math.random() * 8)
    };

    updateDashboard(fake);
  };

  ws.onerror = () => {
    els.connectionStatus.textContent = 'websocket unavailable';
  };
}

simulateFeed();
