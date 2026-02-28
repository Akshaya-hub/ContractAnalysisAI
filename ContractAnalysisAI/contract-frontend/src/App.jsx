// App.jsx
import { Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import UploadPage from "./pages/UploadPage";
import AnalysisPage from "./pages/AnalysisPage";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/upload" element={<UploadPage />} />
      <Route path="/analysis/:docId" element={<AnalysisPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/login" element={<Login />} />
    </Routes>
  );
}

export default App;
