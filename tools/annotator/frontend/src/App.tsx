import { useEffect } from 'react';
import { useAnnotatorStore } from './store';
import { useHotkeys } from './hooks/useHotkeys';
import { ClipList } from './components/ClipList';
import { Viewer } from './components/Viewer';
import { Timeline } from './components/Timeline';

export default function App() {
  const loadClips = useAnnotatorStore((s) => s.loadClips);
  const selectedClipId = useAnnotatorStore((s) => s.selectedClipId);
  const clips = useAnnotatorStore((s) => s.clips);
  const overlays = useAnnotatorStore((s) => s.overlays);
  const toggleOverlay = useAnnotatorStore((s) => s.toggleOverlay);
  const ghostAllowed = useAnnotatorStore((s) => s.ghostAllowed);
  const setGhostAllowed = useAnnotatorStore((s) => s.setGhostAllowed);
  const loupeEnabled = useAnnotatorStore((s) => s.loupeEnabled);
  const toggleLoupe = useAnnotatorStore((s) => s.toggleLoupe);
  const playing = useAnnotatorStore((s) => s.playing);
  const togglePlaying = useAnnotatorStore((s) => s.togglePlaying);

  // Activate keyboard shortcuts
  useHotkeys();

  useEffect(() => {
    void loadClips();
  }, [loadClips]);

  const clip = clips.find((c) => c.clip_id === selectedClipId);

  return (
    <div className="app-layout">
      {/* 1. Left: Clip List */}
      <ClipList />

      {/* 2. Centre: Viewer + Timeline */}
      <main className="centre-pane">
        <header className="top-toolbar">
          <div className="toolbar-left">
            <span className="app-brand">Cricket Annotator</span>
            <span className="toolbar-clip-id">{selectedClipId || 'No clip selected'}</span>
            {clip?.frame_count_mismatch && (
              <span className="badge-warning" title="Decoded frames differ from metadata">
                ⚠️ Mismatch
              </span>
            )}
          </div>
          <div className="toolbar-controls">
            <button
              className={`toolbar-btn ${playing ? 'btn-active' : ''}`}
              onClick={togglePlaying}
              title="Toggle playback at 0.25x speed (Space)"
            >
              {playing ? '⏸ Pause (0.25x)' : '▶ Play (0.25x)'}
            </button>
            <button
              className={`toolbar-btn ${loupeEnabled ? 'btn-active' : ''}`}
              onClick={toggleLoupe}
              title="Toggle 8x loupe magnifier (L or hold Alt)"
            >
              🔍 Loupe (8x)
            </button>
          </div>
        </header>

        <section className="viewer-wrapper">
          <Viewer />
        </section>

        <footer className="timeline-wrapper">
          <Timeline />
        </footer>
      </main>

      {/* 3. Right: Info Panel & Overlays */}
      <aside className="info-pane">
        <div className="info-section">
          <h3 className="section-title">Delivery Info</h3>
          {clip ? (
            <dl className="meta-list">
              <div className="meta-row">
                <dt>Clip ID</dt>
                <dd className="mono-text">{clip.clip_id}</dd>
              </div>
              <div className="meta-row">
                <dt>Resolution</dt>
                <dd>{clip.width} &times; {clip.height}</dd>
              </div>
              <div className="meta-row">
                <dt>Frame Count</dt>
                <dd>{clip.frame_count} frames</dd>
              </div>
              <div className="meta-row">
                <dt>FPS</dt>
                <dd>{clip.fps} fps</dd>
              </div>
              <div className="meta-row">
                <dt>Ball Colour</dt>
                <dd className={`badge-ball ball-${clip.ball_type || 'unknown'}`}>
                  {clip.ball_type || 'N/A'}
                </dd>
              </div>
              <div className="meta-row">
                <dt>Label Status</dt>
                <dd className={`status-pill status-${clip.label_status}`}>
                  {clip.label_status}
                </dd>
              </div>
              <div className="meta-row">
                <dt>Split</dt>
                <dd>{clip.split || 'unassigned'}</dd>
              </div>
              <div className="meta-row">
                <dt>Results</dt>
                <dd>{clip.has_results ? 'Available' : 'Missing'}</dd>
              </div>
              <div className="meta-row">
                <dt>Calibration</dt>
                <dd>{clip.has_calibration ? 'Available' : 'Missing'}</dd>
              </div>
            </dl>
          ) : (
            <p className="hint-text">Select a clip to view details</p>
          )}
        </div>

        <div className="info-section">
          <h3 className="section-title">Overlays</h3>
          <div className="overlay-options">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={overlays.calibration}
                onChange={() => toggleOverlay('calibration')}
              />
              <span>Pitch Calibration</span>
            </label>

            <label className={`checkbox-label ${!ghostAllowed ? 'disabled' : ''}`}>
              <input
                type="checkbox"
                checked={overlays.ghostTrajectory && ghostAllowed}
                disabled={!ghostAllowed}
                onChange={() => toggleOverlay('ghostTrajectory')}
              />
              <span>Ghost Trajectory {!ghostAllowed && '(blind mode)'}</span>
            </label>

            <label className={`checkbox-label ${!ghostAllowed ? 'disabled' : ''}`}>
              <input
                type="checkbox"
                checked={overlays.ghostEvents && ghostAllowed}
                disabled={!ghostAllowed}
                onChange={() => toggleOverlay('ghostEvents')}
              />
              <span>Ghost Events {!ghostAllowed && '(blind mode)'}</span>
            </label>

            <label className="checkbox-label indent-checkbox">
              <input
                type="checkbox"
                checked={overlays.showAllEvents}
                disabled={!overlays.ghostEvents || !ghostAllowed}
                onChange={() => toggleOverlay('showAllEvents')}
              />
              <span>Show All Event Pins</span>
            </label>
          </div>

          <div className="blind-mode-toggle">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={!ghostAllowed}
                onChange={(e) => setGhostAllowed(!e.target.checked)}
              />
              <span className="blind-text">Blind Mode (hide system predictions)</span>
            </label>
          </div>
        </div>

        <div className="info-section shortcuts-section">
          <h3 className="section-title">Navigation Shortcuts</h3>
          <ul className="shortcuts-list">
            <li><kbd>←</kbd> / <kbd>→</kbd> <span>&plusmn;1 Frame</span></li>
            <li><kbd>Shift</kbd> + <kbd>←</kbd> / <kbd>→</kbd> <span>&plusmn;5 Frames</span></li>
            <li><kbd>Home</kbd> / <kbd>End</kbd> <span>First / Last Frame</span></li>
            <li><kbd>Space</kbd> <span>Play / Pause (0.25x)</span></li>
            <li><kbd>[</kbd> / <kbd>]</kbd> <span>Previous / Next Clip</span></li>
            <li><kbd>F</kbd> <span>Fit to Window</span></li>
            <li><kbd>G</kbd> <span>100% Actual Size</span></li>
            <li><kbd>L</kbd> / hold <kbd>Alt</kbd> <span>8x Loupe Magnifier</span></li>
            <li><kbd>Middle / Right Drag</kbd> <span>Pan Viewport</span></li>
            <li><kbd>Scroll Wheel</kbd> <span>Zoom at Cursor</span></li>
          </ul>
        </div>
      </aside>
    </div>
  );
}
