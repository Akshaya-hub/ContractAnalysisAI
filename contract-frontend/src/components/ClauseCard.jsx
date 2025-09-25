import React from "react";
import "../styles/ClauseCard.css";

export default function ClauseCard({ clause, risks }) {
  // Find risk score for this clause
  const risk = risks.find((r) => r.clause_id === clause.id) || { level: "low" };

  return (
    <div className={`clause-card risk-${risk.level}`}>
      <h4>Clause {clause.id}</h4>
      <p>{clause.text}</p>
      <span className="risk-badge">{risk.level.toUpperCase()}</span>
    </div>
  );
}
