/**
 * Hotkey mapping and action resolution for the annotator interface.
 */

import { ImpactType } from './labelModel';

export type ToolKind = 'release' | 'bounce' | 'impact';

export type Action =
  | { type: 'armTool'; tool: ToolKind }
  | { type: 'setLastVisible' }
  | { type: 'setImpactType'; impactType: ImpactType }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'saveDraft' }
  | { type: 'finalize' }
  | { type: 'disarm' }
  | { type: 'nudge'; dx: number; dy: number }
  | { type: 'toggleCalibrationMode' };

export interface KeyContext {
  key: string;
  code?: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  targetTag?: string;
}

/**
 * Translates a keyboard event into an annotation Action, or null if unhandled.
 * Ignores all shortcuts when typing inside INPUT, TEXTAREA, or SELECT elements.
 */
export function keyToAction(ev: KeyContext): Action | null {
  // 1. Ignore if typing in text inputs or selects
  if (ev.targetTag) {
    const tag = ev.targetTag.toUpperCase();
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
      return null;
    }
  }

  const ctrl = Boolean(ev.ctrlKey);
  const shift = Boolean(ev.shiftKey);
  const alt = Boolean(ev.altKey);
  const key = ev.key;

  // 2. Ctrl+S -> saveDraft
  if (ctrl && (key === 's' || key === 'S')) {
    return { type: 'saveDraft' };
  }

  // 3. Ctrl+Enter -> finalize
  if (ctrl && key === 'Enter') {
    return { type: 'finalize' };
  }

  // 4. Escape -> disarm
  if (key === 'Escape') {
    return { type: 'disarm' };
  }

  // 5. Redo: Ctrl+Shift+Z, Y, Ctrl+Y
  if (ctrl && shift && (key === 'z' || key === 'Z')) {
    return { type: 'redo' };
  }
  if (!alt && (key === 'y' || key === 'Y')) {
    return { type: 'redo' };
  }

  // 6. Undo: Z or Ctrl+Z (without shift)
  if (!shift && !alt && (key === 'z' || key === 'Z')) {
    return { type: 'undo' };
  }

  // 7. Nudge: Ctrl+Arrow = 1px, Ctrl+Shift+Arrow = 0.1px
  if (ctrl && (key === 'ArrowLeft' || key === 'ArrowRight' || key === 'ArrowUp' || key === 'ArrowDown')) {
    const step = shift ? 0.1 : 1.0;
    if (key === 'ArrowLeft') return { type: 'nudge', dx: -step, dy: 0 };
    if (key === 'ArrowRight') return { type: 'nudge', dx: step, dy: 0 };
    if (key === 'ArrowUp') return { type: 'nudge', dx: 0, dy: -step };
    if (key === 'ArrowDown') return { type: 'nudge', dx: 0, dy: step };
  }

  // 8. Tool Arming: R (release), B (bounce), H (impact) - without Ctrl/Alt
  if (!ctrl && !alt) {
    if (key === 'c' || key === 'C') return { type: 'toggleCalibrationMode' };
    if (key === 'r' || key === 'R') return { type: 'armTool', tool: 'release' };
    if (key === 'b' || key === 'B') return { type: 'armTool', tool: 'bounce' };
    if (key === 'h' || key === 'H') return { type: 'armTool', tool: 'impact' };

    // 9. E -> setLastVisible on current frame
    if (key === 'e' || key === 'E') return { type: 'setLastVisible' };

    // 10. Impact type selection on digits 1-4
    if (key === '1') return { type: 'setImpactType', impactType: 'bat' };
    if (key === '2') return { type: 'setImpactType', impactType: 'pad' };
    if (key === '3') return { type: 'setImpactType', impactType: 'stumps' };
    if (key === '4') return { type: 'setImpactType', impactType: 'none' };
  }

  // All other keys (Arrows without Ctrl, Home, End, Space, F, G, L, [, ]) keep their normal behavior
  return null;
}
