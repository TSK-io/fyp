(() => {
  const username = document.getElementById("username");
  const password = document.getElementById("password");
  const message = document.getElementById("msg");

  async function doLoginRegister(url) {
    message.textContent = "正在验证...";
    try {
      // 登录和注册共用同一套表单提交流程，只是接口地址不同。
      const result = await EdgeApp.fetchJson(url, {
        method: "POST",
        body: JSON.stringify({
          username: username.value.trim(),
          password: password.value,
        }),
      });
      if (!result.token) throw new Error("未返回令牌");
      localStorage.setItem("auth_token", result.token);
      message.style.color = "var(--shell-success)";
      message.textContent = "登录成功，正在跳转...";
      setTimeout(() => {
        // 登录后默认进入后台页，方便立刻配置策略或查看审计信息。
        window.location.href = "/admin";
      }, 500);
    } catch (error) {
      message.style.color = "var(--shell-danger)";
      message.textContent = `错误: ${error.message}`;
    }
  }

  document.getElementById("btn-login").addEventListener("click", () => doLoginRegister("/api/v1/auth/login"));
  document.getElementById("btn-register").addEventListener("click", () => doLoginRegister("/api/v1/auth/register"));
})();
