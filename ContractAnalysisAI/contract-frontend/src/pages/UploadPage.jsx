import React, { useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import UploadCard from "../components/UploadCard";
import { getToken, clearToken } from "../services/auth";

export default function UploadPage() {
  const navigate = useNavigate();
  const token = getToken();

  useEffect(() => {
    if (!token) {
      navigate("/login", { state: { from: "/upload" } });
    }
  }, [token, navigate]);

  const handleSuccess = (data) => {
    console.log("Final ingest result:", data);
    if (data?.document_id) {
      navigate(`/analysis/${data.document_id}`, { state: { analysis: data } });
    }
  };

  const handleLogout = () => {
    clearToken();
    navigate("/login", { replace: true });
  };

  return (
    <div style={{ padding: "40px", textAlign: "center" }}>
      <h1>Upload Your Contract</h1>
      <p>AI will analyze risks, clauses, and provide recommendations</p>
      {token ? (
        <div style={{ marginBottom: "16px" }}>
          <span className="muted">Authenticated as member.</span>
          <button onClick={handleLogout} className="secondary-btn" style={{ padding: "6px 16px", marginLeft: "12px" }}>
            Log Out
          </button>
        </div>
      ) : (
        <p className="error-text">
          Session expired. Please <Link to="/login">log in</Link> again.
        </p>
      )}
      <UploadCard onUploadSuccess={handleSuccess} />
    </div>
  );
}
