(() => {
  const api = {
    history: "/api/v1/sensors/history",
    historyCsv: "/api/v1/sensors/history.csv",
    logs: "/api/v1/control/logs",
  };

  const el = (id) => document.getElementById(id);
  // 两张图拆开初始化，便于分别响应窗口缩放和局部重绘。
  const thChart = echarts.init(el("chart-th"));
  const lsChart = echarts.init(el("chart-ls"));

  function dtLocalToQuery(value) {
    return value ? value.replace("T", " ") : "";
  }

  function buildQueryParams() {
    const params = new URLSearchParams();
    const start = dtLocalToQuery(el("start").value);
    const end = dtLocalToQuery(el("end").value);
    const limit = Math.max(10, Math.min(1000, parseInt(el("limit").value || "200", 10)));
    if (start) params.set("start", start);
    if (end) params.set("end", end);
    params.set("limit", String(limit));
    return params;
  }

  async function loadPumpIntervals(queryParams) {
    // 通过控制日志反推水泵开关区间，再映射成 markArea 覆盖到土壤曲线图上。
    const params = new URLSearchParams(queryParams);
    params.set("actuator", "pump");
    params.set("limit", "500");
    const result = await EdgeApp.fetchJson(`${api.logs}?${params.toString()}`);
    const logs = (result.items || []).slice().reverse();
    const intervals = [];
    let currentStart = null;
    for (const item of logs) {
      const timestamp = item.created_at || item.timestamp || item.time || item.createdAt || item.ts;
      if (item.action === "on" && !currentStart) currentStart = timestamp;
      if (item.action === "off" && currentStart && timestamp) {
        intervals.push([{ xAxis: currentStart }, { xAxis: timestamp }]);
        currentStart = null;
      }
    }
    return intervals;
  }

  function renderCharts(items, intervals) {
    const ordered = items.slice().reverse();
    const xs = ordered.map((row) => row.timestamp);
    const temp = ordered.map((row) => row.temperature);
    const humi = ordered.map((row) => row.humidity);
    const lux = ordered.map((row) => row.lux);
    const soil = ordered.map((row) => row.soil);

    thChart.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["温度(°C)", "湿度(%)"], bottom: 0 },
      grid: { left: "3%", right: "4%", bottom: "10%", containLabel: true },
      xAxis: { type: "category", data: xs, boundaryGap: false },
      yAxis: [
        { type: "value", name: "温度(°C)" },
        { type: "value", name: "湿度(%)", splitLine: { show: false } },
      ],
      series: [
        { name: "温度(°C)", type: "line", data: temp, smooth: true, itemStyle: { color: "#b14e26" } },
        { name: "湿度(%)", type: "line", yAxisIndex: 1, data: humi, smooth: true, itemStyle: { color: "#446d9e" }, areaStyle: { opacity: 0.08 } },
      ],
    });

    lsChart.setOption({
      tooltip: { trigger: "axis" },
      legend: { data: ["光照(lux)", "土壤(%)"], bottom: 0 },
      grid: { left: "3%", right: "4%", bottom: "10%", containLabel: true },
      xAxis: { type: "category", data: xs, boundaryGap: false },
      yAxis: [
        { type: "value", name: "光照(lux)" },
        { type: "value", name: "土壤(%)", splitLine: { show: false } },
      ],
      series: [
        { name: "光照(lux)", type: "line", data: lux, smooth: true, itemStyle: { color: "#d18c21" } },
        {
          name: "土壤(%)",
          type: "line",
          yAxisIndex: 1,
          data: soil,
          smooth: true,
          itemStyle: { color: "#6f5c9d" },
          markArea: intervals.length ? { itemStyle: { color: "rgba(45,123,85,0.14)" }, data: intervals } : undefined,
        },
      ],
    });
  }

  async function loadData() {
    const params = buildQueryParams();
    el("status").textContent = "加载中...";
    try {
      // 历史数据和浇水区间并行拉取，减少页面等待时间。
      const [historyResult, intervals] = await Promise.all([
        EdgeApp.fetchJson(`${api.history}?${params.toString()}`),
        loadPumpIntervals(params),
      ]);
      const items = historyResult.items || [];
      renderCharts(items, intervals);
      el("status").textContent = `${items.length} 个数据点`;
    } catch (error) {
      el("status").textContent = `加载失败: ${error.message}`;
    }
  }

  function exportCsv() {
    // 导出直接打开后端 CSV 接口，不经过前端二次拼装，避免格式偏差。
    window.open(`${api.historyCsv}?${buildQueryParams().toString()}`, "_blank");
  }

  el("load").addEventListener("click", loadData);
  el("export").addEventListener("click", exportCsv);
  window.addEventListener("resize", () => {
    thChart.resize();
    lsChart.resize();
  });

  loadData();
  // 历史页刷新频率低于实时页，避免对数据库造成不必要压力。
  setInterval(loadData, 10000);
})();
