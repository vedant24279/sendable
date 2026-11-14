import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ResultsView } from "./ResultsView";
import { TrackingResult } from "./types";
import { ThemeToggle } from "../../ThemeToggle";

const SAFE_ID_RE = /^[A-Za-z0-9_-]+$/;

export default function DevPreviewPage() {
  const [searchParams] = useSearchParams();
  const run = searchParams.get("run") || "";
  const clip = searchParams.get("clip") || "";
  const [result, setResult] = useState<TrackingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setResult(null);
    setError(null);
    if (!SAFE_ID_RE.test(run) || !SAFE_ID_RE.test(clip)) {
      setError("Invalid or missing ?run=<run>&clip=<clip> parameters.");
      return;
    }

    let cancelled = false;
    const base = `/__eval_runs/${encodeURIComponent(run)}/${encodeURIComponent(clip)}`;
    fetch(`${base}/results.json`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Not found (${res.status}): ${run}/${clip}/results.json`);
        }
        return (await res.json()) as TrackingResult;
      })
      .then((data) => {
        if (cancelled) return;
        setResult({
          ...data,
          outputs: {
            ...data.outputs,
            annotated_video_url: `${base}/output.mp4`,
            first_frame_url: "",
          },
        });
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [run, clip]);

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          Preview · {run || "?"} / {clip || "?"}
        </h1>
        <ThemeToggle />
      </div>
      {!result && !error && <div className="panel">Loading preview…</div>}
      {error && <div className="panel error">{error}</div>}
      {result && <ResultsView result={result} />}
    </div>
  );
}
