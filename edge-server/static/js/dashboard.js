(() => {
  const api = {
    sensor: "/api/v1/sensors/latest",
    control: "/api/v1/control",
    capture: "/api/v1/camera/capture",
    vision: "/api/v1/vision/analyze",
    assistant: "/api/v1/assistant",
    policyStatus: "/api/v1/policy/irrigation/status",
  };

  const els = {
    temp: document.getElementById("temp"),
    humi: document.getElementById("humi"),
    lux: document.getElementById("lux"),
    soil: document.getElementById("soil"),
    gesture: document.getElementById("gesture"),
    updateTime: document.getElementById("update-time"),
    controlStatus: document.getElementById("control-status"),
    cloudBadge: document.getElementById("cloud-badge"),
    visionResults: document.getElementById("vision-results"),
    visionColor: document.getElementById("vision-color"),
    visionStage: document.getElementById("vision-stage"),
    visionScores: document.getElementById("vision-scores"),
    visionImage: document.getElementById("vision-image"),
    aiResponse: document.getElementById("ai-response"),
    aiText: document.getElementById("ai-text"),
    askAiBtn: document.getElementById("ask-ai-btn"),
    policyEnabled: document.getElementById("policy-enabled"),
    policyThreshold: document.getElementById("policy-threshold"),
    policySeconds: document.getElementById("policy-seconds"),
    policyCooldown: document.getElementById("policy-cooldown"),
    adminToken: document.getElementById("admin-token"),
    policyMsg: document.getElementById("policy-msg"),
    policyStatus: document.getElementById("policy-status"),
    policyLiveBanner: document.getElementById("policy-live-banner"),
    actuatorStatus: document.getElementById("actuator-status"),
  };

  function setControlStatus(message) {
    els.controlStatus.textContent = message;
  }

  function updateCloudBadge(cloudOk) {
    els.cloudBadge.className = `pill-status ${cloudOk ? "pill-status--ok" : "pill-status--error"}`;
    els.cloudBadge.textContent = cloudOk
      ? "边云协同正常，数据正在实时上云"
      : "边缘自治模式，云端链路暂时不可用";
  }

  function setPolicyLiveBanner({ active, text }) {
    els.policyLiveBanner.className = `pill-status ${active ? "pill-status--ok" : ""}`.trim();
    els.policyLiveBanner.textContent = text;
  }

  async function fetchData() {
    try {
      const data = await EdgeApp.fetchJson(api.sensor);
      els.temp.textContent = data.temperature ?? "--";
      els.humi.textContent = data.humidity ?? "--";
      els.lux.textContent = typeof data.lux === "number" ? data.lux.toFixed(1) : "--";
      els.soil.textContent = data.soil ?? "--";
      els.gesture.textContent = data.gesture ?? "暂无识别";
      els.updateTime.textContent = data.timestamp ?? "N/A";
      updateCloudBadge(Boolean(data.cloud_ok));
    } catch (error) {
      console.error("获取数据失败:", error);
      ["temp", "humi", "lux", "soil", "gesture"].forEach((key) => {
        els[key].textContent = "--";
      });
      els.updateTime.textContent = "连接失败";
      updateCloudBadge(false);
    }
  }

  async function sendControlCommand(command) {
    setControlStatus(`正在下发边缘指令: ${command}`);
    try {
      const result = await EdgeApp.fetchJson(api.control, {
        method: "POST",
        body: JSON.stringify({ command }),
      });
      setControlStatus(`成功: ${result.message}`);
      refreshPolicyStatus();
    } catch (error) {
      console.error("发送命令失败:", error);
      setControlStatus(`错误: ${error.message}`);
    }
  }

  async function capturePhoto() {
    setControlStatus("正在唤醒摄像头...");
    try {
      const result = await EdgeApp.fetchJson(api.capture, { method: "POST" });
      setControlStatus(`抓拍完成: ${result.path}`);
    } catch (error) {
      console.error("拍照失败:", error);
      setControlStatus(`硬件错误: ${error.message}`);
    }
  }

  async function analyzeVision() {
    setControlStatus("启动本地图像推理...");
    els.visionResults.classList.remove("result-box--visible");
    try {
      const result = await EdgeApp.fetchJson(api.vision, { method: "POST" });
      if (result.status !== "success") throw new Error(result.message || "推理失败");
      els.visionColor.textContent = result.detected_color;
      els.visionStage.textContent = result.growth_stage;
      els.visionScores.textContent = JSON.stringify(result.scores);
      els.visionImage.src = `${result.analysis_image_url}?t=${Date.now()}`;
      els.visionResults.classList.add("result-box--visible");
      setControlStatus("视觉分析完毕");
    } catch (error) {
      console.error("分析失败:", error);
      setControlStatus(`CV 引擎错误: ${error.message}`);
    }
  }

  async function askAssistant() {
    els.aiResponse.classList.add("result-box--visible");
    els.aiText.textContent = "正在唤醒 Qwen 本地模型进行推理...";
    els.askAiBtn.disabled = true;
    try {
      const result = await EdgeApp.fetchJson(api.assistant, {
        method: "POST",
        body: JSON.stringify({
          message: "请简短评估当前环境是否适合藏红花生长，并给出动作建议（比如是否需要浇水或开灯）。",
        }),
      });
      if (result.status !== "success") throw new Error(result.message || "大模型推理失败");
      els.aiText.innerHTML = result.answer.replace(/\n/g, "<br>");
    } catch (error) {
      console.error("AI 助手失败:", error);
      els.aiText.textContent = `请求失败: ${error.message}`;
    } finally {
      els.askAiBtn.disabled = false;
    }
  }

  async function loadPolicy() {
    try {
      await EdgeApp.loadPolicyIntoForm({
        enabled: "policy-enabled",
        threshold: "policy-threshold",
        seconds: "policy-seconds",
        cooldown: "policy-cooldown",
      });
      els.policyMsg.textContent = "已同步当前策略";
    } catch (error) {
      els.policyMsg.textContent = `无法加载策略: ${error.message}`;
    }
  }

  async function savePolicy() {
    els.policyMsg.textContent = "正在持久化...";
    try {
      await EdgeApp.savePolicyFromForm({
        enabled: "policy-enabled",
        threshold: "policy-threshold",
        seconds: "policy-seconds",
        cooldown: "policy-cooldown",
      }, els.adminToken.value);
      els.policyMsg.textContent = "已保存至数据库";
      els.policyMsg.style.color = "var(--shell-success)";
      refreshPolicyStatus();
    } catch (error) {
      els.policyMsg.textContent = `鉴权/写入失败: ${error.message}`;
      els.policyMsg.style.color = "var(--shell-danger)";
    }
  }

  async function refreshPolicyStatus() {
    try {
      const state = await EdgeApp.fetchJson(api.policyStatus);
      if (state.watering) {
        els.policyStatus.textContent = `自动浇水中${state.last_start_ts ? `，开始于 ${state.last_start_ts}` : ""}`;
        if (state.last_reason) {
          els.policyStatus.textContent += `，触发原因: ${state.last_reason}`;
        }
        setPolicyLiveBanner({ active: true, text: "自动浇水中" });
      } else {
        els.policyStatus.textContent = `待机监控中，上次执行 ${state.last_end_ts || "未知"}`;
        if (state.last_reason) {
          els.policyStatus.textContent += `，上次触发原因: ${state.last_reason}`;
        }
        setPolicyLiveBanner({ active: false, text: "自动浇水待机中" });
      }
      const feedback = state.actuator_feedback || {};
      els.actuatorStatus.textContent = feedback.timestamp
        ? `${feedback.message || "状态已更新"} (${feedback.timestamp})`
        : "等待执行器状态更新";
    } catch (error) {
      els.policyStatus.textContent = "边缘服务连接异常";
      setPolicyLiveBanner({ active: false, text: "自动浇水状态获取失败" });
      els.actuatorStatus.textContent = "执行器状态获取失败";
    }
  }

  document.getElementById("policy-save").addEventListener("click", savePolicy);
  document.getElementById("led-on-btn").addEventListener("click", () => sendControlCommand("led_on"));
  document.getElementById("led-off-btn").addEventListener("click", () => sendControlCommand("led_off"));
  document.getElementById("pump-on-btn").addEventListener("click", () => sendControlCommand(JSON.stringify({ actuator: "pump", action: "on" })));
  document.getElementById("pump-off-btn").addEventListener("click", () => sendControlCommand(JSON.stringify({ actuator: "pump", action: "off" })));
  document.getElementById("led-strip-on-btn").addEventListener("click", () => sendControlCommand(JSON.stringify({ actuator: "led_strip", action: "on" })));
  document.getElementById("led-strip-off-btn").addEventListener("click", () => sendControlCommand(JSON.stringify({ actuator: "led_strip", action: "off" })));
  document.getElementById("capture-photo-btn").addEventListener("click", capturePhoto);
  document.getElementById("analyze-vision-btn").addEventListener("click", analyzeVision);
  document.getElementById("ask-ai-btn").addEventListener("click", askAssistant);

  fetchData();
  loadPolicy();
  refreshPolicyStatus();
  setInterval(fetchData, 1000);
  setInterval(refreshPolicyStatus, 1000);
})();
