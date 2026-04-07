(() => {
  const username = document.getElementById("username");
  const password = document.getElementById("password");
  const message = document.getElementById("msg");

  async function doLoginRegister(url) {
    message.textContent = "正在验证...";
    try {
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
