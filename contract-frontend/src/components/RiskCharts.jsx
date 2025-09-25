import React from "react";
import { PieChart, Pie, Cell, Tooltip, Legend, BarChart, XAxis, YAxis, Bar, CartesianGrid } from "recharts";

const COLORS = ["#4caf50", "#ff9800", "#f44336"];

export default function RiskCharts({ risks }) {
  // Aggregate risk counts
  const counts = risks.reduce(
    (acc, r) => {
      acc[r.level] = (acc[r.level] || 0) + 1;
      return acc;
    },
    { low: 0, medium: 0, high: 0 }
  );

  const data = [
    { name: "Low", value: counts.low },
    { name: "Medium", value: counts.medium },
    { name: "High", value: counts.high },
  ];

  return (
    <div>
      <PieChart width={300} height={250}>
        <Pie
          data={data}
          cx={150}
          cy={100}
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

      <BarChart width={300} height={250} data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="value" fill="#8884d8" />
      </BarChart>
    </div>
  );
}
