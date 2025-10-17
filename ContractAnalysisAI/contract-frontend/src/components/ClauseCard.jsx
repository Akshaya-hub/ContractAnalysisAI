import React from "react";
import "../styles/ClauseCard.css";

export default function ClauseCard({ clause, risks }) {
  // Find risk score for this clause
  const risk =
    risks.find((r) => r.clause_id === clause.id) ||
    risks.find((r) => r.clause_type === clause.type) ||
    {};

  const severity = (risk.severity || risk.level || "Low risk").toString();
  const badgeLabel = severity.toUpperCase();
  const badgeClass = severity.toLowerCase().includes("high")
    ? "risk-high"
    : severity.toLowerCase().includes("medium")
    ? "risk-medium"
    : "risk-low";

  return (
    <div className={`clause-card ${badgeClass}`}>
      <h4>Clause {clause.id}</h4>
      <p>{clause.text}</p>
      <span className="risk-badge">{badgeLabel}</span>
    </div>
  );
}
