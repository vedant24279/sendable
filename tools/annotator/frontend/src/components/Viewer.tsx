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
import {
  systemPinsForFrame,
  hitTestSystemPin,
  type SystemPin,
} from '../lib/compare';
import { placeEvent, setCalibrationPoint, round1 } from '../lib/labelModel';
import {
  hitTestCalibPoint,
  nextMissingCalibPoint,
  formatPitchPos,
  CALIB_HANDLE_COLORS,
} from '../lib/calibUi';
import {
  fitHomography,
  pitchGridSegments,
  pixelToWorld,
  worldToPixel,
} from '../lib/calibration';
import { CALIB_POINT_NAMES, CalibrationPointName } from '../lib/calibConstants';

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
    calibrationMode,
    selectedCalibPoint,
    setSelectedCalibPoint,
    loupeMag,
    compareMode,
    compareData,
  } = annotatorState;

  const { label, apply } = useLabelStore();

  const clip = clips.find((c) => c.clip_id === selectedClipId);

  // Transient warning for impact without type
  const [impactWarning, setImpactWarning] = useState<string | null>(null);
  const [hoveredSysPin, setHoveredSysPin] = useState<{
    pin: SystemPin;
    screenX: number;
    screenY: number;
  } | null>(null);

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

  // Calibration handle drag refs
  const isDraggingCalibRef = useRef<boolean>(false);
  const draggedCalibNameRef = useRef<CalibrationPointName | null>(null);

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

      // Check for valid homography
      let calibH: number[][] | null = null;
      if (label?.calibration_gt?.points) {
        const pts = label.calibration_gt.points;
        if (pts.bat_L && pts.bat_R && pts.bowl_L && pts.bowl_R) {
          try {
            const fit = fitHomography(pts);
            calibH = fit.H;
          } catch {
            calibH = null;
          }
        }
      }

      let cursorStr = 'cursor (—, —)';
      let pitchStr = '';
      if (cursorScreen) {
        const imgPt = screenToImage(cursorScreen, vp);
        cursorStr = `cursor (${imgPt.x.toFixed(1)}, ${imgPt.y.toFixed(1)})`;
        if (calibH) {
          try {
            const [pxm, pzm] = pixelToWorld(calibH, imgPt.x, imgPt.y);
            pitchStr = formatPitchPos(pxm, pzm);
          } catch {
            pitchStr = '';
          }
        }
      }

      if (calibrationMode) {
        const activeHandle = selectedCalibPoint ? `[Handle: ${selectedCalibPoint}]` : '[Calibration Mode]';
        statusRef.current.textContent = `${activeHandle}   ${pitchStr ? `${pitchStr}   ` : ''}${cursorStr}   zoom ${zoomPct}%`;
      } else if (compareMode) {
        statusRef.current.textContent = `[COMPARE READ-ONLY]   Frame ${currentFrame} / ${clip.frame_count - 1}   t = ${t} s   ${pitchStr ? `${pitchStr}   ` : ''}${cursorStr}   zoom ${zoomPct}%`;
      } else {
        const extraPitch = pitchStr ? `${pitchStr}   ` : '';
        statusRef.current.textContent = `Frame ${currentFrame} / ${clip.frame_count - 1}   t = ${t} s   ${extraPitch}${cursorStr}   zoom ${zoomPct}%`;
      }
    },
    [clip, currentFrame, armedTool, label, calibrationMode, selectedCalibPoint, compareMode]
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

    // 3. Calibration Overlay (in standard mode)
    if (!calibrationMode && overlays.calibration) {
      const calibMap = new Map<string, Point>();
      if (label?.calibration_gt?.points) {
        const pts = label.calibration_gt.points;
        for (const [name, coords] of Object.entries(pts)) {
          if (coords && coords.length === 2) {
            calibMap.set(name, { x: coords[0], y: coords[1] });
          }
        }
      } else if (prefill?.calibration) {
        prefill.calibration.forEach((pt) => calibMap.set(pt.name, { x: pt.x, y: pt.y }));
      }

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

    // 6b. Compare Mode System Trajectory (small hollow circles) & System Diamond Pins ("sys R", "sys B", "sys D")
    if (compareMode && compareData?.found) {
      const sysTraj = compareData.trajectory || [];
      if (sysTraj.length > 0) {
        sysTraj.forEach((pt) => {
          const sPt = imageToScreen(pt, vp);
          const isCurrent = pt.frame === currentFrame;
          ctx.save();
          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, isCurrent ? 5 : 3, 0, Math.PI * 2);
          ctx.strokeStyle = isCurrent ? '#facc15' : 'rgba(56, 189, 248, 0.85)';
          ctx.lineWidth = isCurrent ? 2 : 1.3;
          ctx.stroke();
          ctx.restore();
        });
      }

      const sysPins = systemPinsForFrame(compareData.events, currentFrame);
      sysPins.forEach((sPin) => {
        const sPt = imageToScreen({ x: sPin.x, y: sPin.y }, vp);
        const radius = sPin.exact ? 8 : 6.5;

        ctx.save();
        ctx.globalAlpha = sPin.exact ? 1.0 : 0.42;

        // Hollow diamond shape
        ctx.beginPath();
        ctx.moveTo(sPt.x, sPt.y - radius);
        ctx.lineTo(sPt.x + radius, sPt.y);
        ctx.lineTo(sPt.x, sPt.y + radius);
        ctx.lineTo(sPt.x - radius, sPt.y);
        ctx.closePath();

        ctx.strokeStyle = sPin.color;
        ctx.lineWidth = sPin.exact ? 2.2 : 1.4;
        if (!sPin.exact) {
          ctx.setLineDash([3, 2]);
        }
        ctx.stroke();
        ctx.setLineDash([]);

        // Label text ("sys R", "sys B", "sys D")
        ctx.font = sPin.exact ? 'bold 11px system-ui, sans-serif' : '600 10px system-ui, sans-serif';
        ctx.fillStyle = sPin.color;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        const suffix = sPin.exact ? '' : ` (${sPin.frameOffset > 0 ? `+${sPin.frameOffset}` : sPin.frameOffset}f)`;
        ctx.fillText(`${sPin.shortLabel}${suffix}`, sPt.x + radius + 5, sPt.y - 10);

        ctx.restore();
      });
    }

    // 7. Calibration Mode Overlays (Pitch rectangle, 1m grid, predicted stumps, 6 handles)
    if (calibrationMode) {
      const calibGT = label?.calibration_gt;
      const points = (calibGT?.points || {}) as Record<string, [number, number]>;

      // Check if 4 corner points exist to fit H
      const hasCorners = points.bat_L && points.bat_R && points.bowl_L && points.bowl_R;
      if (hasCorners) {
        try {
          const fit = fitHomography(points as Record<CalibrationPointName, [number, number]>);

          // A. Draw 1m pitch grid lines (thin, semi-transparent)
          const segments = pitchGridSegments(fit.H, 1.0);
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.22)';
          ctx.lineWidth = 1;
          for (const [p1, p2] of segments) {
            const s1 = imageToScreen({ x: p1[0], y: p1[1] }, vp);
            const s2 = imageToScreen({ x: p2[0], y: p2[1] }, vp);
            ctx.beginPath();
            ctx.moveTo(s1.x, s1.y);
            ctx.lineTo(s2.x, s2.y);
            ctx.stroke();
          }

          // B. Draw pitch rectangle outline
          const sBowlL = imageToScreen({ x: points.bowl_L[0], y: points.bowl_L[1] }, vp);
          const sBowlR = imageToScreen({ x: points.bowl_R[0], y: points.bowl_R[1] }, vp);
          const sBatR = imageToScreen({ x: points.bat_R[0], y: points.bat_R[1] }, vp);
          const sBatL = imageToScreen({ x: points.bat_L[0], y: points.bat_L[1] }, vp);

          ctx.beginPath();
          ctx.moveTo(sBowlL.x, sBowlL.y);
          ctx.lineTo(sBowlR.x, sBowlR.y);
          ctx.lineTo(sBatR.x, sBatR.y);
          ctx.lineTo(sBatL.x, sBatL.y);
          ctx.closePath();

          ctx.strokeStyle = 'rgba(56, 189, 248, 0.85)';
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.fillStyle = 'rgba(56, 189, 248, 0.08)';
          ctx.fill();

          // C. Draw the two stump positions PREDICTED by the homography as hollow circles
          // bat_stump predicted at world (0.0, 0.0)
          const predBat = worldToPixel(fit.H, 0.0, 0.0, fit.H_inv);
          const sPredBat = imageToScreen({ x: predBat[0], y: predBat[1] }, vp);
          ctx.beginPath();
          ctx.arc(sPredBat.x, sPredBat.y, 8, 0, Math.PI * 2);
          ctx.strokeStyle = '#f59e0b';
          ctx.lineWidth = 2;
          ctx.setLineDash([4, 3]);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.font = 'bold 10px system-ui, sans-serif';
          ctx.fillStyle = '#f59e0b';
          ctx.textAlign = 'left';
          ctx.fillText('pred bat stump', sPredBat.x + 10, sPredBat.y + 3);

          // bowl_stump predicted at world (0.0, 20.12)
          const predBowl = worldToPixel(fit.H, 0.0, 20.12, fit.H_inv);
          const sPredBowl = imageToScreen({ x: predBowl[0], y: predBowl[1] }, vp);
          ctx.beginPath();
          ctx.arc(sPredBowl.x, sPredBowl.y, 8, 0, Math.PI * 2);
          ctx.strokeStyle = '#a855f7';
          ctx.lineWidth = 2;
          ctx.setLineDash([4, 3]);
          ctx.stroke();
          ctx.setLineDash([]);
          ctx.font = 'bold 10px system-ui, sans-serif';
          ctx.fillStyle = '#a855f7';
          ctx.textAlign = 'left';
          ctx.fillText('pred bowl stump', sPredBowl.x + 10, sPredBowl.y + 3);
        } catch {
          // Degenerate homography, skip grid
        }
      }

      // D. Draw the 6 calibration point handles
      for (const name of CALIB_POINT_NAMES) {
        let pt = points[name];
        if (
          isDraggingCalibRef.current &&
          draggedCalibNameRef.current === name &&
          dragCurrentImgPosRef.current
        ) {
          pt = [dragCurrentImgPosRef.current.x, dragCurrentImgPosRef.current.y];
        }

        if (pt) {
          const sPt = imageToScreen({ x: pt[0], y: pt[1] }, vp);
          const isSelected = selectedCalibPoint === name;
          const color = CALIB_HANDLE_COLORS[name];

          // Selected outer ring
          if (isSelected) {
            ctx.beginPath();
            ctx.arc(sPt.x, sPt.y, 11, 0, Math.PI * 2);
            ctx.strokeStyle = '#ffffff';
            ctx.lineWidth = 2.5;
            ctx.stroke();
          }

          // Handle solid circle
          ctx.beginPath();
          ctx.arc(sPt.x, sPt.y, 6, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.strokeStyle = '#000000';
          ctx.lineWidth = 1.5;
          ctx.stroke();

          // Text badge
          ctx.font = 'bold 11px system-ui, sans-serif';
          const badgeText = `${name} (${pt[0].toFixed(1)}, ${pt[1].toFixed(1)})`;
          const textW = ctx.measureText(badgeText).width;
          ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
          ctx.fillRect(sPt.x + 9, sPt.y - 9, textW + 8, 18);
          ctx.fillStyle = color;
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillText(badgeText, sPt.x + 13, sPt.y);
        }
      }
    }

    // 8. Loupe Magnifier (Offset up-right: cursor + (28, -28 - size), flipped when leaving canvas)
    const isLoupeActive =
      (calibrationMode ? loupeEnabled : (loupeEnabled || altHeld)) &&
      isMouseOverRef.current &&
      bitmap;
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
        const zoomFactor = calibrationMode ? (loupeMag || 8.0) : 8.0;
        const srcSize = loupeSize / zoomFactor; // source image pixels

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
        ctx.strokeStyle = calibrationMode ? '#a855f7' : '#38bdf8';
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
    calibrationMode,
    selectedCalibPoint,
    loupeMag,
    compareMode,
    compareData,
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

    // Left button (0): Disabled in Compare read-only mode; otherwise Tool placement / Calibration / Pin Drag
    if (e.button === 0) {
      if (compareMode) {
        return;
      }
      if (calibrationMode) {
        const calibGT = label?.calibration_gt;
        const points = (calibGT?.points || {}) as Record<string, [number, number]>;
        const hit = hitTestCalibPoint(points, imgPt.x, imgPt.y, viewportRef.current.scale, 14);

        if (hit) {
          setSelectedCalibPoint(hit);
          isDraggingCalibRef.current = true;
          draggedCalibNameRef.current = hit;
          dragCurrentImgPosRef.current = { x: points[hit][0], y: points[hit][1] };
          draw();
          return;
        }

        // Clicked on empty space: place selected point or next missing point
        const clampedX = round1(Math.max(0, Math.min(clip.width, imgPt.x)));
        const clampedY = round1(Math.max(0, Math.min(clip.height, imgPt.y)));
        const targetName =
          selectedCalibPoint && !points[selectedCalibPoint]
            ? selectedCalibPoint
            : nextMissingCalibPoint(points, selectedCalibPoint) || selectedCalibPoint || 'bat_L';

        const ghostVis = computeGhostVisible(useAnnotatorStore.getState());
        apply((prev) =>
          setCalibrationPoint(prev, targetName, clampedX, clampedY, prefill?.calibration, {
            ghostVisible: ghostVis,
          })
        );

        // Advance to next missing point
        const simulated = { ...points, [targetName]: [clampedX, clampedY] };
        const nextMissing = nextMissingCalibPoint(simulated, targetName);
        if (nextMissing) {
          setSelectedCalibPoint(nextMissing);
        }
        return;
      }

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

    // Calibration handle dragging
    if (isDraggingCalibRef.current && draggedCalibNameRef.current) {
      const imgPt = screenToImage(cursor, viewportRef.current);
      const clampedX = round1(Math.max(0, Math.min(clip.width, imgPt.x)));
      const clampedY = round1(Math.max(0, Math.min(clip.height, imgPt.y)));
      dragCurrentImgPosRef.current = { x: clampedX, y: clampedY };
      draw();
      updateStatusBar(cursor);
      return;
    }

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

    // Check system pin hover tooltip in compare mode
    if (compareMode && compareData?.found) {
      const imgPt = screenToImage(cursor, viewportRef.current);
      const visibleSysPins = systemPinsForFrame(compareData.events, currentFrame);
      const hitSys = hitTestSystemPin(
        visibleSysPins,
        imgPt.x,
        imgPt.y,
        viewportRef.current.scale,
        14
      );
      if (hitSys) {
        const screenPinPt = imageToScreen({ x: hitSys.x, y: hitSys.y }, viewportRef.current);
        setHoveredSysPin({ pin: hitSys, screenX: screenPinPt.x, screenY: screenPinPt.y });
      } else if (hoveredSysPin) {
        setHoveredSysPin(null);
      }
    } else if (hoveredSysPin) {
      setHoveredSysPin(null);
    }

    // If loupe is active, redraw loupe position
    if (loupeEnabled || altHeld) {
      draw();
    }

    updateStatusBar(cursor);
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    // Left mouse up finishes calibration handle drag
    if (e.button === 0 && isDraggingCalibRef.current && draggedCalibNameRef.current) {
      isDraggingCalibRef.current = false;
      const target = draggedCalibNameRef.current;
      draggedCalibNameRef.current = null;
      if (dragCurrentImgPosRef.current) {
        const { x: nx, y: ny } = dragCurrentImgPosRef.current;
        dragCurrentImgPosRef.current = null;
        const ghostVis = computeGhostVisible(useAnnotatorStore.getState());
        apply((prev) =>
          setCalibrationPoint(prev, target, nx, ny, prefill?.calibration, {
            ghostVisible: ghostVis,
          })
        );
      }
      return;
    }

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
    if (hoveredSysPin) {
      setHoveredSysPin(null);
    }
    if (isDraggingCalibRef.current && draggedCalibNameRef.current && dragCurrentImgPosRef.current) {
      isDraggingCalibRef.current = false;
      const target = draggedCalibNameRef.current;
      draggedCalibNameRef.current = null;
      const { x: nx, y: ny } = dragCurrentImgPosRef.current;
      dragCurrentImgPosRef.current = null;
      const ghostVis = computeGhostVisible(useAnnotatorStore.getState());
      apply((prev) =>
        setCalibrationPoint(prev, target, nx, ny, prefill?.calibration, {
          ghostVisible: ghostVis,
        })
      );
    }
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
          className={`viewer-canvas ${calibrationMode ? 'cursor-calib' : armedTool ? 'cursor-armed' : ''}`}
          title={hoveredSysPin ? hoveredSysPin.pin.tooltip : undefined}
          onContextMenu={(e) => e.preventDefault()}
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        />
        {compareMode && hoveredSysPin && (
          <div
            className="compare-pin-tooltip"
            style={{
              left: `${hoveredSysPin.screenX + 12}px`,
              top: `${Math.max(8, hoveredSysPin.screenY - 28)}px`,
            }}
          >
            {hoveredSysPin.pin.tooltip}
          </div>
        )}
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
