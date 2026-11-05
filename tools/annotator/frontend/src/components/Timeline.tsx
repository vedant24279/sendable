import { useCallback, useMemo, useRef } from 'react';
import { useAnnotatorStore } from '../store';
import { frameToTime } from '../lib/viewport';

export const Timeline = () => {
  const selectedClipId = useAnnotatorStore((s) => s.selectedClipId);
  const clips = useAnnotatorStore((s) => s.clips);
  const currentFrame = useAnnotatorStore((s) => s.currentFrame);
  const setCurrentFrame = useAnnotatorStore((s) => s.setCurrentFrame);
  const prefill = useAnnotatorStore((s) => s.prefill);

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

        {/* Event Markers */}
        {events?.release && events.release.frame >= 0 && (
          <div
            className="event-marker marker-release"
            style={{ left: `${(events.release.frame / (frameCount - 1)) * 100}%` }}
            title={`Release (frame ${events.release.frame})`}
          >
            <span>R</span>
          </div>
        )}
        {events?.bounce && events.bounce.frame >= 0 && (
          <div
            className="event-marker marker-bounce"
            style={{ left: `${(events.bounce.frame / (frameCount - 1)) * 100}%` }}
            title={`Bounce (frame ${events.bounce.frame})`}
          >
            <span>B</span>
          </div>
        )}
        {events?.deviation && events.deviation.frame >= 0 && (
          <div
            className="event-marker marker-deviation"
            style={{ left: `${(events.deviation.frame / (frameCount - 1)) * 100}%` }}
            title={`Deviation (frame ${events.deviation.frame})`}
          >
            <span>D</span>
          </div>
        )}
        {events?.impact && events.impact.frame != null && events.impact.frame >= 0 && (
          <div
            className="event-marker marker-impact"
            style={{ left: `${(events.impact.frame / (frameCount - 1)) * 100}%` }}
            title={`Impact (${events.impact.type || ''} frame ${events.impact.frame})`}
          >
            <span>I</span>
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
