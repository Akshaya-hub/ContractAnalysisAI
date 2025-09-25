import React, { useEffect, useState } from "react";
import { useParams, useLocation } from "react-router-dom";
import { getClauses, getRisks, getRecommendations } from "../services/api";
import RiskCharts from "../components/RiskCharts";
import ClauseCard from "../components/ClauseCard";
import ClauseDiffViewer from "../components/ClauseDiffViewer";
import AgentChat from "../components/AgentChat";
import "../styles/AnalysisPage.css";

export default function AnalysisPage() {
  const { docId } = useParams();
  const location = useLocation(); // carries ingest results from UploadPage
  const [clauses, setClauses] = useState([]);
  const [risks, setRisks] = useState([]);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [c, r, rec] = await Promise.all([
          getClauses(docId),
          getRisks(docId),
          getRecommendations(docId),
        ]);
        setClauses(c);
        setRisks(r);
        setRecommendations(rec);
      } catch (err) {
        console.error("Analysis fetch error:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [docId]);

  if (loading) return <h2>Loading contract analysis...</h2>;

  return (
    <div className="analysis-container">
      {/* Left Panel */}
      <div className="contract-viewer">
        <h2>Contract Viewer</h2>
        <div className="contract-text">
          {clauses.map((clause, idx) => (
            <ClauseCard key={idx} clause={clause} risks={risks} />
          ))}
        </div>
      </div>

      {/* Right Panel */}
      <div className="analysis-right">
        <h2>Risk Dashboard</h2>
        <RiskCharts risks={risks} />

        <h2>AI Assistant</h2>
        <AgentChat docId={docId} recommendations={recommendations} />
      </div>
      <div>
        <h2>Recommendations</h2>
        <ClauseDiffViewer docId={docId} />
        </div>
    </div>
  );
}
