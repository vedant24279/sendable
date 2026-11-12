import { useMemo } from 'react';
import type { FC } from 'react';
import { useAnnotatorStore } from '../store';
import { useLabelStore } from '../labelStore';
import { computeGhostVisible } from '../lib/ghost';
import {
  acceptSystemCalibration,
  resetCalibrationToSystem,
  clearCalibration,
  clearCalibrationPoint,
} from '../lib/labelModel';
import {
  CALIB_POINT_NAMES,
  CALIB_WARN_PX,
  CALIB_ERROR_PX,
  CalibrationPointName,
} from '../lib/calibConstants';
import { CALIB_HANDLE_COLORS, CALIB_POINT_LABELS } from '../lib/calibUi';
import { fitHomography, pixelToWorld } from '../lib/calibration';

export const CalibrationPanel: FC = () => {
  const annotatorState = useAnnotatorStore();
  const {
    prefill,
    selectedCalibPoint,
    setSelectedCalibPoint,
    setViewport,
    setCalibrationMode,
  } = annotatorState;

  const { label, issues, apply } = useLabelStore();

  const ghostVisible = computeGhostVisible(annotatorState);
  const calibGT = label?.calibration_gt;
  const points = calibGT?.points || ({} as Record<CalibrationPointName, [number, number]>);
  const source = calibGT?.source || 'none';
  const residual = calibGT?.residual_px;

  // Residual color class
  const residualClass = useMemo(() => {
    if (residual == null) return 'residual-none';
    if (residual < CALIB_WARN_PX) return 'residual-pass';
    if (residual <= CALIB_ERROR_PX) return 'residual-warn';
    return 'residual-error';
  }, [residual]);

  // Compute Stump check Z coordinates via homography (Amendment D)
  const stumpCheck = useMemo(() => {
    const batPt = points.bat_stump;
    const bowlPt = points.bowl_stump;
    if (!batPt || !bowlPt) {
      return { batZ: null, bowlZ: null };
    }

    // Check if 4 corners are present to fit H
    const cornersPresent =
      points.bat_L && points.bat_R && points.bowl_L && points.bowl_R;
    if (!cornersPresent) {
      return { batZ: null, bowlZ: null };
    }

    try {
      const fit = fitHomography(points as Record<CalibrationPointName, [number, number]>);
      const [, batZ] = pixelToWorld(fit.H, batPt[0], batPt[1]);
      const [, bowlZ] = pixelToWorld(fit.H, bowlPt[0], bowlPt[1]);
      return { batZ, bowlZ };
    } catch {
      return { batZ: null, bowlZ: null };
    }
  }, [points]);

  // Filter issues for calibration
  const calibIssues = useMemo(() => {
    return issues.filter((i) => i.path.startsWith('calibration_gt'));
  }, [issues]);

  const handleAcceptSystem = () => {
    if (!prefill?.calibration) return;
    apply((prev) =>
      acceptSystemCalibration(prev, prefill.calibration, { ghostVisible })
    );
  };

  const handleResetSystem = () => {
    if (!prefill?.calibration) return;
    apply((prev) =>
      resetCalibrationToSystem(prev, prefill.calibration, { ghostVisible })
    );
  };

  const handleClearAll = () => {
    apply((prev) => clearCalibration(prev, { ghostVisible }));
  };

  const handleClearPoint = (name: CalibrationPointName) => {
    apply((prev) =>
      clearCalibrationPoint(prev, name, prefill?.calibration, { ghostVisible })
    );
  };

  const handleGoToPoint = (name: CalibrationPointName) => {
    setSelectedCalibPoint(name);
    const pt = points[name];
    if (pt) {
      // Zoom to 4x centered on point
      setViewport((prev) => ({
        ...prev,
        scale: 4.0,
        offsetX: 400 - pt[0] * 4.0,
        offsetY: 300 - pt[1] * 4.0,
      }));
    }
  };

  return (
    <div className="calib-panel-container">
      {/* Header */}
      <div className="calib-panel-header">
        <div className="calib-header-title-row">
          <h3 className="section-title">📐 Pitch Calibration</h3>
          <button
            className="calib-exit-btn"
            onClick={() => setCalibrationMode(false)}
            title="Exit Calibration Mode (C)"
          >
            ✕ Close
          </button>
        </div>
        <div className="calib-meta-badges">
          <span className="calib-source-badge">
            Source: <strong>{source}</strong>
          </span>
          <span className={`calib-residual-badge ${residualClass}`}>
            Stump residual:{' '}
            <strong>
              {residual != null ? `${residual.toFixed(1)} px` : '—'}
            </strong>
          </span>
        </div>
      </div>

      {/* Stump Check Readout (Amendment D) */}
      <div className="calib-stump-check-box">
        <span className="stump-check-label">Stump check:</span>
        <span className="stump-check-value">
          bat end Z ={' '}
          {stumpCheck.batZ != null ? `${stumpCheck.batZ.toFixed(2)} m` : '—'}{' '}
          <span className="expected-text">(expected 0.00)</span> | bowl end Z ={' '}
          {stumpCheck.bowlZ != null ? `${stumpCheck.bowlZ.toFixed(2)} m` : '—'}{' '}
          <span className="expected-text">(expected 20.12)</span>
        </span>
      </div>

      {/* Calibration Issues */}
      {calibIssues.length > 0 && (
        <div className="calib-issues-list">
          {calibIssues.map((issue, idx) => (
            <div key={idx} className={`calib-issue-item issue-${issue.severity}`}>
              <span className="issue-icon">
                {issue.severity === 'error' ? '❌' : '⚠️'}
              </span>
              <span className="issue-msg">{issue.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* 6 Calibration Points Table */}
      <div className="calib-points-table-wrapper">
        <table className="calib-points-table">
          <thead>
            <tr>
              <th>Point</th>
              <th>Coords (px)</th>
              <th className="actions-header">Actions</th>
            </tr>
          </thead>
          <tbody>
            {CALIB_POINT_NAMES.map((name) => {
              const pt = points[name];
              const isSelected = selectedCalibPoint === name;
              const color = CALIB_HANDLE_COLORS[name];
              const labelText = CALIB_POINT_LABELS[name];

              return (
                <tr
                  key={name}
                  className={`calib-row ${isSelected ? 'row-selected' : ''}`}
                  onClick={() => setSelectedCalibPoint(name)}
                >
                  <td className="point-name-cell">
                    <span
                      className="calib-color-swatch"
                      style={{ backgroundColor: color }}
                    />
                    <div className="point-text-wrap">
                      <span className="point-code">{name}</span>
                      <span className="point-desc">{labelText}</span>
                    </div>
                  </td>
                  <td className="point-coords-cell mono-text">
                    {pt ? `${pt[0].toFixed(1)}, ${pt[1].toFixed(1)}` : '—'}
                  </td>
                  <td className="point-actions-cell" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="btn-tiny btn-go"
                      disabled={!pt}
                      onClick={() => handleGoToPoint(name)}
                      title="Center and zoom to 4x on this handle"
                    >
                      Go
                    </button>
                    <button
                      className="btn-tiny btn-clear"
                      disabled={!pt}
                      onClick={() => handleClearPoint(name)}
                      title="Clear this point"
                    >
                      Clear
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Global Actions */}
      <div className="calib-actions-row">
        <button
          className="btn-secondary btn-action"
          onClick={handleAcceptSystem}
          disabled={!prefill?.calibration}
          title="Accept the system's predicted calibration points"
        >
          Accept system calibration
        </button>
        <button
          className="btn-secondary btn-action"
          onClick={handleResetSystem}
          disabled={!prefill?.calibration}
          title="Reset calibration points to system prefill"
        >
          Reset to system
        </button>
        <button
          className="btn-danger btn-action"
          onClick={handleClearAll}
          disabled={!calibGT}
          title="Clear all calibration ground-truth points"
        >
          Clear all
        </button>
      </div>

      {/* Hints (Amendment B) */}
      <div className="calib-hints-box">
        <p className="hint-line">
          💡 <strong>Hint:</strong> Click the ground point directly below the middle
          stump. If the base is hidden by the batter, use the visible part of the
          stumps and go straight down to the ground.
        </p>
        <p className="hint-line">
          🎥 Check the first and last frame; if the grid leaves the painted
          creases the camera moved: tick <code>camera_moved</code>.
        </p>
        <p className="hint-shortcuts">
          <kbd>Tab</kbd> / <kbd>Shift+Tab</kbd> cycles handles. <kbd>Ctrl+Arrow</kbd>{' '}
          nudges 1 px (<kbd>Shift</kbd> for 0.1 px).
        </p>
      </div>
    </div>
  );
};
