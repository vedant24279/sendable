/**
 * Pure functions for event pin extraction and hit-testing on the viewer canvas.
 */

import { Label } from './labelModel';

export type PinKind = 'release' | 'bounce' | 'impact';

export interface Pin {
  kind: PinKind;
  frame: number;
  x: number;
  y: number;
}

/**
 * Returns the pins present in the label for the specified frame.
 * If showAll is true, returns all non-null pins across the clip.
 */
export function pinsForFrame(
  label: Label | null,
  frame: number,
  showAll = false
): Pin[] {
  if (!label) return [];

  const result: Pin[] = [];

  if (label.release && (showAll || label.release.frame === frame)) {
    result.push({
      kind: 'release',
      frame: label.release.frame,
      x: label.release.x,
      y: label.release.y,
    });
  }

  if (label.bounce && (showAll || label.bounce.frame === frame)) {
    result.push({
      kind: 'bounce',
      frame: label.bounce.frame,
      x: label.bounce.x,
      y: label.bounce.y,
    });
  }

  if (
    label.impact &&
    label.impact.frame != null &&
    label.impact.x != null &&
    label.impact.y != null &&
    (showAll || label.impact.frame === frame)
  ) {
    result.push({
      kind: 'impact',
      frame: label.impact.frame,
      x: label.impact.x,
      y: label.impact.y,
    });
  }

  return result;
}

/**
 * Hit tests a list of pins against an image position (imgX, imgY).
 * Converts distance to screen pixels using viewport scale and returns the nearest pin within radiusScreenPx.
 */
export function hitTestPin(
  pins: Pin[],
  imgX: number,
  imgY: number,
  scale: number,
  radiusScreenPx = 10
): Pin | null {
  if (!pins || pins.length === 0 || scale <= 0) return null;

  let nearestPin: Pin | null = null;
  let minDistanceScreen = Infinity;

  for (const pin of pins) {
    const dxScreen = (pin.x - imgX) * scale;
    const dyScreen = (pin.y - imgY) * scale;
    const distScreen = Math.hypot(dxScreen, dyScreen);

    if (distScreen <= radiusScreenPx && distScreen < minDistanceScreen) {
      minDistanceScreen = distScreen;
      nearestPin = pin;
    }
  }

  return nearestPin;
}
