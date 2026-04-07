(() => {
  const els = {
    enabled: document.getElementById("en"),
    threshold: document.getElementById("th"),
    seconds: document.getElementById("sec"),
    cooldown: document.getElementById("cd"),
    token: document.getElementById("tok"),
    message: document.getElementById("msg"),
    limit: document.getElementById("limit"),
    logs: document.getElementById("logs"),
    status: document.getElementById("status"),
    authInfo: document.getElementById("auth-info"),
  };

  async function loadPolicy() {
    try {
      await EdgeApp.loadPolicyIntoForm({
        enabled: "en",
        threshold: "th",
        seconds: "sec",
        cooldown: "cd",
      });
      els.message.textContent = "当前策略已加载";
    } catch (error) {
      els.message.textContent = `获取硬件策略失败: ${error.message}`;
    }
  }

  async function savePolicy() {
    els.message.textContent = "正在下发...";
    try {
      await EdgeApp.savePolicyFromForm({
        enabled: "en",
        threshold: "th",
        seconds: "sec",
        cooldown: "cd",
      }, els.token.value);
      els.message.style.color = "var(--shell-success)";
      els.message.textContent = "策略已成功部署到边缘节点";
    } catch (error) {
      els.message.style.color = "var(--shell-danger)";
      els.message.textContent = `错误: ${error.message}`;
    }
  }

  async function loadLogs() {
    const limit = Math.max(10, Math.min(500, parseInt(els.limit.value || "100", 10)));
    els.status.textContent = "拉取中...";
    try {
      const response = await EdgeApp.fetchJson(`/api/v1/control/logs?limit=${limit}`);
      const items = response.items || [];
      els.logs.innerHTML = items.map((item) => `
        <tr>
          <td>${item.created_at || ""}</td>
          <td>${item.actuator || ""}</td>
          <td><code>${item.action || ""}</code></td>
          <td>${item.success ? '<span class="tag tag--ok">执行成功</span>' : '<span class="tag tag--error">执行失败</span>'}</td>
        </tr>
      `).join("");
      els.status.textContent = `当前展示最新的 ${items.length} 条流水`;
    } catch (error) {
      els.status.textContent = `加载失败: ${error.message}`;
    }
  }

  async function checkAuth() {
    const user = await EdgeApp.fetchCurrentUser();
    if (!user) {
      els.authInfo.className = "panel auth-banner pill-status pill-status--error";
      els.authInfo.innerHTML = '访客模式，请前往 <a href="/login">/login</a> 登录获取写权限';
      return;
    }
    els.authInfo.className = "panel auth-banner pill-status pill-status--ok";
    els.authInfo.textContent = `管理员在线: ${user.username} (Role: ${(user.roles || []).join(", ") || "User"})`;
  }

  document.getElementById("save").addEventListener("click", savePolicy);
  document.getElementById("reload").addEventListener("click", loadLogs);

  loadPolicy();
  loadLogs();
  checkAuth();
})();
