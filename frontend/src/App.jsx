import React, { useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import AIInsightsPage from "./pages/AIInsights";

/**
 * App holds the shared AI insights state so it survives navigation.
 * Dashboard writes to it; AIInsightsPage reads from it.
 */
const App = () => {
  const [aiState, setAiState] = useState(null); // { jobId, data } | null

  return (
    <Routes>
      <Route
        path="/"
        element={<Dashboard onAiInsights={setAiState} />}
      />
      <Route
        path="/ai-insights"
        element={
          aiState
            ? <AIInsightsPage jobId={aiState.jobId} insightsData={aiState.data} />
            : <Navigate to="/" replace />
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;