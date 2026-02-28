import React from "react";
import { PieChart, Pie, Cell, Tooltip, Legend, BarChart, XAxis, YAxis, Bar, CartesianGrid } from "recharts";
import "../styles/RiskCharts.css"; // Import the CSS file

const COLORS = ["#4caf50", "#ff9800", "#f44336"];

export default function RiskCharts({ risks }) {
  // Aggregate risk counts
  const counts = risks.reduce(
    (acc, r) => {
      const severity = (r.severity || r.level || "low").toString().toLowerCase();
      if (severity.includes("high")) {
        acc.high += 1;
      } else if (severity.includes("medium")) {
        acc.medium += 1;
      } else {
        acc.low += 1;
      }
      return acc;
    },
    { low: 0, medium: 0, high: 0 }
  );

  const data = [
    { name: "Low", value: counts.low },
    { name: "Medium", value: counts.medium },
    { name: "High", value: counts.high },
  ];

  const hasData = data.some((item) => item.value > 0);

  return (
    <div className="risk-charts-container">
      {hasData ? (
        <>
          <div className="chart-wrapper pie-chart-wrapper">
            <div className="chart-title">Risk Distribution</div>
            <PieChart width={300} height={250}>
              <Pie
                data={data}
                cx={150}
                cy={125}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label
              >
                {data.map((entry, idx) => (
                  <Cell key={`cell-${idx}`} fill={COLORS[idx]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </div>

          <div className="chart-wrapper bar-chart-wrapper">
            <div className="chart-title">Risk Counts</div>
            <BarChart width={300} height={250} data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="name" stroke="#94a3b8" />
              <YAxis allowDecimals={false} stroke="#94a3b8" />
              <Tooltip 
                contentStyle={{
                  backgroundColor: 'rgba(30, 41, 59, 0.9)',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                  color: '#f1f5f9'
                }}
              />
              <Bar dataKey="value" fill="#6366f1" />
            </BarChart>
          </div>
        </>
      ) : (
        <div className="empty-state">
          <p>No risks were detected for this upload.</p>
          <p className="muted">Try a contract with clauses about termination, confidentiality, or liability to see the charts populate.</p>
        </div>
      )}
    </div>
  );
}