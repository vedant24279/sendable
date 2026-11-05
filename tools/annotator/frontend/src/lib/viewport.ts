/**
 * Pure functions for view transform {scale, offsetX, offsetY} over original image pixels.
 */

export interface Point {
  x: number;
  y: number;
}

export interface Viewport {
  scale: number;
  offsetX: number;
  offsetY: number;
}

export const MIN_SCALE = 0.1;
export const MAX_SCALE = 16.0;

export function clampScale(scale: number): number {
  return Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale));
}

/**
 * Maps screen coordinates (CSS pixels relative to canvas) to original image pixels.
 */
export function screenToImage(screen: Point, vp: Viewport): Point {
  return {
    x: (screen.x - vp.offsetX) / vp.scale,
    y: (screen.y - vp.offsetY) / vp.scale,
  };
}

/**
 * Maps original image coordinates to screen coordinates (CSS pixels).
 */
export function imageToScreen(image: Point, vp: Viewport): Point {
  return {
    x: image.x * vp.scale + vp.offsetX,
    y: image.y * vp.scale + vp.offsetY,
  };
}

/**
 * Zooms the viewport by factor around cursor screen point, keeping the image pixel under cursor fixed.
 */
export function zoomAt(vp: Viewport, cursor: Point, factor: number): Viewport {
  const newScale = clampScale(vp.scale * factor);
  if (newScale === vp.scale) {
    return vp;
  }
  const imagePt = screenToImage(cursor, vp);
  return {
    scale: newScale,
    offsetX: cursor.x - imagePt.x * newScale,
    offsetY: cursor.y - imagePt.y * newScale,
  };
}

/**
 * Fits the image of dimensions (imgW, imgH) into the viewport of dimensions (viewW, viewH)
 * with the image centered and scale clamped to [0.1, 16].
 */
export function fit(imgW: number, imgH: number, viewW: number, viewH: number): Viewport {
  if (imgW <= 0 || imgH <= 0 || viewW <= 0 || viewH <= 0) {
    return { scale: 1, offsetX: 0, offsetY: 0 };
  }
  const scale = clampScale(Math.min(viewW / imgW, viewH / imgH));
  const offsetX = (viewW - imgW * scale) / 2;
  const offsetY = (viewH - imgH * scale) / 2;
  return { scale, offsetX, offsetY };
}

/**
 * Helper to convert frame number to elapsed seconds based on fps.
 */
export function frameToTime(frame: number, fps: number): number {
  if (fps <= 0) return 0;
  return frame / fps;
}
