const state = {
  timelineChart: null,
  forecastChart: null,
  timelinePoints: null,
  forecastPoints: null,
};
let busy = false;
const THEME_KEY = "workforce_theme";

const fmtNum = (value, decimals = 0) =>
  new Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
const fmtPct = (value) => `${(value * 100).toFixed(2)}%`;
const fmtFloat = (value) => Number(value).toFixed(4);

function getThemeColors() {
  const styles = getComputedStyle(document.documentElement);
  const read = (name) => styles.getPropertyValue(name).trim();
  return {
    atmosphereTop: read("--chart-atmosphere-top"),
    atmosphereBottom: read("--chart-atmosphere-bottom"),
    atmosphereStroke: read("--chart-atmosphere-stroke"),
    recessionBand: read("--chart-recession-band"),
    riskHigh: read("--chart-risk-high"),
    riskMed: read("--chart-risk-med"),
    legend: read("--chart-legend"),
    tooltipBg: read("--chart-tooltip-bg"),
    tooltipBorder: read("--chart-tooltip-border"),
    tooltipTitle: read("--chart-tooltip-title"),
    tooltipBody: read("--chart-tooltip-body"),
    tick: read("--chart-tick"),
    grid: read("--chart-grid"),
    netPos: read("--chart-net-pos"),
    netNeg: read("--chart-net-neg"),
    yNet: read("--chart-ynet"),
    yRisk: read("--chart-yrisk"),
    yEmployees: read("--chart-yemployees"),
    yVol: read("--chart-yvol"),
    hiringLineStart: read("--chart-hiring-line-start"),
    hiringLineEnd: read("--chart-hiring-line-end"),
    hiringFillStart: read("--chart-hiring-fill-start"),
    hiringFillEnd: read("--chart-hiring-fill-end"),
    layoffsLineStart: read("--chart-layoffs-line-start"),
    layoffsLineEnd: read("--chart-layoffs-line-end"),
    layoffsFillStart: read("--chart-layoffs-fill-start"),
    layoffsFillEnd: read("--chart-layoffs-fill-end"),
    trendLineStart: read("--chart-trend-line-start"),
    trendLineEnd: read("--chart-trend-line-end"),
    hiresBarStart: read("--chart-hires-bar-start"),
    hiresBarEnd: read("--chart-hires-bar-end"),
    layoffsBarStart: read("--chart-layoffs-bar-start"),
    layoffsBarEnd: read("--chart-layoffs-bar-end"),
    riskLineStart: read("--chart-risk-line-start"),
    riskLineEnd: read("--chart-risk-line-end"),
    employeeLineStart: read("--chart-employee-line-start"),
    employeeLineEnd: read("--chart-employee-line-end"),
    employeeFillStart: read("--chart-employee-fill-start"),
    employeeFillEnd: read("--chart-employee-fill-end"),
    volatilityLineStart: read("--chart-volatility-line-start"),
    volatilityLineEnd: read("--chart-volatility-line-end"),
    message: read("--message"),
    messageError: read("--message-error"),
  };
}

const atmospherePlugin = {
  id: "atmosphere",
  beforeDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const { left, right, top, bottom } = chartArea;
    const colors = getThemeColors();
    ctx.save();

    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
    gradient.addColorStop(0, colors.atmosphereTop);
    gradient.addColorStop(1, colors.atmosphereBottom);
    ctx.fillStyle = gradient;
    ctx.fillRect(left, top, right - left, bottom - top);

    ctx.globalAlpha = 0.12;
    ctx.strokeStyle = colors.atmosphereStroke;
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
    const colors = getThemeColors();

    ctx.save();
    bands.forEach(({ start, end }) => {
      const startPx = x.getPixelForValue(start);
      const endPx = x.getPixelForValue(end);

      const leftGap = start > 0 ? startPx - x.getPixelForValue(start - 1) : x.getPixelForValue(1) - startPx;
      const rightGap =
        end < count - 1 ? x.getPixelForValue(end + 1) - endPx : endPx - x.getPixelForValue(end - 1);

      const left = startPx - leftGap / 2;
      const right = endPx + rightGap / 2;

      ctx.fillStyle = colors.recessionBand;
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
    const colors = getThemeColors();
    const left = x.left;
    const right = x.right;

    const yHighTop = yRisk.getPixelForValue(1.0);
    const yHighBottom = yRisk.getPixelForValue(0.6);
    const yMedTop = yRisk.getPixelForValue(0.6);
    const yMedBottom = yRisk.getPixelForValue(0.3);

    ctx.save();
    ctx.fillStyle = colors.riskHigh;
    ctx.fillRect(left, yHighTop, right - left, yHighBottom - yHighTop);

    ctx.fillStyle = colors.riskMed;
    ctx.fillRect(left, yMedTop, right - left, yMedBottom - yMedTop);
    ctx.restore();
  },
};

Chart.register(atmospherePlugin, recessionBandsPlugin, riskZonesPlugin);

function setMessage(text, isError = false) {
  const box = document.getElementById("messageBox");
  box.textContent = text;
  box.dataset.state = isError ? "error" : "default";
  const colors = getThemeColors();
  box.style.color = isError ? colors.messageError : colors.message;
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
  const colors = getThemeColors();
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
          color: colors.legend,
          usePointStyle: true,
          boxWidth: 10,
          font: {
            family: "Inter",
            weight: "700",
          },
        },
      },
      tooltip: {
        backgroundColor: colors.tooltipBg,
        borderColor: colors.tooltipBorder,
        borderWidth: 1,
        titleColor: colors.tooltipTitle,
        bodyColor: colors.tooltipBody,
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
  const colors = getThemeColors();
  const labels = points.map((p) => p.year);

  if (state.timelineChart) {
    state.timelineChart.destroy();
  }

  state.timelinePoints = points;
  const hiringSeries = points.map((p) => p.hiring);
  const layoffsSeries = points.map((p) => p.layoffs);
  const netSeries = points.map((p) => p.net_change);

  const hiresLine = createGradient(ctx, colors.hiringLineStart, colors.hiringLineEnd);
  const hiresFill = createGradient(ctx, colors.hiringFillStart, colors.hiringFillEnd);
  const layoffsLine = createGradient(ctx, colors.layoffsLineStart, colors.layoffsLineEnd);
  const layoffsFill = createGradient(ctx, colors.layoffsFillStart, colors.layoffsFillEnd);
  const trendLine = createGradient(ctx, colors.trendLineStart, colors.trendLineEnd);

  state.timelineChart = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: "line",
          label: "Historical Hiring",
          data: hiringSeries,
          borderColor: hiresLine,
          backgroundColor: hiresFill,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.35,
          fill: true,
          stack: "workforce",
          order: 1,
        },
        {
          type: "line",
          label: "Historical Layoffs",
          data: layoffsSeries,
          borderColor: layoffsLine,
          backgroundColor: layoffsFill,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.35,
          fill: true,
          stack: "workforce",
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
        {
          type: "line",
          label: "Net Change",
          data: netSeries,
          yAxisID: "yNet",
          borderColor: colors.yNet,
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 3,
          pointHoverRadius: 5,
          pointBackgroundColor: (context) => (context.raw >= 0 ? colors.netPos : colors.netNeg),
          pointBorderColor: (context) => (context.raw >= 0 ? colors.netPos : colors.netNeg),
          tension: 0.25,
          fill: false,
          order: 3,
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
          ticks: { color: colors.tick, font: { weight: "600" } },
          grid: { color: colors.grid },
        },
        y: {
          beginAtZero: true,
          stacked: true,
          ticks: { color: colors.tick, font: { weight: "600" } },
          grid: { color: colors.grid },
        },
        yNet: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: {
            color: colors.tick,
            font: { weight: "600" },
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
  const colors = getThemeColors();
  const labels = forecast.map((p) => p.year);

  if (state.forecastChart) {
    state.forecastChart.destroy();
  }

  state.forecastPoints = forecast;
  const hiresBar = createGradient(ctx, colors.hiresBarStart, colors.hiresBarEnd);
  const layoffsBar = createGradient(ctx, colors.layoffsBarStart, colors.layoffsBarEnd);
  const riskLine = createGradient(ctx, colors.riskLineStart, colors.riskLineEnd);
  const employeeLine = createGradient(ctx, colors.employeeLineStart, colors.employeeLineEnd);
  const employeeFill = createGradient(ctx, colors.employeeFillStart, colors.employeeFillEnd);
  const volatilityLine = createGradient(ctx, colors.volatilityLineStart, colors.volatilityLineEnd);

  state.forecastChart = new Chart(ctx, {
    data: {
      labels,
      datasets: [
        {
          type: "bar",
          label: "Predicted Hiring",
          data: forecast.map((p) => p.hiring),
          backgroundColor: hiresBar,
          borderRadius: 12,
          maxBarThickness: 26,
          barPercentage: 0.7,
          categoryPercentage: 0.6,
          stack: "forecast",
          order: 2,
        },
        {
          type: "bar",
          label: "Predicted Layoffs",
          data: forecast.map((p) => p.layoffs),
          backgroundColor: layoffsBar,
          borderRadius: 12,
          maxBarThickness: 26,
          barPercentage: 0.7,
          categoryPercentage: 0.6,
          stack: "forecast",
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
          ticks: { color: colors.tick, font: { weight: "600" } },
          grid: { color: colors.grid },
        },
        y: {
          beginAtZero: true,
          stacked: true,
          ticks: { color: colors.tick, font: { weight: "600" } },
          grid: { color: colors.grid },
        },
        yRisk: {
          position: "right",
          min: 0,
          max: 1,
          grid: { drawOnChartArea: false },
          ticks: {
            color: colors.tick,
            font: { weight: "600" },
            callback: (value) => `${Math.round(value * 100)}%`,
          },
        },
        yEmployees: {
          position: "right",
          offset: true,
          grid: { drawOnChartArea: false },
          ticks: {
            color: colors.tick,
            font: { weight: "600" },
            callback: (value) => fmtNum(value, 0),
          },
        },
        yVol: {
          position: "left",
          grid: { drawOnChartArea: false },
          ticks: {
            color: colors.tick,
            font: { weight: "600" },
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

function refreshCharts() {
  if (state.timelinePoints) {
    renderTimelineChart(state.timelinePoints);
  }
  if (state.forecastPoints) {
    renderForecastChart(state.forecastPoints);
  }
}

function syncMessageTheme() {
  const box = document.getElementById("messageBox");
  if (!box || !box.textContent) return;
  const colors = getThemeColors();
  const isError = box.dataset.state === "error";
  box.style.color = isError ? colors.messageError : colors.message;
}

function applyTheme(theme) {
  const normalized = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = normalized;
  localStorage.setItem(THEME_KEY, normalized);
  const colors = getThemeColors();
  Chart.defaults.color = colors.tick;
  Chart.defaults.borderColor = colors.grid;
  Chart.defaults.plugins.legend.labels.color = colors.legend;
  Chart.defaults.plugins.tooltip.backgroundColor = colors.tooltipBg;
  Chart.defaults.plugins.tooltip.borderColor = colors.tooltipBorder;
  Chart.defaults.plugins.tooltip.titleColor = colors.tooltipTitle;
  Chart.defaults.plugins.tooltip.bodyColor = colors.tooltipBody;
  refreshCharts();
  syncMessageTheme();
}

function initTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initial = stored || (prefersDark ? "dark" : "light");
  applyTheme(initial);
}

async function bootstrap() {
  initTheme();
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
