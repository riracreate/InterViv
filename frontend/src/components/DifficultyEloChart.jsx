import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend
);

const difficultyMap = { easy: 1, medium: 2, hard: 3 };

/**
 * Compute a simple moving average over `values` using a window of `size`.
 */
function movingAverage(values, size = 3) {
  return values.map((_, index) => {
    const start = Math.max(0, index - size + 1);
    const slice = values.slice(start, index + 1);
    return slice.reduce((sum, v) => sum + v, 0) / slice.length;
  });
}

/**
 * DifficultyEloChart
 *
 * Renders a dual-axis Chart.js line chart:
 *  - Left  Y-axis (primary)  : Elo Rating Trajectory (blue line)
 *  - Right Y-axis (secondary): Difficulty Moving Average (orange line)
 *
 * Props:
 *   eloValues         number[]  – elo_progression from the dashboard API
 *   difficultyValues  string[]  – difficulty_progression (e.g. ['medium','hard',…])
 *   movingAvgWindow   number    – window size for the difficulty moving average (default 3)
 */
function DifficultyEloChart({
  eloValues = [],
  difficultyValues = [],
  movingAvgWindow = 3,
}) {
  const numericDifficulty = difficultyValues.map(
    (level) => difficultyMap[(level || "").toLowerCase()] ?? 2
  );
  const diffMA = movingAverage(numericDifficulty, movingAvgWindow);

  const maxRounds = Math.max(eloValues.length, difficultyValues.length);
  const labels = Array.from({ length: maxRounds }, (_, i) => `R${i + 1}`);

  const data = {
    labels,
    datasets: [
      {
        label: "Elo Rating",
        data: eloValues,
        borderColor: "#246a73",
        backgroundColor: "rgba(36, 106, 115, 0.15)",
        fill: true,
        tension: 0.35,
        pointRadius: 4,
        pointBackgroundColor: "#246a73",
        yAxisID: "yElo",
      },
      {
        label: "Difficulty (Moving Avg)",
        data: diffMA,
        borderColor: "#f26a4b",
        backgroundColor: "transparent",
        fill: false,
        tension: 0.35,
        pointRadius: 4,
        pointBackgroundColor: "#f26a4b",
        borderDash: [6, 3],
        yAxisID: "yDiff",
      },
    ],
  };

  const options = {
    responsive: true,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      legend: {
        display: true,
        position: "top",
        labels: {
          usePointStyle: true,
          pointStyleWidth: 12,
          font: { size: 12 },
        },
      },
      tooltip: {
        callbacks: {
          label(context) {
            const { dataset, parsed } = context;
            if (dataset.yAxisID === "yDiff") {
              const map = { 1: "Easy", 2: "Medium", 3: "Hard" };
              const rounded = Math.round(parsed.y * 2) / 2;
              return `Difficulty MA: ${map[Math.round(parsed.y)] ?? parsed.y.toFixed(1)}`;
            }
            return `Elo: ${Math.round(parsed.y)}`;
          },
        },
      },
    },
    scales: {
      yElo: {
        type: "linear",
        position: "left",
        title: {
          display: true,
          text: "Elo Rating",
          color: "#246a73",
        },
        grid: { color: "rgba(16, 33, 43, 0.08)" },
        ticks: { color: "#246a73" },
      },
      yDiff: {
        type: "linear",
        position: "right",
        min: 0.5,
        max: 3.5,
        title: {
          display: true,
          text: "Difficulty",
          color: "#f26a4b",
        },
        ticks: {
          color: "#f26a4b",
          stepSize: 1,
          callback(value) {
            if (value === 1) return "Easy";
            if (value === 2) return "Medium";
            if (value === 3) return "Hard";
            return "";
          },
        },
        grid: { drawOnChartArea: false },
      },
      x: {
        grid: { display: false },
      },
    },
  };

  return (
    <div className="glass-panel p-6">
      <div className="mb-4">
        <p className="section-title">Performance Momentum</p>
        <h3 className="mt-2 text-2xl font-bold">
          Elo Trajectory &amp; Difficulty Change
        </h3>
        <p className="mt-1 text-sm text-ink/60">
          Elo rating (left axis) plotted with difficulty moving average (right
          axis).
        </p>
      </div>
      <Line data={data} options={options} />
    </div>
  );
}

export default DifficultyEloChart;
