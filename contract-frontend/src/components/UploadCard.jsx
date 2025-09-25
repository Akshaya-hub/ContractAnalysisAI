import React, { useState } from "react";
import "../styles/UploadCard.css";
import { uploadContract, ingestContract } from "../services/api";

export default function UploadCard({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }
    setError("");
    setLoading(true);

    try {
      // Step 1: Upload (sanitize)
      const uploadResp = await uploadContract(file);
      console.log("Sanitize response:", uploadResp);

      if (!uploadResp.ok) {
        throw new Error("File upload failed.");
      }

      // Step 2: Ingest
      const ingestResp = await ingestContract(uploadResp.document_id, "demo_tenant");
      console.log("Ingest response:", ingestResp);

      setLoading(false);
      if (onUploadSuccess) {
        onUploadSuccess(ingestResp);
      }
    } catch (err) {
      console.error(err);
      setError("Upload/analysis failed. Try again.");
      setLoading(false);
    }
  };

  return (
    <div className="upload-card">
      <input
        type="file"
        id="fileInput"
        accept=".pdf,.docx"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      <label htmlFor="fileInput" className="upload-label">
        {file ? <p>{file.name}</p> : <p>📄 Drag & Drop or click to upload</p>}
      </label>

      {error && <p className="error-text">{error}</p>}

      <button className="upload-btn" onClick={handleUpload} disabled={loading}>
        {loading ? "Processing..." : "Analyze Contract"}
      </button>
    </div>
  );
}
