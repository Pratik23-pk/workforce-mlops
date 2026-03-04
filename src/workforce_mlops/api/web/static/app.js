const state = {
  timelineChart: null,
  forecastChart: null,
};
let busy = false;

const fmtNum = (value, decimals = 0) =>
  new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
const fmtPct = (value) => `${(value * 100).toFixed(2)}%`;
const fmtFloat = (value) => Number(value).toFixed(4);

const atmospherePlugin = {
  id: "atmosphere",
  beforeDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const { left, right, top, bottom } = chartArea;
    ctx.save();

    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
    gradient.addColorStop(0, "rgba(255, 255, 255, 0.06)");
    gradient.addColorStop(1, "rgba(0, 0, 0, 0.16)");
    ctx.fillStyle = gradient;
    ctx.fillRect(left, top, right - left, bottom - top);

    ctx.globalAlpha = 0.12;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.14)";
    ctx.lineWidth = 1;
    for (let x = left; x < right; x += 26) {
      ctx.beginPath();
      ctx.moveTo(x, top);
      ctx.lineTo(x + 10, bottom);
      ctx.stroke();
    }

    ctx.restore();
  },
};

const recessionBandsPlugin = {
  id: "recessionBands",
  beforeDatasetsDraw(chart, args, pluginOptions) {
    const { bands = [] } = pluginOptions || {};
    if (!bands.length) return;

    const x = chart.scales.x;
    const y = chart.scales.y;
    if (!x || !y) return;

    const { ctx } = chart;
    const count = chart.data.labels.length;

    ctx.save();
    bands.forEach(({ start, end }) => {
      const startPx = x.getPixelForValue(start);
      const endPx = x.getPixelForValue(end);

      const leftGap = start > 0 ? startPx - x.getPixelForValue(start - 1) : x.getPixelForValue(1) - startPx;
      const rightGap =
        end < count - 1 ? x.getPixelForValue(end + 1) - endPx : endPx - x.getPixelForValue(end - 1);

      const left = startPx - leftGap / 2;
      const right = endPx + rightGap / 2;

      ctx.fillStyle = "rgba(255, 101, 132, 0.16)";
      ctx.fillRect(left, y.top, right - left, y.bottom - y.top);
    });
    ctx.restore();
  },
};

const riskZonesPlugin = {
  id: "riskZones",
  beforeDatasetsDraw(chart) {
    const yRisk = chart.scales.yRisk;
    const x = chart.scales.x;
    if (!yRisk || !x) return;

    const { ctx } = chart;
    const left = x.left;
    const right = x.right;

    const yHighTop = yRisk.getPixelForValue(1.0);
    const yHighBottom = yRisk.getPixelForValue(0.6);
    const yMedTop = yRisk.getPixelForValue(0.6);
    const yMedBottom = yRisk.getPixelForValue(0.3);

    ctx.save();
    ctx.fillStyle = "rgba(255, 101, 132, 0.12)";
    ctx.fillRect(left, yHighTop, right - left, yHighBottom - yHighTop);

    ctx.fillStyle = "rgba(255, 194, 71, 0.1)";
    ctx.fillRect(left, yMedTop, right - left, yMedBottom - yMedTop);
    ctx.restore();
  },
};

Chart.register(atmospherePlugin, recessionBandsPlugin, riskZonesPlugin);

function setMessage(text, isError = false) {
  const box = document.getElementById("messageBox");
  box.textContent = text;
  box.style.color = isError ? "#ff8aa2" : "#9ac4ff";
}

function setControlsBusy(status) {
  busy = status;
  const customBtn = document.getElementById("customPredictBtn");
  const marketInput = document.getElementById("marketIndex");
  if (customBtn) customBtn.disabled = status;
  if (marketInput) marketInput.disabled = status;

  document.querySelectorAll("#presetButtons .btn").forEach((button) => {
    button.disabled = status;
  });
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function createGradient(ctx, c1, c2) {
  const h = ctx.canvas.clientHeight || 260;
  const gradient = ctx.createLinearGradient(0, 0, 0, h);
  gradient.addColorStop(0, c1);
  gradient.addColorStop(1, c2);
  return gradient;
}

function commonChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 420,
      easing: "easeOutQuart",
    },
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      atmosphere: {},
      legend: {
        position: "top",
        labels: {
          color: "#f6f8ff",
          usePointStyle: true,
          boxWidth: 10,
          font: {
            family: "Space Grotesk",
            weight: "700",
          },
        },
      },
      tooltip: {
        backgroundColor: "rgba(10, 14, 36, 0.95)",
        borderColor: "rgba(0, 231, 255, 0.55)",
        borderWidth: 1,
        titleColor: "#ffffff",
        bodyColor: "#dbe8ff",
        padding: 10,
        displayColors: true,
      },
    },
    onHover: (event, elements, chart) => {
      chart.canvas.style.cursor = elements.length ? "pointer" : "default";
    },
  };
}

function movingAverage(values, windowSize = 3) {
  return values.map((_, index) => {
    const start = Math.max(0, index - windowSize + 1);
    const slice = values.slice(start, index + 1);
    const sum = slice.reduce((acc, value) => acc + value, 0);
    return sum / slice.length;
  });
}

function buildRecessionBands(points) {
  const bands = [];
  let start = null;

  points.forEach((point, index) => {
    if (point.net_change < 0 && start === null) {
      start = index;
    }
    if (point.net_change >= 0 && start !== null) {
      bands.push({ start, end: index - 1 });
      start = null;
    }
  });

  if (start !== null) {
    bands.push({ start, end: points.length - 1 });
  }

  return bands;
}

function renderTimelineChart(points) {
  const canvas = document.getElementById("timelineChart");
  const ctx = canvas.getContext("2d");
  const labels = points.map((p) => p.year);

  if (state.timelineChart) {
    state.timelineChart.destroy();
  }

  const hiringSeries = points.map((p) => p.hiring);
  const layoffsSeries = points.map((p) => p.layoffs);
  const netSeries = points.map((p) => p.net_change);

  const hiresLine = createGradient(ctx, "rgba(0, 231, 255, 1)", "rgba(0, 152, 255, 0.82)");
  const hiresFill = createGradient(ctx, "rgba(0, 231, 255, 0.34)", "rgba(0, 231, 255, 0.02)");
  const layoffsLine = createGradient(ctx, "rgba(255, 101, 132, 1)", "rgba(255, 78, 205, 0.8)");
  const layoffsFill = createGradient(ctx, "rgba(255, 101, 132, 0.26)", "rgba(255, 101, 132, 0.01)");
  const trendLine = createGradient(ctx, "rgba(255, 194, 71, 0.98)", "rgba(255, 150, 71, 0.9)");

  state.timelineChart = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: "Net Change",
          data: netSeries,
          yAxisID: "yNet",
          backgroundColor: (context) =>
            context.raw >= 0 ? "rgba(123, 255, 123, 0.5)" : "rgba(255, 101, 132, 0.5)",
          borderRadius: 5,
          maxBarThickness: 22,
          order: 3,
        },
        {
          type: "line",
          label: "Historical Hiring",
          data: hiringSeries,
          borderColor: hiresLine,
          backgroundColor: hiresFill,
          borderWidth: 3,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.32,
          fill: true,
          order: 1,
        },
        {
          type: "line",
          label: "Historical Layoffs",
          data: layoffsSeries,
          borderColor: layoffsLine,
          backgroundColor: layoffsFill,
          borderWidth: 3,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.32,
          fill: true,
          order: 1,
        },
        {
          type: "line",
          label: "Hiring Trend (3Y Avg)",
          data: movingAverage(hiringSeries, 3),
          borderColor: trendLine,
          borderWidth: 2,
          borderDash: [6, 4],
          pointRadius: 0,
          tension: 0.2,
          fill: false,
          order: 2,
        },
      ],
    },
    options: {
      ...commonChartOptions(),
      plugins: {
        ...commonChartOptions().plugins,
        recessionBands: {
          bands: buildRecessionBands(points),
        },
      },
      scales: {
        x: {
          ticks: { color: "#d4d8ff" },
          grid: { color: "rgba(255, 255, 255, 0.08)" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#d4d8ff" },
          grid: { color: "rgba(255, 255, 255, 0.08)" },
        },
        yNet: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: {
            color: "#b3ffcb",
            callback: (value) => fmtNum(value, 0),
          },
        },
      },
    },
  });
}

function renderForecastChart(forecast) {
  const canvas = document.getElementById("forecastChart");
  const ctx = canvas.getContext("2d");
  const labels = forecast.map((p) => p.year);

  if (state.forecastChart) {
    state.forecastChart.destroy();
  }

  const hiresBar = createGradient(ctx, "rgba(0, 231, 255, 0.95)", "rgba(0, 153, 255, 0.7)");
  const layoffsBar = createGradient(ctx, "rgba(255, 101, 132, 0.95)", "rgba(255, 78, 205, 0.68)");
  const riskLine = createGradient(ctx, "rgba(123, 255, 123, 0.95)", "rgba(79, 255, 175, 0.8)");
  const employeeLine = createGradient(ctx, "rgba(255, 194, 71, 1)", "rgba(255, 150, 71, 0.85)");
  const employeeFill = createGradient(ctx, "rgba(255, 194, 71, 0.24)", "rgba(255, 194, 71, 0.02)");
  const volatilityLine = createGradient(ctx, "rgba(191, 153, 255, 0.95)", "rgba(137, 115, 255, 0.8)");

  state.forecastChart = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: "Predicted Hiring",
          data: forecast.map((p) => p.hiring),
          backgroundColor: hiresBar,
          borderRadius: 8,
          maxBarThickness: 30,
          order: 2,
        },
        {
          type: "bar",
          label: "Predicted Layoffs",
          data: forecast.map((p) => p.layoffs),
          backgroundColor: layoffsBar,
          borderRadius: 8,
          maxBarThickness: 30,
          order: 2,
        },
        {
          type: "line",
          label: "Layoff Risk Probability",
          data: forecast.map((p) => p.layoff_risk_prob),
          yAxisID: "yRisk",
          borderColor: riskLine,
          borderWidth: 3,
          pointRadius: 3,
          pointHoverRadius: 6,
          tension: 0.3,
          order: 1,
        },
        {
          type: "line",
          label: "Projected Employees",
          data: forecast.map((p) => p.employees),
          yAxisID: "yEmployees",
          borderColor: employeeLine,
          backgroundColor: employeeFill,
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.25,
          fill: true,
          order: 3,
        },
        {
          type: "line",
          label: "Volatility",
          data: forecast.map((p) => p.workforce_volatility),
          yAxisID: "yVol",
          borderColor: volatilityLine,
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.28,
          fill: false,
          order: 1,
        },
      ],
    },
    options: {
      ...commonChartOptions(),
      plugins: {
        ...commonChartOptions().plugins,
        riskZones: {},
      },
      scales: {
        x: {
          ticks: { color: "#d4d8ff" },
          grid: { color: "rgba(255, 255, 255, 0.08)" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#d4d8ff" },
          grid: { color: "rgba(255, 255, 255, 0.08)" },
        },
        yRisk: {
          position: "right",
          min: 0,
          max: 1,
          grid: { drawOnChartArea: false },
          ticks: {
            color: "#9dffcb",
            callback: (value) => `${Math.round(value * 100)}%`,
          },
        },
        yEmployees: {
          position: "right",
          offset: true,
          grid: { drawOnChartArea: false },
          ticks: {
            color: "#ffd49f",
            callback: (value) => fmtNum(value, 0),
          },
        },
        yVol: {
          position: "left",
          grid: { drawOnChartArea: false },
          ticks: {
            color: "#c8bdff",
            callback: (value) => fmtFloat(value),
          },
        },
      },
    },
  });
}

function renderMetrics(response) {
  const pred = response.predictions || {};
  const latest =
    Array.isArray(response.forecast) && response.forecast.length > 0
      ? response.forecast[response.forecast.length - 1]
      : null;

  const hiring = latest ? latest.hiring : pred.hiring;
  const layoffs = latest ? latest.layoffs : pred.layoffs;
  const risk = latest ? latest.layoff_risk_prob : pred.layoff_risk_prob;
  const volatility = latest ? latest.workforce_volatility : pred.workforce_volatility;

  document.getElementById("metricHiring").textContent = fmtNum(hiring, 0);
  document.getElementById("metricLayoffs").textContent = fmtNum(layoffs, 0);
  document.getElementById("metricRisk").textContent = fmtPct(risk);
  document.getElementById("metricVolatility").textContent = fmtFloat(volatility);

  const yearLabel = latest ? latest.year : response.features?.year;
  document.getElementById("metricHiringLabel").textContent = `Hiring (${yearLabel})`;
  document.getElementById("metricLayoffsLabel").textContent = `Layoffs (${yearLabel})`;
  document.getElementById("metricRiskLabel").textContent = `Layoff Risk (${yearLabel})`;
  document.getElementById("metricVolatilityLabel").textContent = `Volatility (${yearLabel})`;

  const label = document.getElementById("scenarioLabel");
  const marketIndexInfo =
    response.scenario_id === "custom_market_index"
      ? ` | Market Index Input: ${document.getElementById("marketIndex").value}`
      : "";
  label.textContent = `${response.scenario_name}: ${response.scenario_description}${marketIndexInfo}`;
}

async function runPresetPrediction(presetId) {
  if (busy) return;
  setControlsBusy(true);
  setMessage("Running preset prediction...");
  try {
    const response = await fetchJson("/api/predict/preset", {
      method: "POST",
      body: JSON.stringify({ preset_id: presetId }),
    });

    renderMetrics(response);
    renderForecastChart(response.forecast);
    setMessage("Preset prediction complete.");
  } catch (error) {
    setMessage(`Prediction failed: ${error.message}`, true);
  } finally {
    setControlsBusy(false);
  }
}

async function runCustomPrediction() {
  if (busy) return;

  const input = document.getElementById("marketIndex");
  const marketIndex = Number(input.value);

  if (Number.isNaN(marketIndex) || marketIndex < 0 || marketIndex > 100) {
    setMessage("Custom market index must be between 0 and 100.", true);
    return;
  }

  setControlsBusy(true);
  setMessage("Running custom prediction...");
  try {
    const response = await fetchJson("/api/predict/custom", {
      method: "POST",
      body: JSON.stringify({ market_index: marketIndex }),
    });

    renderMetrics(response);
    renderForecastChart(response.forecast);
    setMessage("Custom prediction complete.");
  } catch (error) {
    setMessage(`Prediction failed: ${error.message}`, true);
  } finally {
    setControlsBusy(false);
  }
}

function renderPresets(presets) {
  const parent = document.getElementById("presetButtons");
  parent.innerHTML = "";

  presets.forEach((preset) => {
    const button = document.createElement("button");
    button.className = "btn";
    button.innerHTML = `<span class=\"title\">${preset.name}</span><span class=\"desc\">${preset.description}</span>`;
    button.addEventListener("click", () => runPresetPrediction(preset.id));
    parent.appendChild(button);
  });
}

async function bootstrap() {
  setMessage("Loading dashboard...");
  try {
    const [timeline, presetData] = await Promise.all([
      fetchJson("/api/timeline"),
      fetchJson("/api/presets"),
    ]);

    renderTimelineChart(timeline.points);
    renderPresets(presetData.presets);

    document.getElementById("customPredictBtn").addEventListener("click", runCustomPrediction);
    setMessage("Dashboard ready. Pick a scenario to spark the forecast.");
  } catch (error) {
    setMessage(`Initialization failed: ${error.message}`, true);
  }
}

bootstrap();
