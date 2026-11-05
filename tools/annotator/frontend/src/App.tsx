import { useEffect } from 'react';
import { useAnnotatorStore } from './store';
import { useLabelStore } from './labelStore';
import { useHotkeys } from './hooks/useHotkeys';
import { ClipList } from './components/ClipList';
import { Viewer } from './components/Viewer';
import { Timeline } from './components/Timeline';
import { LabelPanel } from './components/LabelPanel';

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
  const autoAdvance = useAnnotatorStore((s) => s.autoAdvance);
  const setAutoAdvance = useAnnotatorStore((s) => s.setAutoAdvance);
  const annotatorName = useAnnotatorStore((s) => s.annotatorName);
  const setAnnotatorName = useAnnotatorStore((s) => s.setAnnotatorName);

  // Activate keyboard shortcuts
  useHotkeys();

  // Read ?annotator= on mount (default: 'vedant')
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const annotatorParam = params.get('annotator');
    if (annotatorParam && annotatorParam.trim()) {
      setAnnotatorName(annotatorParam.trim());
    }
  }, [setAnnotatorName]);

  // Load clips on mount
  useEffect(() => {
    void loadClips();
  }, [loadClips]);

  // Load label whenever selected clip or annotator changes
  useEffect(() => {
    if (selectedClipId) {
      void useLabelStore.getState().load(selectedClipId, annotatorName);
    }
  }, [selectedClipId, annotatorName]);

  // Warn on tab/window close if dirty or currently saving
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      const { dirty, saveState } = useLabelStore.getState();
      if (dirty || saveState === 'saving') {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Leave anyway?';
        return 'You have unsaved changes. Leave anyway?';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  const clip = clips.find((c) => c.clip_id === selectedClipId);
  const finalCount = clips.filter((c) => c.label_status === 'final').length;
  const totalCount = clips.length;

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
            <span className="progress-counter" title="Finalized deliveries count">
              Final: {finalCount} / {totalCount}
            </span>
            <span className="annotator-pill" title="Active annotator">
              👤 {annotatorName}
            </span>
          </div>
          <div className="toolbar-controls">
            <label className="toolbar-checkbox" title="Automatically select the next non-final clip upon finalizing">
              <input
                type="checkbox"
                checked={autoAdvance}
                onChange={(e) => setAutoAdvance(e.target.checked)}
              />
              <span>Auto-advance after finalize</span>
            </label>
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
        {/* Label and Annotation Management */}
        <LabelPanel />

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
          <h3 className="section-title">Annotation Shortcuts</h3>
          <ul className="shortcuts-list">
            <li><kbd>R</kbd> / <kbd>B</kbd> / <kbd>H</kbd> <span>Arm Release / Bounce / Impact</span></li>
            <li><kbd>E</kbd> <span>Set Last Visible Frame</span></li>
            <li><kbd>1</kbd>–<kbd>4</kbd> <span>Impact: Bat, Pad, Stumps, None</span></li>
            <li><kbd>Ctrl</kbd> + <kbd>Z</kbd> / <kbd>Y</kbd> <span>Undo / Redo</span></li>
            <li><kbd>Ctrl</kbd> + <kbd>S</kbd> <span>Save Draft</span></li>
            <li><kbd>Ctrl</kbd> + <kbd>↵</kbd> <span>Finalize</span></li>
            <li><kbd>Ctrl</kbd> + <kbd>Arrows</kbd> <span>Nudge Pin (&plusmn;1px, Shift: &plusmn;10px)</span></li>
            <li><kbd>Esc</kbd> <span>Disarm Tool / Deselect Pin</span></li>
            <li><kbd>←</kbd> / <kbd>→</kbd> <span>&plusmn;1 Frame (Shift: &plusmn;5)</span></li>
            <li><kbd>Space</kbd> <span>Play / Pause</span></li>
            <li><kbd>[</kbd> / <kbd>]</kbd> <span>Previous / Next Clip</span></li>
            <li><kbd>F</kbd> / <kbd>G</kbd> <span>Fit to Window / 100% Size</span></li>
            <li><kbd>L</kbd> / hold <kbd>Alt</kbd> <span>8x Loupe Magnifier</span></li>
          </ul>
        </div>
      </aside>
    </div>
  );
}
