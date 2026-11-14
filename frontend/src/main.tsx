import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { TrackingPage } from "./features/tracking/TrackingPage";
import { JobDetailPage } from "./features/tracking/JobDetailPage";
import "./styles.css";

const DevPreviewPage = import.meta.env.DEV
  ? React.lazy(() => import("./features/tracking/DevPreviewPage"))
  : null;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/tracking" replace />} />
        <Route path="/tracking" element={<TrackingPage />} />
        <Route path="/delivery-analysis" element={<JobDetailPage />} />
        {import.meta.env.DEV && DevPreviewPage ? (
          <Route
            path="/dev/preview"
            element={
              <React.Suspense fallback={<div className="panel">Loading…</div>}>
                <DevPreviewPage />
              </React.Suspense>
            }
          />
        ) : null}
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
