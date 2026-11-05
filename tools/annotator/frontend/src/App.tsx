import { useEffect, useState } from 'react';

interface ClipItem {
  clip_id: string;
  path: string;
  fps: number;
  frame_count: number;
  width: number;
  height: number;
  ball_type: string | null;
  has_results: boolean;
  has_calibration: boolean;
  label_status: 'none' | 'draft' | 'final' | 'flagged';
  split: 'dev' | 'final' | null;
  frame_count_mismatch?: boolean;
}

export default function App() {
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/clips')
      .then((res) => {
        if (!res.ok) {
          throw new Error(`Failed to fetch clips: HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((data: ClipItem[]) => {
        setClips(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="container">
      <header className="header">
        <h1>Cricket Delivery Annotator</h1>
        <p className="subtitle">Local Video Annotation Tool &bull; Frame-Exact Ground Truth</p>
      </header>

      <main>
        {loading && <div className="status">Loading delivery clips...</div>}
        {error && <div className="status error">Error: {error}</div>}

        {!loading && !error && (
          <div className="card">
            <div className="card-header">
              <h2>Clips Manifest ({clips.length} deliveries)</h2>
              <span className="badge-count">{clips.length} Loaded</span>
            </div>
            <div className="table-responsive">
              <table className="clips-table">
                <thead>
                  <tr>
                    <th>Clip ID</th>
                    <th>Resolution</th>
                    <th>FPS</th>
                    <th>Frames</th>
                    <th>Ball</th>
                    <th>Results</th>
                    <th>Calibration</th>
                    <th>Split</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {clips.map((clip) => (
                    <tr key={clip.clip_id}>
                      <td className="clip-id">{clip.clip_id}</td>
                      <td>{clip.width} &times; {clip.height}</td>
                      <td>{clip.fps}</td>
                      <td>
                        {clip.frame_count}
                        {clip.frame_count_mismatch && (
                          <span className="badge badge-warning" title="Decoded count differs from metadata">Mismatch</span>
                        )}
                      </td>
                      <td>
                        <span className={`ball-tag ball-${clip.ball_type || 'unknown'}`}>
                          {clip.ball_type || 'N/A'}
                        </span>
                      </td>
                      <td>{clip.has_results ? '✓' : '—'}</td>
                      <td>{clip.has_calibration ? '✓' : '—'}</td>
                      <td>
                        <span className="split-badge">{clip.split || 'unassigned'}</span>
                      </td>
                      <td>
                        <span className={`status-pill status-${clip.label_status}`}>
                          {clip.label_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {clips.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: 'center', padding: '2rem' }}>
                        No clips found in manifest.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
