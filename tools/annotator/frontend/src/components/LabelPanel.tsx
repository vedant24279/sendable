import { useState } from 'react';
import type { FC } from 'react';
import { useAnnotatorStore } from '../store';
import { useLabelStore } from '../labelStore';
import { computeGhostVisible } from '../lib/ghost';
import {
  setMeta,
  setImpactType,
  setLbw,
  toggleFlag,
  setNotes,
  setSplit,
  clearEvent,
  adoptSystemEvents,
  ImpactType,
  LBWDecision,
  LabelFlag,
  BallColour,
  BatterHand,
  BowlerType,
  Lighting,
  SplitType,
} from '../lib/labelModel';

export const LabelPanel: FC = () => {
  const annotatorState = useAnnotatorStore();
  const {
    setCurrentFrame,
    prefill,
    selectedClipId,
    clips,
    selectClip,
    autoAdvance,
  } = annotatorState;

  const {
    label,
    dirty,
    saveState,
    saveError,
    issues,
    apply,
    saveDraft,
    finalize,
    flag,
    reopen,
  } = useLabelStore();

  const [flagModalOpen, setFlagModalOpen] = useState(false);
  const [flagNoteInput, setFlagNoteInput] = useState('');

  if (!label) {
    return <div className="panel-loading">No label loaded</div>;
  }

  const ghostVisible = computeGhostVisible(annotatorState);
  const isFinal = label.status === 'final';

  const handleAdopt = () => {
    if (!prefill) return;
    apply((prev) => adoptSystemEvents(prev, prefill));
  };

  const handleFinalize = async () => {
    const ok = await finalize();
    if (ok && autoAdvance) {
      const currIdx = clips.findIndex((c) => c.clip_id === selectedClipId);
      for (let i = 1; i < clips.length; i++) {
        const nextIdx = (currIdx + i) % clips.length;
        if (clips[nextIdx].label_status !== 'final') {
          void selectClip(clips[nextIdx].clip_id);
          break;
        }
      }
    }
  };

  const handleConfirmFlag = () => {
    flag(flagNoteInput.trim() || 'Flagged by annotator');
    setFlagModalOpen(false);
    setFlagNoteInput('');
  };

  return (
    <div className="label-panel-container">
      {/* 1. Header with Save State & Mode Badge */}
      <div className="label-panel-header">
        <h3 className="section-title">Delivery Annotation</h3>
        <div className="save-status-row">
          <span className={`save-badge save-${saveState}`}>
            {saveState === 'saving' && '⏳ Saving...'}
            {saveState === 'saved' && '✓ Saved'}
            {saveState === 'error' && '⚠️ Save Failed'}
            {saveState === 'idle' && (dirty ? '● Unsaved' : 'Idle')}
          </span>
          <span className={`mode-badge mode-${label.mode}`}>
            {label.mode.toUpperCase()}
          </span>
          <span className={`status-pill status-${label.status}`}>
            {label.status}
          </span>
        </div>
        {saveError && <div className="save-error-message">{saveError}</div>}
      </div>

      {/* 2. Action Buttons */}
      <div className="label-actions-group">
        {ghostVisible && (
          <button
            type="button"
            className="action-btn btn-adopt"
            onClick={handleAdopt}
            title="Adopt system predicted release and bounce"
          >
            📥 Adopt System Release+Bounce
          </button>
        )}
        <div className="action-button-row">
          <button
            type="button"
            className="action-btn btn-draft"
            onClick={() => void saveDraft()}
            disabled={saveState === 'saving'}
            title="Save as draft (Ctrl+S)"
          >
            Save Draft <kbd>Ctrl+S</kbd>
          </button>
          <button
            type="button"
            className="action-btn btn-finalize"
            onClick={() => void handleFinalize()}
            disabled={saveState === 'saving'}
            title="Finalize delivery (Ctrl+Enter)"
          >
            Finalize <kbd>Ctrl+↵</kbd>
          </button>
        </div>
        <div className="action-button-row">
          <button
            type="button"
            className="action-btn btn-flag"
            onClick={() => setFlagModalOpen(true)}
          >
            🚩 Flag
          </button>
          {isFinal && (
            <button
              type="button"
              className="action-btn btn-reopen"
              onClick={reopen}
            >
              🔓 Reopen Draft
            </button>
          )}
        </div>
      </div>

      {/* Inline Flag Modal */}
      {flagModalOpen && (
        <div className="flag-input-box">
          <label className="field-label">Reason for Flagging:</label>
          <input
            type="text"
            className="text-input"
            placeholder="e.g. Camera moved, ball obscured..."
            value={flagNoteInput}
            onChange={(e) => setFlagNoteInput(e.target.value)}
            autoFocus
          />
          <div className="flag-btn-row">
            <button type="button" className="small-btn confirm" onClick={handleConfirmFlag}>
              Confirm Flag
            </button>
            <button type="button" className="small-btn cancel" onClick={() => setFlagModalOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* 3. Validation Issues List */}
      {issues.length > 0 && (
        <div className="validation-issues-box">
          <h4 className="issues-title">Validation Issues ({issues.length})</h4>
          <ul className="issues-list">
            {issues.map((issue, idx) => {
              // Extract frame if issue relates to a frame
              let targetFrame: number | null = null;
              if (issue.path.includes('release') && label.release) targetFrame = label.release.frame;
              else if (issue.path.includes('bounce') && label.bounce) targetFrame = label.bounce.frame;
              else if (issue.path.includes('impact') && label.impact?.frame != null) targetFrame = label.impact.frame;
              else if (issue.path.includes('last_visible') && label.last_visible_frame != null) targetFrame = label.last_visible_frame;

              return (
                <li
                  key={idx}
                  className={`issue-item issue-${issue.severity} ${targetFrame != null ? 'clickable' : ''}`}
                  onClick={() => {
                    if (targetFrame != null) setCurrentFrame(targetFrame);
                  }}
                  title={targetFrame != null ? `Jump to frame ${targetFrame}` : undefined}
                >
                  <span className="issue-icon">{issue.severity === 'error' ? '✖' : '▲'}</span>
                  <span className="issue-text">{issue.message}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* 4. Events Table */}
      <div className="events-table-section">
        <h4 className="sub-title">Key Events</h4>
        <table className="events-table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Frame</th>
              <th>Pos (X, Y)</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><span className="event-tag tag-release">Release</span></td>
              <td>{label.release ? label.release.frame : '—'}</td>
              <td>{label.release ? `${label.release.x.toFixed(1)}, ${label.release.y.toFixed(1)}` : '—'}</td>
              <td>
                <div className="row-actions">
                  {label.release && (
                    <button
                      type="button"
                      className="table-action-btn"
                      onClick={() => setCurrentFrame(label.release!.frame)}
                      title="Jump to frame"
                    >
                      Go
                    </button>
                  )}
                  {label.release && (
                    <button
                      type="button"
                      className="table-action-btn clear"
                      onClick={() => apply((l) => clearEvent(l, 'release', { ghostVisible }))}
                      title="Clear release"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </td>
            </tr>
            <tr>
              <td><span className="event-tag tag-bounce">Bounce</span></td>
              <td>{label.bounce ? label.bounce.frame : '—'}</td>
              <td>{label.bounce ? `${label.bounce.x.toFixed(1)}, ${label.bounce.y.toFixed(1)}` : '—'}</td>
              <td>
                <div className="row-actions">
                  {label.bounce && (
                    <button
                      type="button"
                      className="table-action-btn"
                      onClick={() => setCurrentFrame(label.bounce!.frame)}
                      title="Jump to frame"
                    >
                      Go
                    </button>
                  )}
                  {label.bounce && (
                    <button
                      type="button"
                      className="table-action-btn clear"
                      onClick={() => apply((l) => clearEvent(l, 'bounce', { ghostVisible }))}
                      title="Clear bounce"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </td>
            </tr>
            <tr>
              <td>
                <span className="event-tag tag-impact">
                  Impact {label.impact?.type ? `(${label.impact.type})` : ''}
                </span>
              </td>
              <td>{label.impact?.frame != null ? label.impact.frame : '—'}</td>
              <td>
                {label.impact?.x != null && label.impact?.y != null
                  ? `${label.impact.x.toFixed(1)}, ${label.impact.y.toFixed(1)}`
                  : '—'}
              </td>
              <td>
                <div className="row-actions">
                  {label.impact?.frame != null && (
                    <button
                      type="button"
                      className="table-action-btn"
                      onClick={() => setCurrentFrame(label.impact!.frame!)}
                      title="Jump to frame"
                    >
                      Go
                    </button>
                  )}
                  {label.impact && (
                    <button
                      type="button"
                      className="table-action-btn clear"
                      onClick={() => apply((l) => clearEvent(l, 'impact', { ghostVisible }))}
                      title="Clear impact"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </td>
            </tr>
            <tr>
              <td><span className="event-tag tag-end">Last Visible</span></td>
              <td>{label.last_visible_frame != null ? label.last_visible_frame : '—'}</td>
              <td>—</td>
              <td>
                <div className="row-actions">
                  {label.last_visible_frame != null && (
                    <button
                      type="button"
                      className="table-action-btn"
                      onClick={() => setCurrentFrame(label.last_visible_frame!)}
                      title="Jump to frame"
                    >
                      Go
                    </button>
                  )}
                  {label.last_visible_frame != null && (
                    <button
                      type="button"
                      className="table-action-btn clear"
                      onClick={() => apply((l) => clearEvent(l, 'last_visible', { ghostVisible }))}
                      title="Clear last visible frame"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* 5. Impact Type Selection */}
      <div className="form-group">
        <label className="field-label">
          Impact Type <span className="req-star">*</span>
        </label>
        <div className="impact-btn-group">
          {(['bat', 'pad', 'stumps', 'none'] as ImpactType[]).map((t, idx) => (
            <button
              key={t}
              type="button"
              className={`impact-btn ${label.impact?.type === t ? 'active' : ''}`}
              onClick={() => apply((l) => setImpactType(l, t, { ghostVisible }))}
            >
              <kbd>{idx + 1}</kbd> {t}
            </button>
          ))}
        </div>
      </div>

      {/* 6. LBW Decision (Only enabled when impact type is pad) */}
      <div className="form-group">
        <label className="field-label">LBW Decision (pad impact only)</label>
        <select
          className="select-input"
          value={label.lbw ?? ''}
          disabled={label.impact?.type !== 'pad'}
          onChange={(e) => {
            const val = e.target.value as LBWDecision;
            apply((l) => setLbw(l, val || null, { ghostVisible }));
          }}
        >
          <option value="">None / Not Applicable</option>
          <option value="out">Out</option>
          <option value="not_out_pitched_leg">Not Out (Pitched Outside Leg)</option>
          <option value="not_out_impact_outside">Not Out (Impact Outside Off)</option>
          <option value="not_out_missing">Not Out (Missing Wickets)</option>
          <option value="umpires_call">Umpire's Call</option>
        </select>
      </div>

      {/* 7. Metadata Attributes */}
      <div className="metadata-fields-grid">
        <div className="form-group">
          <label className="field-label">
            Ball Colour <span className="req-star">*</span>
          </label>
          <select
            className="select-input"
            value={label.ball_colour ?? ''}
            onChange={(e) =>
              apply((l) => setMeta(l, 'ball_colour', (e.target.value as BallColour) || null, { ghostVisible }))
            }
          >
            <option value="">Select...</option>
            <option value="white">White</option>
            <option value="red">Red</option>
            <option value="pink">Pink</option>
          </select>
        </div>

        <div className="form-group">
          <label className="field-label">
            Batter Hand <span className="req-star">*</span>
          </label>
          <select
            className="select-input"
            value={label.batter_hand ?? ''}
            onChange={(e) =>
              apply((l) => setMeta(l, 'batter_hand', (e.target.value as BatterHand) || null, { ghostVisible }))
            }
          >
            <option value="">Select...</option>
            <option value="right">Right</option>
            <option value="left">Left</option>
          </select>
        </div>

        <div className="form-group">
          <label className="field-label">Bowler Type</label>
          <select
            className="select-input"
            value={label.bowler_type ?? ''}
            onChange={(e) =>
              apply((l) => setMeta(l, 'bowler_type', (e.target.value as BowlerType) || null, { ghostVisible }))
            }
          >
            <option value="">Unspecified</option>
            <option value="pace">Pace</option>
            <option value="spin">Spin</option>
          </select>
        </div>

        <div className="form-group">
          <label className="field-label">Lighting</label>
          <select
            className="select-input"
            value={label.lighting ?? ''}
            onChange={(e) =>
              apply((l) => setMeta(l, 'lighting', (e.target.value as Lighting) || null, { ghostVisible }))
            }
          >
            <option value="">Unspecified</option>
            <option value="bright">Bright</option>
            <option value="overcast">Overcast</option>
            <option value="low">Low</option>
          </select>
        </div>

        <div className="form-group">
          <label className="field-label">Delivery Split</label>
          <select
            className="select-input"
            value={label.split ?? ''}
            onChange={(e) =>
              apply((l) => setSplit(l, (e.target.value as SplitType) || null, { ghostVisible }))
            }
          >
            <option value="">Unassigned</option>
            <option value="dev">Dev</option>
            <option value="final">Final</option>
          </select>
        </div>
      </div>

      {/* 8. Delivery Flags */}
      <div className="form-group">
        <label className="field-label">Flags</label>
        <div className="flags-grid">
          {(['ball_not_visible', 'camera_moved', 'bad_calibration', 'unclear'] as LabelFlag[]).map((f) => (
            <label key={f} className="flag-checkbox-label">
              <input
                type="checkbox"
                checked={label.flags.includes(f)}
                onChange={() => apply((l) => toggleFlag(l, f, { ghostVisible }))}
              />
              <span>{f.replace(/_/g, ' ')}</span>
            </label>
          ))}
        </div>
      </div>

      {/* 9. Notes */}
      <div className="form-group">
        <label className="field-label">Notes</label>
        <textarea
          className="textarea-input"
          rows={3}
          placeholder="Add delivery annotation notes..."
          value={label.notes}
          onChange={(e) => apply((l) => setNotes(l, e.target.value, { ghostVisible }))}
        />
      </div>
    </div>
  );
};
