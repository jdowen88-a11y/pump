(function () {
  function headers() {
    return typeof getAuthHeaders === 'function' ? getAuthHeaders() : { 'Content-Type': 'application/json' };
  }

  async function tick() {
    if (typeof updateDashboard !== 'function') return;
    try {
      const response = await fetch('/api/protected/telemetry/latest', { headers: headers() });
      if (!response.ok) return;
      const body = await response.json();
      const payload = body && body.telemetry && body.telemetry.payload;
      if (payload) updateDashboard(payload);
    } catch (error) {
      return;
    }
  }

  tick();
  window.setInterval(tick, 3000);
})();
