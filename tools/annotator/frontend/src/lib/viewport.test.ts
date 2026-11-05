import { describe, it, expect } from 'vitest';
import {
  screenToImage,
  imageToScreen,
  zoomAt,
  fit,
  frameToTime,
  clampScale,
  Viewport,
  Point,
} from './viewport';

describe('viewport math', () => {
  it('round trips screenToImage and imageToScreen', () => {
    const vp: Viewport = { scale: 2.5, offsetX: 120, offsetY: -45 };
    const originalImagePt: Point = { x: 500.5, y: 320.2 };

    const screenPt = imageToScreen(originalImagePt, vp);
    const recoveredImagePt = screenToImage(screenPt, vp);

    expect(recoveredImagePt.x).toBeCloseTo(originalImagePt.x, 6);
    expect(recoveredImagePt.y).toBeCloseTo(originalImagePt.y, 6);
  });

  it('zoomAt keeps the image pixel under cursor fixed', () => {
    const vp: Viewport = { scale: 1.0, offsetX: 50, offsetY: 70 };
    const cursor: Point = { x: 400, y: 300 };

    // Image point under cursor before zoom
    const imgPtBefore = screenToImage(cursor, vp);

    // Zoom in by factor 1.5
    const zoomedVp = zoomAt(vp, cursor, 1.5);

    // Screen point of the same image pixel after zoom
    const screenPtAfter = imageToScreen(imgPtBefore, zoomedVp);

    expect(screenPtAfter.x).toBeCloseTo(cursor.x, 5);
    expect(screenPtAfter.y).toBeCloseTo(cursor.y, 5);
  });

  it('fit centres the image inside the view', () => {
    const imgW = 1920;
    const imgH = 1080;
    const viewW = 960;
    const viewH = 540;

    const vp = fit(imgW, imgH, viewW, viewH);

    // Expected scale is 0.5
    expect(vp.scale).toBeCloseTo(0.5, 4);

    // Centre of image
    const imgCentre: Point = { x: imgW / 2, y: imgH / 2 };
    const screenCentre = imageToScreen(imgCentre, vp);

    expect(screenCentre.x).toBeCloseTo(viewW / 2, 4);
    expect(screenCentre.y).toBeCloseTo(viewH / 2, 4);
  });

  it('fits 1920x1080 image into 1354x732 view: scale 0.6778 (+-0.001), fully inside view, offsetX ~26.5, offsetY 0', () => {
    const imgW = 1920;
    const imgH = 1080;
    const viewW = 1354;
    const viewH = 732;

    const vp = fit(imgW, imgH, viewW, viewH);

    // scale 0.6778 (+-0.001)
    expect(vp.scale).toBeGreaterThanOrEqual(0.6778 - 0.001);
    expect(vp.scale).toBeLessThanOrEqual(0.6778 + 0.001);

    // offsetX ~26.5, offsetY 0
    expect(vp.offsetX).toBeCloseTo(26.33, 1);
    expect(vp.offsetY).toBe(0);

    // image fully inside the view
    const topLeft = imageToScreen({ x: 0, y: 0 }, vp);
    const bottomRight = imageToScreen({ x: imgW, y: imgH }, vp);

    expect(topLeft.x).toBeGreaterThanOrEqual(0);
    expect(topLeft.y).toBeGreaterThanOrEqual(0);
    expect(bottomRight.x).toBeLessThanOrEqual(viewW);
    expect(bottomRight.y).toBeLessThanOrEqual(viewH);
  });

  it('fits 1920x1080 image into 2000x500 view (height-limited)', () => {
    const imgW = 1920;
    const imgH = 1080;
    const viewW = 2000;
    const viewH = 500;

    const vp = fit(imgW, imgH, viewW, viewH);

    // Height-limited: scale = 500 / 1080
    expect(vp.scale).toBeCloseTo(500 / 1080, 4);
    expect(vp.offsetY).toBe(0);
    expect(vp.offsetX).toBeGreaterThan(0);

    // Rendered height equals view height
    const renderedH = imgH * vp.scale;
    expect(renderedH).toBeCloseTo(viewH, 4);
    const renderedW = imgW * vp.scale;
    expect(renderedW).toBeLessThan(viewW);
  });

  it('clamps scale between 0.1 and 16', () => {
    expect(clampScale(0.01)).toBe(0.1);
    expect(clampScale(0.1)).toBe(0.1);
    expect(clampScale(5.0)).toBe(5.0);
    expect(clampScale(16.0)).toBe(16.0);
    expect(clampScale(25.0)).toBe(16.0);

    const vp: Viewport = { scale: 15.0, offsetX: 0, offsetY: 0 };
    const zoomed = zoomAt(vp, { x: 100, y: 100 }, 2.0);
    expect(zoomed.scale).toBe(16.0);

    const zoomedOut = zoomAt({ scale: 0.15, offsetX: 0, offsetY: 0 }, { x: 100, y: 100 }, 0.5);
    expect(zoomedOut.scale).toBe(0.1);
  });

  it('at zoom 8 screen position of image point (936, 426) maps back with screenToImage to within 0.01 px', () => {
    const vp: Viewport = { scale: 8.0, offsetX: -2500, offsetY: -1200 };
    const originalPt: Point = { x: 936, y: 426 };

    const screenPt = imageToScreen(originalPt, vp);
    const recoveredPt = screenToImage(screenPt, vp);

    expect(Math.abs(recoveredPt.x - originalPt.x)).toBeLessThan(0.01);
    expect(Math.abs(recoveredPt.y - originalPt.y)).toBeLessThan(0.01);
  });

  it('frameToTime returns correct seconds from frame / fps', () => {
    expect(frameToTime(0, 30.0)).toBe(0.0);
    expect(frameToTime(15, 30.0)).toBeCloseTo(0.5, 5);
    expect(frameToTime(92, 30.0)).toBeCloseTo(3.066667, 5);
    expect(frameToTime(10, 0)).toBe(0);
  });
});
