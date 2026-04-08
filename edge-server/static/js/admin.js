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
      // 管理页与首页共享同一策略接口，但这里偏向“完整配置”场景。
      await EdgeApp.loadPolicyIntoForm({
        enabled: "en",
        threshold: "th",
        seconds: "sec",
        cooldown: "cd",
      });
      els.message.textContent = "策略已加载";
    } catch (error) {
      els.message.textContent = `获取硬件策略失败: ${error.message}`;
    }
  }

  async function savePolicy() {
    els.message.textContent = "保存中...";
    try {
      await EdgeApp.savePolicyFromForm({
        enabled: "en",
        threshold: "th",
        seconds: "sec",
        cooldown: "cd",
      }, els.token.value);
      els.message.style.color = "var(--shell-success)";
      els.message.textContent = "保存成功";
    } catch (error) {
      els.message.style.color = "var(--shell-danger)";
      els.message.textContent = `错误: ${error.message}`;
    }
  }

  async function loadLogs() {
    const limit = Math.max(10, Math.min(500, parseInt(els.limit.value || "100", 10)));
    els.status.textContent = "加载中...";
    try {
      // 审计日志只关心控制动作结果，不重复展示原始整条命令载荷。
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
      els.status.textContent = `${items.length} 条记录`;
    } catch (error) {
      els.status.textContent = `加载失败: ${error.message}`;
    }
  }

  async function checkAuth() {
    // 页面顶部只做轻量状态提示，不阻止未登录用户浏览配置界面。
    const user = await EdgeApp.fetchCurrentUser();
    if (!user) {
      els.authInfo.className = "panel auth-banner pill-status pill-status--error";
      els.authInfo.innerHTML = '访客模式，请前往 <a href="/login">登录</a>';
      return;
    }
    els.authInfo.className = "panel auth-banner pill-status pill-status--ok";
    els.authInfo.textContent = `当前用户: ${user.username}`;
  }

  document.getElementById("save").addEventListener("click", savePolicy);
  document.getElementById("reload").addEventListener("click", loadLogs);

  // 首屏先拉策略和日志，再异步补充当前登录态。
  loadPolicy();
  loadLogs();
  checkAuth();
})();
