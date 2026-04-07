window.EdgeApp = (() => {
  const POLICY_URL = '/api/v1/policy/irrigation';
  const AUTH_ME_URL = '/api/v1/auth/me';

  function getStoredToken() {
    return (localStorage.getItem('auth_token') || '').trim();
  }

  function getAuthHeaders(adminToken = '') {
    const headers = { 'Content-Type': 'application/json' };
    const loginToken = getStoredToken();
    const overrideToken = (adminToken || '').trim();
    if (loginToken) headers.Authorization = `Bearer ${loginToken}`;
    if (overrideToken) headers['X-Admin-Token'] = overrideToken;
    return headers;
  }

  function readNumber(id, parser) {
    const raw = document.getElementById(id)?.value?.trim();
    if (raw === '') return null;
    const value = parser(raw);
    return Number.isNaN(value) ? NaN : value;
  }

  function fillPolicyForm(fieldIds, policy = {}) {
    document.getElementById(fieldIds.enabled).checked = !!(policy.enabled === 1 || policy.enabled === true);
    document.getElementById(fieldIds.threshold).value = policy.soil_threshold_min ?? '';
    document.getElementById(fieldIds.seconds).value = policy.watering_seconds ?? '';
    document.getElementById(fieldIds.cooldown).value = policy.cooldown_seconds ?? '';
  }

  async function loadPolicyIntoForm(fieldIds) {
    const response = await fetch(POLICY_URL);
    const policy = await response.json();
    if (!response.ok) throw new Error(policy.error || `HTTP ${response.status}`);
    fillPolicyForm(fieldIds, policy);
    return policy;
  }

  function buildPolicyPayload(fieldIds) {
    const soil = readNumber(fieldIds.threshold, Number.parseFloat);
    const wateringSeconds = readNumber(fieldIds.seconds, value => Number.parseInt(value, 10));
    const cooldownSeconds = readNumber(fieldIds.cooldown, value => Number.parseInt(value, 10));
    if ([soil, wateringSeconds, cooldownSeconds].some(Number.isNaN)) {
      throw new Error('请检查阈值、时长和冷却间隔');
    }
    return {
      enabled: document.getElementById(fieldIds.enabled).checked,
      soil_threshold_min: soil,
      watering_seconds: wateringSeconds,
      cooldown_seconds: cooldownSeconds,
    };
  }

  async function savePolicyFromForm(fieldIds, adminToken = '') {
    const response = await fetch(POLICY_URL, {
      method: 'POST',
      headers: getAuthHeaders(adminToken),
      body: JSON.stringify(buildPolicyPayload(fieldIds)),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '保存失败');
    fillPolicyForm(fieldIds, result);
    return result;
  }

  async function fetchCurrentUser() {
    const token = getStoredToken();
    if (!token) return null;
    const response = await fetch(AUTH_ME_URL, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return response.json();
  }

  return {
    getStoredToken,
    getAuthHeaders,
    loadPolicyIntoForm,
    savePolicyFromForm,
    fetchCurrentUser,
  };
})();
