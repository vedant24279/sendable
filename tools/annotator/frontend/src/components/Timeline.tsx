import { useCallback, useMemo, useRef } from 'react';
import { useAnnotatorStore } from '../store';
import { useLabelStore } from '../labelStore';
import { frameToTime } from '../lib/viewport';
import { computeGhostVisible } from '../lib/ghost';

export const Timeline = () => {
  const annotatorState = useAnnotatorStore();
  const { selectedClipId, clips, currentFrame, setCurrentFrame, prefill } = annotatorState;
  const label = useLabelStore((s) => s.label);

  const clip = useMemo(() => clips.find((c) => c.clip_id === selectedClipId), [clips, selectedClipId]);
  const frameCount = clip ? clip.frame_count : 0;
  const fps = clip ? clip.fps : 30;

  const trackRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  // Map trajectory points by frame for fast tick styling
  const trajByFrame = useMemo(() => {
    const map = new Map<number, { interpolated: boolean }>();
    if (prefill?.trajectory) {
      prefill.trajectory.forEach((pt) => {
        map.set(pt.frame, { interpolated: pt.interpolated });
      });
    }
    return map;
  }, [prefill]);

  // Scrub calculation
  const updateFrameFromEvent = useCallback(
    (clientX: number) => {
      if (!trackRef.current || frameCount <= 1) return;
      const rect = trackRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      const targetFrame = Math.round(ratio * (frameCount - 1));
      setCurrentFrame(targetFrame);
    },
    [frameCount, setCurrentFrame]
  );

  const handleMouseDown = (e: React.MouseEvent) => {
    isDraggingRef.current = true;
    updateFrameFromEvent(e.clientX);

    const onMouseMove = (moveEvent: MouseEvent) => {
      if (isDraggingRef.current) {
        updateFrameFromEvent(moveEvent.clientX);
      }
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };

    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
  };

  if (!clip || frameCount === 0) {
    return <div className="timeline-container disabled">No clip selected</div>;
  }

  const events = prefill?.events;
  const ghostVisible = computeGhostVisible(annotatorState);

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <span className="timeline-time">
          Frame {currentFrame} / {frameCount - 1} &bull; {frameToTime(currentFrame, fps).toFixed(3)}s
        </span>
        <div className="timeline-legend">
          <span className="legend-item"><span className="legend-dot solid-dot"></span> Detected</span>
          <span className="legend-item"><span className="legend-dot hollow-dot"></span> Interpolated</span>
        </div>
      </div>

      <div className="timeline-track-wrapper" ref={trackRef} onMouseDown={handleMouseDown}>
        <div className="timeline-ticks">
          {Array.from({ length: frameCount }).map((_, idx) => {
            const traj = trajByFrame.get(idx);
            let tickClass = 'tick-none';
            if (traj) {
              tickClass = traj.interpolated ? 'tick-interpolated' : 'tick-detected';
            }
            return (
              <div
                key={idx}
                className={`timeline-tick ${tickClass} ${idx === currentFrame ? 'tick-current' : ''}`}
                style={{ left: `${(idx / (frameCount - 1)) * 100}%` }}
              />
            );
          })}
        </div>

        {/* System Ghost Event Markers (Only drawn when ghost is visible) */}
        {ghostVisible && events?.release && events.release.frame >= 0 && (
          <div
            className="event-marker ghost-marker marker-release"
            style={{ left: `${(events.release.frame / (frameCount - 1)) * 100}%` }}
            title={`System Release (f:${events.release.frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(events.release!.frame); }}
          >
            <span>R</span>
          </div>
        )}
        {ghostVisible && events?.bounce && events.bounce.frame >= 0 && (
          <div
            className="event-marker ghost-marker marker-bounce"
            style={{ left: `${(events.bounce.frame / (frameCount - 1)) * 100}%` }}
            title={`System Bounce (f:${events.bounce.frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(events.bounce!.frame); }}
          >
            <span>B</span>
          </div>
        )}
        {ghostVisible && events?.deviation && events.deviation.frame >= 0 && (
          <div
            className="event-marker ghost-marker marker-deviation"
            style={{ left: `${(events.deviation.frame / (frameCount - 1)) * 100}%` }}
            title={`System Deviation (f:${events.deviation.frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(events.deviation!.frame); }}
          >
            <span>D</span>
          </div>
        )}
        {ghostVisible && events?.impact && events.impact.frame != null && events.impact.frame >= 0 && (
          <div
            className="event-marker ghost-marker marker-impact"
            style={{ left: `${(events.impact.frame / (frameCount - 1)) * 100}%` }}
            title={`System Impact (${events.impact.type || ''} f:${events.impact.frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(events.impact!.frame!); }}
          >
            <span>H</span>
          </div>
        )}

        {/* User Label Event Markers (Always drawn) */}
        {label?.release && label.release.frame >= 0 && (
          <div
            className="event-marker label-marker marker-release"
            style={{ left: `${(label.release.frame / (frameCount - 1)) * 100}%` }}
            title={`Label Release (f:${label.release.frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(label.release!.frame); }}
          >
            <span>R</span>
          </div>
        )}
        {label?.bounce && label.bounce.frame >= 0 && (
          <div
            className="event-marker label-marker marker-bounce"
            style={{ left: `${(label.bounce.frame / (frameCount - 1)) * 100}%` }}
            title={`Label Bounce (f:${label.bounce.frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(label.bounce!.frame); }}
          >
            <span>B</span>
          </div>
        )}
        {label?.impact && label.impact.frame != null && label.impact.frame >= 0 && (
          <div
            className="event-marker label-marker marker-impact"
            style={{ left: `${(label.impact.frame / (frameCount - 1)) * 100}%` }}
            title={`Label Impact (${label.impact.type} f:${label.impact.frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(label.impact!.frame!); }}
          >
            <span>H</span>
          </div>
        )}
        {label?.last_visible_frame != null && label.last_visible_frame >= 0 && (
          <div
            className="event-marker label-marker marker-end"
            style={{ left: `${(label.last_visible_frame / (frameCount - 1)) * 100}%` }}
            title={`Label Last Visible (f:${label.last_visible_frame})`}
            onClick={(e) => { e.stopPropagation(); setCurrentFrame(label.last_visible_frame!); }}
          >
            <span>END</span>
          </div>
        )}

        {/* Current playhead */}
        <div
          className="timeline-playhead"
          style={{ left: `${(currentFrame / (frameCount - 1)) * 100}%` }}
        />
      </div>
    </div>
  );
};
