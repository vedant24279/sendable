import { useEffect, useRef, useCallback, useState } from 'react';
import type { FC } from 'react';
import { useAnnotatorStore } from '../store';
import { useLabelStore } from '../labelStore';
import {
  screenToImage,
  imageToScreen,
  zoomAt,
  fit,
  frameToTime,
  Point,
  Viewport,
} from '../lib/viewport';
import { frameCache } from '../lib/frameCache';
import { computeGhostVisible } from '../lib/ghost';
import { pinsForFrame, hitTestPin } from '../lib/pins';
import { placeEvent, round1 } from '../lib/labelModel';

export const Viewer: FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);

  const annotatorState = useAnnotatorStore();
  const {
    selectedClipId,
    clips,
    currentFrame,
    prefill,
    viewport,
    setViewport,
    overlays,
    loupeEnabled,
    altHeld,
    armedTool,
    setArmedTool,
    selectedPin,
    setSelectedPin,
  } = annotatorState;

  const { label, apply } = useLabelStore();

  const clip = clips.find((c) => c.clip_id === selectedClipId);

  // Transient warning for impact without type
  const [impactWarning, setImpactWarning] = useState<string | null>(null);

  // Mutable refs to prevent React re-renders on mouse movement
  const mousePosRef = useRef<Point>({ x: 0, y: 0 });
  const isMouseOverRef = useRef<boolean>(false);
  const isPanningRef = useRef<boolean>(false);
  const panStartRef = useRef<{ x: number; y: number; ox: number; oy: number }>({
    x: 0,
    y: 0,
    ox: 0,
    oy: 0,
  });

  // Pin drag handling refs
  const isDraggingPinRef = useRef<boolean>(false);
  const dragCurrentImgPosRef = useRef<{ x: number; y: number } | null>(null);

  const viewDimensionsRef = useRef<{ w: number; h: number }>({ w: 800, h: 600 });
  const viewportRef = useRef<Viewport>(viewport);
  viewportRef.current = viewport;

  // Track if user has manually adjusted zoom or pan
  const hasManualAdjustmentRef = useRef<boolean>(false);

  // Fit view helper
  const handleFit = useCallback(() => {
    hasManualAdjustmentRef.current = false;
    if (!clip) return;
    const { w, h } = viewDimensionsRef.current;
    if (w <= 0 || h <= 0) return;
    const fitted = fit(clip.width, clip.height, w, h);
    setViewport(fitted);
  }, [clip, setViewport]);

  // 100% zoom helper
  const handleActualSize = useCallback(() => {
    hasManualAdjustmentRef.current = true;
    if (!clip) return;
    const { w, h } = viewDimensionsRef.current;
    setViewport({
      scale: 1.0,
      offsetX: (w - clip.width) / 2,
      offsetY: (h - clip.height) / 2,
    });
  }, [clip, setViewport]);

  // Update status bar directly in DOM without React state updates
  const updateStatusBar = useCallback(
    (cursorScreen?: Point) => {
      if (!statusRef.current || !clip) return;

      if (armedTool) {
        statusRef.current.textContent = `Tool: ${armedTool} - click to place`;
        return;
      }

      const vp = viewportRef.current;
      const t = frameToTime(currentFrame, clip.fps).toFixed(3);
      const zoomPct = (vp.scale * 100).toFixed(0);

      let cursorStr = 'cursor (—, —)';
      if (cursorScreen) {
        const imgPt = screenToImage(cursorScreen, vp);
        cursorStr = `cursor (${imgPt.x.toFixed(1)}, ${imgPt.y.toFixed(1)})`;
      }

      statusRef.current.textContent = `Frame ${currentFrame} / ${clip.frame_count - 1}   t = ${t} s   ${cursorStr}   zoom ${zoomPct}%`;
    },
    [clip, currentFrame, armedTool]
  );

  // Main canvas drawing function
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !clip) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { w: viewW, h: viewH } = viewDimensionsRef.current;
    const dpr = window.devicePixelRatio || 1;
    const vp = viewportRef.current;

    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);

    // 1. Background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, viewW, viewH);

    // 2. Frame image
    const bitmap = frameCache.getFrame(clip.clip_id, currentFrame);
    if (!bitmap) {
      // Loading placeholder
      ctx.fillStyle = '#94a3b8';
      ctx.font = '14px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`Loading frame ${currentFrame}...`, viewW / 2, viewH / 2);
    } else {
      ctx.imageSmoothingEnabled = vp.scale < 2.0;
      const destX = vp.offsetX;
      const destY = vp.offsetY;
      const destW = clip.width * vp.scale;
      const destH = clip.height * vp.scale;
      ctx.drawImage(bitmap, destX, destY, destW, destH);
    }

    // 3. Calibration Overlay
    if (overlays.calibration && prefill?.calibration) {
      const calibMap = new Map<string, Point>();
      prefill.calibration.forEach((pt) => calibMap.set(pt.name, { x: pt.x, y: pt.y }));

      const bowlL = calibMap.get('bowl_L');
      const bowlR = calibMap.get('bowl_R');
      const batR = calibMap.get('bat_R');
      const batL = calibMap.get('bat_L');

      if (bowlL && bowlR && batR && batL) {
        const sBowlL = imageToScreen(bowlL, vp);
        const sBowlR = imageToScreen(bowlR, vp);
        const sBatR = imageToScreen(batR, vp);
        const sBatL = imageToScreen(batL, vp);

        ctx.beginPath();
        ctx.moveTo(sBowlL.x, sBowlL.y);
        ctx.lineTo(sBowlR.x, sBowlR.y);
        ctx.lineTo(sBatR.x, sBatR.y);
        ctx.lineTo(sBatL.x, sBatL.y);
        ctx.closePath();

        ctx.strokeStyle = '#22c55e';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = 'rgba(34, 197, 94, 0.08)';
        ctx.fill();
      }

      ['bat_stump', 'bowl_stump'].forEach((stumpName) => {
        const pt = calibMap.get(stumpName);
        if (pt) {
          const sPt = imageToScreen(pt, vp);
          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#22c55e';
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1;
          ctx.stroke();

          ctx.font = '10px system-ui, sans-serif';
          ctx.fillStyle = '#22c55e';
          ctx.textAlign = 'left';
          ctx.fillText(stumpName, sPt.x + 6, sPt.y + 3);
        }
      });
    }

    const ghostVisible = computeGhostVisible(annotatorState);

    // 4. Ghost Trajectory Overlay (only if ghostVisible)
    if (ghostVisible && overlays.ghostTrajectory && prefill?.trajectory) {
      const traj = prefill.trajectory;

      if (traj.length > 1) {
        ctx.beginPath();
        const first = imageToScreen(traj[0], vp);
        ctx.moveTo(first.x, first.y);
        for (let i = 1; i < traj.length; i++) {
          const pt = imageToScreen(traj[i], vp);
          ctx.lineTo(pt.x, pt.y);
        }
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.4)';
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      traj.forEach((pt) => {
        const sPt = imageToScreen(pt, vp);
        const isCurrent = pt.frame === currentFrame;

        if (isCurrent) {
          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, 7, 0, Math.PI * 2);
          ctx.strokeStyle = '#facc15';
          ctx.lineWidth = 2.5;
          ctx.stroke();

          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, 3, 0, Math.PI * 2);
          ctx.fillStyle = '#facc15';
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, 3, 0, Math.PI * 2);
          if (pt.interpolated) {
            ctx.strokeStyle = '#38bdf8';
            ctx.lineWidth = 1.5;
            ctx.stroke();
          } else {
            ctx.fillStyle = '#38bdf8';
            ctx.fill();
          }
        }
      });
    }

    // 5. Ghost Events Overlay (only if ghostVisible)
    if (ghostVisible && overlays.ghostEvents && prefill?.events) {
      const evs = prefill.events;
      const eventList: Array<{ name: string; pt: Point; frame: number; color: string }> = [];

      if (evs.release && evs.release.frame >= 0) {
        eventList.push({ name: 'Release', pt: evs.release, frame: evs.release.frame, color: '#f97316' });
      }
      if (evs.bounce && evs.bounce.frame >= 0) {
        eventList.push({ name: 'Bounce', pt: evs.bounce, frame: evs.bounce.frame, color: '#ec4899' });
      }
      if (evs.deviation && evs.deviation.frame >= 0) {
        eventList.push({ name: 'Deviation', pt: evs.deviation, frame: evs.deviation.frame, color: '#06b6d4' });
      }
      if (evs.impact && evs.impact.frame != null && evs.impact.x != null && evs.impact.y != null) {
        eventList.push({
          name: `Impact (${evs.impact.type || ''})`,
          pt: { x: evs.impact.x, y: evs.impact.y },
          frame: evs.impact.frame,
          color: '#ef4444',
        });
      }

      eventList.forEach((ev) => {
        if (overlays.showAllEvents || ev.frame === currentFrame) {
          const sPt = imageToScreen(ev.pt, vp);

          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, 5, 0, Math.PI * 2);
          ctx.fillStyle = ev.color;
          ctx.fill();
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 1.5;
          ctx.stroke();

          ctx.font = 'bold 11px system-ui, sans-serif';
          ctx.fillStyle = ev.color;
          ctx.textAlign = 'left';
          ctx.fillText(`Ghost ${ev.name} [f:${ev.frame}]`, sPt.x + 8, sPt.y + 4);
        }
      });
    }

    // 6. Label Annotation Pins (Release, Bounce, Impact)
    const pins = pinsForFrame(label, currentFrame, overlays.showAllEvents);
    pins.forEach((pin) => {
      // If currently dragging this pin, use drag position preview
      const isCurrentlyDragged =
        isDraggingPinRef.current &&
        selectedPin?.kind === pin.kind &&
        dragCurrentImgPosRef.current != null;

      const px = isCurrentlyDragged ? dragCurrentImgPosRef.current!.x : pin.x;
      const py = isCurrentlyDragged ? dragCurrentImgPosRef.current!.y : pin.y;

      const sPt = imageToScreen({ x: px, y: py }, vp);
      const isSelected = selectedPin?.kind === pin.kind;

      const color =
        pin.kind === 'release' ? '#f97316' : pin.kind === 'bounce' ? '#ec4899' : '#ef4444';
      const letter = pin.kind === 'release' ? 'R' : pin.kind === 'bounce' ? 'B' : 'H';

      // Selection ring
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(sPt.x, sPt.y, 11, 0, Math.PI * 2);
        ctx.strokeStyle = '#facc15';
        ctx.lineWidth = 3;
        ctx.stroke();
      }

      // Pin circle
      ctx.beginPath();
      ctx.arc(sPt.x, sPt.y, 7, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Letter inside pin
      ctx.font = 'bold 9px system-ui, sans-serif';
      ctx.fillStyle = '#ffffff';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(letter, sPt.x, sPt.y);

      // Pin text label (frame & rounded coordinates)
      ctx.font = 'bold 11px system-ui, sans-serif';
      ctx.fillStyle = color;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(
        `${letter} [f:${pin.frame}, (${px.toFixed(1)}, ${py.toFixed(1)})]`,
        sPt.x + 12,
        sPt.y
      );
    });

    // 7. Loupe Magnifier (Offset up-right: cursor + (28, -28 - size), flipped when leaving canvas)
    const isLoupeActive = (loupeEnabled || altHeld) && isMouseOverRef.current && bitmap;
    if (isLoupeActive && bitmap) {
      const cursor = mousePosRef.current;
      const imgCursor = screenToImage(cursor, vp);

      if (
        imgCursor.x >= 0 &&
        imgCursor.x <= clip.width &&
        imgCursor.y >= 0 &&
        imgCursor.y <= clip.height
      ) {
        const loupeSize = 160;
        const zoomFactor = 8.0;
        const srcSize = loupeSize / zoomFactor; // 20 image px

        const sx = imgCursor.x - srcSize / 2;
        const sy = imgCursor.y - srcSize / 2;

        // Default position: offset up-right by (28, -28 - loupeSize)
        let dx = cursor.x + 28;
        let dy = cursor.y - 28 - loupeSize;

        // Flip to opposite side if it would leave the canvas
        if (dy < 8) {
          dy = cursor.y + 28; // flip below
        }
        if (dx + loupeSize > viewW - 8) {
          dx = cursor.x - 28 - loupeSize; // flip left
        }

        // Clamp to stay inside canvas view
        dx = Math.max(8, Math.min(viewW - loupeSize - 8, dx));
        dy = Math.max(8, Math.min(viewH - loupeSize - 8, dy));

        ctx.save();
        ctx.beginPath();
        ctx.rect(dx, dy, loupeSize, loupeSize);
        ctx.clip();

        ctx.fillStyle = '#0f172a';
        ctx.fillRect(dx, dy, loupeSize, loupeSize);

        // Nearest-neighbour magnification
        ctx.imageSmoothingEnabled = false;
        ctx.drawImage(bitmap, sx, sy, srcSize, srcSize, dx, dy, loupeSize, loupeSize);

        // Loupe border
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2;
        ctx.strokeRect(dx, dy, loupeSize, loupeSize);

        // Center crosshair
        const cx = dx + loupeSize / 2;
        const cy = dy + loupeSize / 2;
        ctx.beginPath();
        ctx.moveTo(cx, dy);
        ctx.lineTo(cx, dy + loupeSize);
        ctx.moveTo(dx, cy);
        ctx.lineTo(dx + loupeSize, cy);
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.9)';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.restore();
      }
    }

    ctx.restore();
  }, [
    clip,
    currentFrame,
    overlays,
    loupeEnabled,
    altHeld,
    prefill,
    annotatorState,
    label,
    selectedPin,
  ]);

  // Subscribe to frameCache updates to re-render when image is loaded
  useEffect(() => {
    const unsubscribe = frameCache.subscribe(() => {
      draw();
    });
    return unsubscribe;
  }, [draw]);

  // Redraw when dependencies change
  useEffect(() => {
    draw();
    updateStatusBar(isMouseOverRef.current ? mousePosRef.current : undefined);
  }, [draw, updateStatusBar]);

  // ResizeObserver for canvas content area
  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width <= 0 || height <= 0) continue;

        viewDimensionsRef.current = { w: width, h: height };
        const dpr = window.devicePixelRatio || 1;

        canvas.width = Math.round(width * dpr);
        canvas.height = Math.round(height * dpr);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        if (!hasManualAdjustmentRef.current && clip) {
          const fitted = fit(clip.width, clip.height, width, height);
          setViewport(fitted);
        }

        draw();
        updateStatusBar();
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, [clip, draw, setViewport, updateStatusBar]);

  // Re-fit view when clip changes
  useEffect(() => {
    hasManualAdjustmentRef.current = false;
    if (clip && viewDimensionsRef.current.w > 0 && viewDimensionsRef.current.h > 0) {
      const fitted = fit(
        clip.width,
        clip.height,
        viewDimensionsRef.current.w,
        viewDimensionsRef.current.h
      );
      setViewport(fitted);
    }
  }, [selectedClipId, clip, setViewport]);

  // Wheel zoom listener
  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;

    hasManualAdjustmentRef.current = true;

    const rect = canvas.getBoundingClientRect();
    const cursor: Point = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };

    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const nextVp = zoomAt(viewportRef.current, cursor, factor);
    setViewport(nextVp);
    updateStatusBar(cursor);
  };

  // Mouse pan & click & drag listeners
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !clip) return;

    const rect = canvas.getBoundingClientRect();
    const cursor: Point = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
    const imgPt = screenToImage(cursor, viewportRef.current);

    // Left button (0): Tool placement OR Pin Selection / Dragging
    if (e.button === 0) {
      if (armedTool) {
        // Impact requires an impact type first
        if (
          armedTool === 'impact' &&
          (!label?.impact || !label.impact.type || label.impact.type === 'none')
        ) {
          setImpactWarning('Choose impact type first (1-4)');
          return;
        }

        const clampedX = round1(Math.max(0, Math.min(clip.width, imgPt.x)));
        const clampedY = round1(Math.max(0, Math.min(clip.height, imgPt.y)));
        const ghostVis = computeGhostVisible(useAnnotatorStore.getState());

        apply((prev) =>
          placeEvent(prev, armedTool, currentFrame, clampedX, clampedY, { ghostVisible: ghostVis })
        );

        setArmedTool(null);
        setSelectedPin(null);
        setImpactWarning(null);
        return;
      }

      // Tool not armed: hit-test pins on current frame
      const pins = pinsForFrame(label, currentFrame, overlays.showAllEvents);
      const hit = hitTestPin(pins, imgPt.x, imgPt.y, viewportRef.current.scale, 12);

      if (hit) {
        setSelectedPin({ kind: hit.kind });
        isDraggingPinRef.current = true;
        dragCurrentImgPosRef.current = { x: hit.x, y: hit.y };
      } else {
        setSelectedPin(null);
      }
      return;
    }

    // Middle (1) or Right (2) button pans
    if (e.button === 1 || e.button === 2) {
      e.preventDefault();
      isPanningRef.current = true;
      panStartRef.current = {
        x: e.clientX,
        y: e.clientY,
        ox: viewportRef.current.offsetX,
        oy: viewportRef.current.offsetY,
      };
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !clip) return;

    const rect = canvas.getBoundingClientRect();
    const cursor: Point = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };

    mousePosRef.current = cursor;
    isMouseOverRef.current = true;

    // Pin dragging
    if (isDraggingPinRef.current && selectedPin) {
      const imgPt = screenToImage(cursor, viewportRef.current);
      const clampedX = round1(Math.max(0, Math.min(clip.width, imgPt.x)));
      const clampedY = round1(Math.max(0, Math.min(clip.height, imgPt.y)));
      dragCurrentImgPosRef.current = { x: clampedX, y: clampedY };
      draw();
      updateStatusBar(cursor);
      return;
    }

    // Pan handling
    if (isPanningRef.current) {
      hasManualAdjustmentRef.current = true;
      const dx = e.clientX - panStartRef.current.x;
      const dy = e.clientY - panStartRef.current.y;
      setViewport({
        ...viewportRef.current,
        offsetX: panStartRef.current.ox + dx,
        offsetY: panStartRef.current.oy + dy,
      });
    }

    // If loupe is active, redraw loupe position
    if (loupeEnabled || altHeld) {
      draw();
    }

    updateStatusBar(cursor);
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    // Left mouse up finishes pin drag
    if (e.button === 0 && isDraggingPinRef.current && selectedPin) {
      isDraggingPinRef.current = false;
      if (dragCurrentImgPosRef.current) {
        const { x: nx, y: ny } = dragCurrentImgPosRef.current;
        dragCurrentImgPosRef.current = null;
        const ghostVis = computeGhostVisible(useAnnotatorStore.getState());
        apply((prev) => placeEvent(prev, selectedPin.kind, currentFrame, nx, ny, { ghostVisible: ghostVis }));
      }
      return;
    }

    // Middle or Right mouse up finishes pan
    if (e.button === 1 || e.button === 2) {
      isPanningRef.current = false;
    }
  };

  const handleMouseEnter = () => {
    isMouseOverRef.current = true;
  };

  const handleMouseLeave = () => {
    isMouseOverRef.current = false;
    isPanningRef.current = false;
    if (isDraggingPinRef.current && selectedPin && dragCurrentImgPosRef.current) {
      isDraggingPinRef.current = false;
      const { x: nx, y: ny } = dragCurrentImgPosRef.current;
      dragCurrentImgPosRef.current = null;
      const ghostVis = computeGhostVisible(useAnnotatorStore.getState());
      apply((prev) => placeEvent(prev, selectedPin.kind, currentFrame, nx, ny, { ghostVisible: ghostVis }));
    }
    draw();
    updateStatusBar();
  };

  // Hotkeys F (fit) and G (100%)
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }
      if (e.key === 'f' || e.key === 'F') {
        e.preventDefault();
        handleFit();
      } else if (e.key === 'g' || e.key === 'G') {
        e.preventDefault();
        handleActualSize();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleFit, handleActualSize]);

  return (
    <div className="viewer-container">
      <div className="viewer-canvas-box" ref={containerRef}>
        <canvas
          ref={canvasRef}
          className={`viewer-canvas ${armedTool ? 'cursor-armed' : ''}`}
          onContextMenu={(e) => e.preventDefault()}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        />
        {impactWarning && (
          <div className="viewer-toast-warning">
            <span>⚠️ {impactWarning}</span>
            <button
              type="button"
              className="toast-close-btn"
              onClick={() => setImpactWarning(null)}
            >
              ✕
            </button>
          </div>
        )}
      </div>
      <div className="viewer-status-bar" ref={statusRef}>
        Frame {currentFrame} / {clip ? clip.frame_count - 1 : 0} &bull; t = 0.000 s &bull; cursor (—, —) &bull; zoom 100%
      </div>
    </div>
  );
};
