import React, { useState } from "react";
import "../styles/UploadCard.css";
import { uploadContract } from "../services/api";
import { orchestrate, pollJob } from "../services/orchestrator";
import { getToken } from "../services/auth";

export default function UploadCard({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [showPopup, setShowPopup] = useState(false);
  const [popupData, setPopupData] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    setError("");
    setStatus("");
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    // Double-check file is PDF before uploading
    const fileName = file.name.toLowerCase();
    if (!fileName.endsWith('.pdf')) {
      setError("Only PDF files can be analyzed. Please select a valid PDF document.");
      return;
    }

    if (!getToken()) {
      setError("Authentication required. Please log in again.");
      return;
    }
    setError("");
    setLoading(true);
    setStatus("Uploading and sanitizing...");

    try {
      // Step 1: Upload (sanitize)
      const uploadResp = await uploadContract(file);
      console.log("Sanitize response:", uploadResp);

      if (!uploadResp.ok) {
        throw new Error("File upload failed.");
      }

      // Verify it's actually a PDF from the response
      const uploadedFileName = uploadResp.filename.toLowerCase();
      if (!uploadedFileName.endsWith('.pdf')) {
        throw new Error("Only PDF files can be analyzed. The uploaded file is not a valid PDF.");
      }

      // Show popup for valid PDF
      setPopupData({
        filename: uploadResp.filename,
        documentId: uploadResp.document_id,
      });
      setShowPopup(true);
      setStatus("Valid PDF detected! Processing...");

      // Auto-redirect after 5 seconds or wait for user click
      const timeoutId = setTimeout(() => {
        proceedToAnalysis(uploadResp.document_id);
      }, 5000);

      // Store timeout ID so we can cancel it if user clicks OK
      window.uploadTimeoutId = timeoutId;

    } catch (err) {
      console.error(err);
      setError(err?.message || "Upload/analysis failed. Try again.");
      setStatus("");
      setLoading(false);
    }
  };

  const proceedToAnalysis = async (documentId) => {
    if (window.uploadTimeoutId) {
      clearTimeout(window.uploadTimeoutId);
      window.uploadTimeoutId = null;
    }
    setShowPopup(false);
    setStatus("Dispatching orchestration job...");

    try {
      const orchestration = await orchestrate(documentId, "demo");
      setStatus("Analyzing contract (this may take a moment)...");
      const jobStatus = await pollJob(orchestration.job_id, { timeoutMs: 120000 });

      if (jobStatus.status !== "completed") {
        throw new Error(jobStatus.detail || "Analysis failed");
      }

      const result = jobStatus.result || {};
      const payload = {
        document_id: documentId,
        tenant_id: result.tenant_id || "demo",
        clauses: result.clauses || [],
        risks: result.risks || [],
        recommendations: result.recommendations || [],
        ingest: result.ingest,
      };

      if (onUploadSuccess) {
        onUploadSuccess(payload);
      }

      setStatus("Contract analyzed successfully!");
      setLoading(false);
    } catch (err) {
      console.error(err);
      setError(err?.message || "Analysis failed. Try again.");
      setStatus("");
      setLoading(false);
    }
  };

  return (
    <div className="upload-card">
      <input
        type="file"
        id="fileInput"
        accept="*"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />
      <label htmlFor="fileInput" className="upload-label">
        {file ? <p>📄 {file.name}</p> : <p>📄 Click to upload a document</p>}
      </label>

      {error && <p className="error-text">{error}</p>}
      {status && !error && <p className="muted">{status}</p>}

      <button className="upload-btn" onClick={handleUpload} disabled={loading}>
        {loading ? "Processing..." : "Analyze Contract"}
      </button>

      {/* Popup Modal */}
      {showPopup && popupData && (
        <div className="popup-overlay">
          <div className="popup-content">
            <h3>✅ Valid PDF Detected!</h3>
            <p><strong>File:</strong> {popupData.filename}</p>
            <p><strong>Document ID:</strong> {popupData.documentId}</p>
            <p className="muted">Redirecting to analysis in 5 seconds...</p>
            <button 
              className="popup-btn" 
              onClick={() => proceedToAnalysis(popupData.documentId)}
            >
              OK - Proceed Now
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
