// copytrading dashboard — chart wiring.
// Spec: renderEquityChart via htmx:afterSwap + #equity-data JSON island.

(function () {
  "use strict";

  var chartInstance = null;

  function renderEquityChart(data) {
    var canvas = document.getElementById("equity-chart");
    if (!canvas) {
      return;
    }
    if (typeof Chart === "undefined") {
      console.warn("Chart.js not loaded yet; skipping equity render");
      return;
    }
    var labels = data.map(function (_, i) { return i + 1; });
    if (chartInstance) {
      chartInstance.data.labels = labels;
      chartInstance.data.datasets[0].data = data;
      chartInstance.update();
      return;
    }
    chartInstance = new Chart(canvas, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Equity (USDC)",
          data: data,
          borderColor: "#0ff",
          backgroundColor: "rgba(0, 255, 255, 0.1)",
          tension: 0.2,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { display: false },
          y: { ticks: { color: "#8a8a99" } },
        },
      },
    });
  }

  document.body.addEventListener("htmx:afterSwap", function (event) {
    var target = event.target;
    if (!target || !target.querySelector) {
      return;
    }
    var island = target.querySelector("#equity-data");
    if (island && island.textContent) {
      try {
        renderEquityChart(JSON.parse(island.textContent));
      } catch (e) {
        console.error("Failed to parse equity data island", e);
      }
    }
  });
})();
