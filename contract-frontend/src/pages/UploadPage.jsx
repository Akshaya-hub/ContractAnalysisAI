import React from "react";
import { useNavigate } from "react-router-dom";
import UploadCard from "../components/UploadCard";

export default function UploadPage() {
  const navigate = useNavigate();

  const handleSuccess = (data) => {
    console.log("Final ingest result:", data);
    if (data.document_id) {
      // Navigate to analysis page with chunks + metadata
      navigate(`/analysis/${data.document_id}`, { state: { analysis: data } });
    }
  };

  return (
    <div style={{ padding: "40px", textAlign: "center" }}>
      <h1>Upload Your Contract</h1>
      <p>AI will analyze risks, clauses, and provide recommendations</p>
      <UploadCard onUploadSuccess={handleSuccess} />
    </div>
  );
}
