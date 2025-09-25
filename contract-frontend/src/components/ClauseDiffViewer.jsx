import React, { useEffect, useState } from "react";
import { getRecommendations } from "../services/api";
import "../styles/ClauseDiffViewer.css";

export default function ClauseDiffViewer({ docId }) {
  const [recs, setRecs] = useState([]);

  useEffect(() => {
    async function fetchData() {
      try {
        const data = await getRecommendations(docId);
        setRecs(data);
      } catch (err) {
        console.error("Failed to fetch recommendations", err);
      }
    }
    fetchData();
  }, [docId]);

  return (
    <div className="diff-container">
      <h2>Clause Recommendations</h2>
      {recs.map((r, idx) => (
        <div key={idx} className="diff-card">
          <div className="diff-side original">
            <h4>Original Clause</h4>
            <p>{r.original_text || "Original text not available"}</p>
          </div>
          <div className="diff-side suggested">
            <h4>Suggested Rewrite</h4>
            <p>{r.suggested_text}</p>
          </div>
          <div className="diff-meta">
            <span className="diff-change">{r.diff}</span>
            {r.why && <p className="diff-why">💡 {r.why}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
