(() => {
  // 统一维护首页依赖的 API 路径，避免散落在各个事件处理函数里。
  const api = {
    sensor: "/api/v1/sensors/latest",
    intelligence: "/api/v1/intelligence/diagnosis",
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
    intelBadge: document.getElementById("intel-badge"),
    intelScore: document.getElementById("intel-score"),
    intelRisk: document.getElementById("intel-risk"),
    intelSummary: document.getElementById("intel-summary"),
    intelThreshold: document.getElementById("intel-threshold"),
    intelDuration: document.getElementById("intel-duration"),
    intelAction: document.getElementById("intel-action"),
    intelDecisionReason: document.getElementById("intel-decision-reason"),
    intelMetrics: document.getElementById("intel-metrics"),
    intelTrends: document.getElementById("intel-trends"),
    intelAlerts: document.getElementById("intel-alerts"),
    intelRecommendations: document.getElementById("intel-recommendations"),
    visionResults: document.getElementById("vision-results"),
    visionColor: document.getElementById("vision-color"),
    visionStage: document.getElementById("vision-stage"),
    visionScores: document.getElementById("vision-scores"),
    visionImage: document.getElementById("vision-image"),
    aiResponse: document.getElementById("ai-response"),
    aiText: document.getElementById("ai-text"),
    aiModeBadge: document.getElementById("ai-mode-badge"),
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
    wateringToast: document.getElementById("watering-toast"),
  };

  let lastWateringState = null;
  let wateringToastTimer = null;

  function setControlStatus(message) {
    els.controlStatus.textContent = message;
  }

  function updateCloudBadge(cloudOk) {
    els.cloudBadge.className = `pill-status ${cloudOk ? "pill-status--ok" : "pill-status--error"}`;
    els.cloudBadge.textContent = cloudOk
      ? "云端在线"
      : "离线自治";
  }

  function setPolicyLiveBanner({ active, text }) {
    els.policyLiveBanner.className = `pill-status ${active ? "pill-status--ok" : ""}`.trim();
    els.policyLiveBanner.textContent = text;
  }

  function setAiModeBadge(mode) {
    const label = mode === "llm" ? "本地 LLM" : "规则引擎";
    const isOk = mode === "llm";
    els.aiModeBadge.className = `pill-status ${isOk ? "pill-status--ok" : ""}`.trim();
    els.aiModeBadge.textContent = label;
  }

  function renderTextList(container, items, itemClassName, emptyText) {
    if (!items || items.length === 0) {
      container.innerHTML = `<div class="${itemClassName} is-empty">${emptyText}</div>`;
      return;
    }
    container.innerHTML = items.join("");
  }

  function renderDiagnosis(diagnosis) {
    // 诊断结果由后端规则引擎生成，这里只负责映射为卡片、趋势和推荐动作。
    const riskClassMap = {
      low: "pill-status pill-status--ok",
      medium: "pill-status",
      high: "pill-status pill-status--error",
    };
    const decision = diagnosis.irrigation_decision || {};
    els.intelBadge.className = riskClassMap[diagnosis.risk_level] || "pill-status";
    els.intelBadge.textContent = diagnosis.risk_label || "未知";
    els.intelScore.textContent = diagnosis.overall_score ?? "--";
    els.intelRisk.textContent = diagnosis.risk_label || "等待分析";
    els.intelSummary.textContent = diagnosis.summary || "暂无诊断摘要";
    els.intelThreshold.textContent = decision.effective_threshold != null ? `${decision.effective_threshold}%` : "--";
    els.intelDuration.textContent = decision.recommended_duration != null ? `${decision.recommended_duration} 秒` : "--";
    els.intelAction.textContent = decision.action || "--";
    els.intelDecisionReason.textContent = decision.reason || "等待决策结果...";

    const metrics = (diagnosis.metrics || []).map((metric) => `
      <article class="intel-metric-card intel-metric-card--${metric.status || "missing"}">
        <span class="intel-metric-card__label">${metric.label}</span>
        <strong class="intel-metric-card__score">${metric.score ?? "--"}</strong>
        <span class="intel-metric-card__meta">${metric.display_value} / 目标 ${metric.target}</span>
      </article>
    `);
    renderTextList(els.intelMetrics, metrics, "intel-metric-card", "等待传感器数据...");

    const directionText = {
      rising: "上升",
      falling: "下降",
      stable: "平稳",
      unknown: "未知",
    };
    const trends = (diagnosis.trends || []).map((trend) => `
      <article class="intel-trend-chip intel-trend-chip--${trend.direction || "unknown"}">
        <span class="intel-trend-chip__label">${trend.label}</span>
        <strong>${directionText[trend.direction] || "未知"}</strong>
        <span>${trend.text || "历史数据不足"}</span>
      </article>
    `);
    renderTextList(els.intelTrends, trends, "intel-trend-chip", "历史趋势计算中...");

    const alerts = (diagnosis.alerts || []).map((alert) => `
      <article class="intel-list-item intel-list-item--${alert.severity || "low"}">
        <strong>${alert.title}</strong>
        <span>${alert.detail}</span>
      </article>
    `);
    renderTextList(els.intelAlerts, alerts, "intel-list-item", "当前没有明显异常告警。");

    const recommendations = (diagnosis.recommendations || []).map((text) => `
      <article class="intel-list-item intel-list-item--recommendation">
        <strong>推荐动作</strong>
        <span>${text}</span>
      </article>
    `);
    renderTextList(els.intelRecommendations, recommendations, "intel-list-item", "等待策略建议...");
  }

  function showWateringToast() {
    if (!els.wateringToast) return;

    els.wateringToast.classList.add("is-visible");
    window.clearTimeout(wateringToastTimer);
    wateringToastTimer = window.setTimeout(() => {
      els.wateringToast.classList.remove("is-visible");
    }, 2600);
  }

  async function fetchData() {
    try {
      // 传感器刷新频率最高，因此单独拆成轻量请求，避免和重型诊断接口互相拖慢。
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

  async function refreshDiagnosis() {
    try {
      const result = await EdgeApp.fetchJson(api.intelligence);
      renderDiagnosis(result);
    } catch (error) {
      console.error("获取智能诊断失败:", error);
      els.intelBadge.className = "pill-status pill-status--error";
      els.intelBadge.textContent = "AI 诊断获取失败";
      els.intelSummary.textContent = "智能诊断服务暂不可用";
      els.intelDecisionReason.textContent = error.message;
    }
  }

  async function sendControlCommand(command) {
    setControlStatus(`正在下发边缘指令: ${command}`);
    try {
      // control 接口接受原始 command 字符串，兼容 JSON 指令与旧版简写协议。
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
    // 请求返回前先显示“规则模式”，如果 LLM 可用再由响应结果把徽章切到本地模型。
    setAiModeBadge("heuristic");
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
      setAiModeBadge(result.mode);
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
      els.policyMsg.textContent = "策略已加载";
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
      els.policyMsg.textContent = "保存成功";
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
      // 只在状态从“非浇水”切换到“浇水中”时弹一次提示，避免轮询时反复闪烁。
      if (state.watering && lastWateringState !== true) {
        showWateringToast();
      }

      if (state.watering) {
        els.policyStatus.textContent = "浇水中";
        if (state.last_reason) {
          els.policyStatus.textContent += ` · ${state.last_reason}`;
        }
        setPolicyLiveBanner({ active: true, text: "自动浇水中" });
      } else {
        els.policyStatus.textContent = "待机";
        if (state.effective_threshold != null) {
          els.policyStatus.textContent += ` · 阈值 ${state.effective_threshold}%`;
        }
        if (state.decision_hint) {
          els.policyStatus.textContent += ` · ${state.decision_hint}`;
        }
        setPolicyLiveBanner({ active: false, text: "自动浇水待机中" });
      }
      const feedback = state.actuator_feedback || {};
      els.actuatorStatus.textContent = feedback.timestamp
        ? `${feedback.message || "状态已更新"} (${feedback.timestamp})`
        : "等待执行器状态更新";
      lastWateringState = Boolean(state.watering);
    } catch (error) {
      els.policyStatus.textContent = "状态异常";
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

  // 首页采用“快速数据 + 中速诊断”的分层轮询策略，兼顾实时性和树莓派负载。
  fetchData();
  refreshDiagnosis();
  loadPolicy();
  refreshPolicyStatus();
  setInterval(fetchData, 1000);
  setInterval(refreshDiagnosis, 5000);
  setInterval(refreshPolicyStatus, 1000);
})();
