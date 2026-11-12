import { describe, it, expect } from 'vitest';
import { keyToAction } from './hotkeys';

describe('keyToAction', () => {
  it('ignores everything when typing in INPUT, TEXTAREA, or SELECT', () => {
    expect(keyToAction({ key: 'r', targetTag: 'INPUT' })).toBeNull();
    expect(keyToAction({ key: 'b', targetTag: 'textarea' })).toBeNull();
    expect(keyToAction({ key: '1', targetTag: 'SELECT' })).toBeNull();
    expect(keyToAction({ key: 's', ctrlKey: true, targetTag: 'input' })).toBeNull();
    expect(keyToAction({ key: 'c', targetTag: 'INPUT' })).toBeNull();
    expect(keyToAction({ key: 'C', targetTag: 'TEXTAREA' })).toBeNull();
    expect(keyToAction({ key: 'o', targetTag: 'INPUT' })).toBeNull();
    expect(keyToAction({ key: 'O', targetTag: 'TEXTAREA' })).toBeNull();
  });

  it('maps O to openFilePicker', () => {
    expect(keyToAction({ key: 'o' })).toEqual({ type: 'openFilePicker' });
    expect(keyToAction({ key: 'O' })).toEqual({ type: 'openFilePicker' });
    expect(keyToAction({ key: 'o', ctrlKey: true })).toBeNull();
    expect(keyToAction({ key: 'o', altKey: true })).toBeNull();
  });

  it('maps C to toggleCalibrationMode', () => {
    expect(keyToAction({ key: 'c' })).toEqual({ type: 'toggleCalibrationMode' });
    expect(keyToAction({ key: 'C' })).toEqual({ type: 'toggleCalibrationMode' });
    expect(keyToAction({ key: 'c', ctrlKey: true })).toBeNull();
    expect(keyToAction({ key: 'c', altKey: true })).toBeNull();
  });

  it('maps tool arming keys R, B, H', () => {
    expect(keyToAction({ key: 'r' })).toEqual({ type: 'armTool', tool: 'release' });
    expect(keyToAction({ key: 'R' })).toEqual({ type: 'armTool', tool: 'release' });
    expect(keyToAction({ key: 'b' })).toEqual({ type: 'armTool', tool: 'bounce' });
    expect(keyToAction({ key: 'B' })).toEqual({ type: 'armTool', tool: 'bounce' });
    expect(keyToAction({ key: 'h' })).toEqual({ type: 'armTool', tool: 'impact' });
    expect(keyToAction({ key: 'H' })).toEqual({ type: 'armTool', tool: 'impact' });
  });

  it('maps E to setLastVisible', () => {
    expect(keyToAction({ key: 'e' })).toEqual({ type: 'setLastVisible' });
    expect(keyToAction({ key: 'E' })).toEqual({ type: 'setLastVisible' });
  });

  it('maps digits 1-4 to impact types', () => {
    expect(keyToAction({ key: '1' })).toEqual({ type: 'setImpactType', impactType: 'bat' });
    expect(keyToAction({ key: '2' })).toEqual({ type: 'setImpactType', impactType: 'pad' });
    expect(keyToAction({ key: '3' })).toEqual({ type: 'setImpactType', impactType: 'stumps' });
    expect(keyToAction({ key: '4' })).toEqual({ type: 'setImpactType', impactType: 'none' });
  });

  it('maps undo to Z or Ctrl+Z', () => {
    expect(keyToAction({ key: 'z' })).toEqual({ type: 'undo' });
    expect(keyToAction({ key: 'Z' })).toEqual({ type: 'undo' });
    expect(keyToAction({ key: 'z', ctrlKey: true })).toEqual({ type: 'undo' });
  });

  it('maps redo to Y, Ctrl+Y, or Ctrl+Shift+Z', () => {
    expect(keyToAction({ key: 'y' })).toEqual({ type: 'redo' });
    expect(keyToAction({ key: 'Y', ctrlKey: true })).toEqual({ type: 'redo' });
    expect(keyToAction({ key: 'z', ctrlKey: true, shiftKey: true })).toEqual({ type: 'redo' });
    expect(keyToAction({ key: 'Z', ctrlKey: true, shiftKey: true })).toEqual({ type: 'redo' });
  });

  it('maps Ctrl+S to saveDraft and Ctrl+Enter to finalize', () => {
    expect(keyToAction({ key: 's', ctrlKey: true })).toEqual({ type: 'saveDraft' });
    expect(keyToAction({ key: 'S', ctrlKey: true })).toEqual({ type: 'saveDraft' });
    expect(keyToAction({ key: 'Enter', ctrlKey: true })).toEqual({ type: 'finalize' });
  });

  it('maps Escape to disarm', () => {
    expect(keyToAction({ key: 'Escape' })).toEqual({ type: 'disarm' });
  });

  it('maps Ctrl+Arrow to 1px nudge and Ctrl+Shift+Arrow to 0.1px nudge', () => {
    expect(keyToAction({ key: 'ArrowLeft', ctrlKey: true })).toEqual({ type: 'nudge', dx: -1.0, dy: 0 });
    expect(keyToAction({ key: 'ArrowRight', ctrlKey: true })).toEqual({ type: 'nudge', dx: 1.0, dy: 0 });
    expect(keyToAction({ key: 'ArrowUp', ctrlKey: true })).toEqual({ type: 'nudge', dx: 0, dy: -1.0 });
    expect(keyToAction({ key: 'ArrowDown', ctrlKey: true })).toEqual({ type: 'nudge', dx: 0, dy: 1.0 });

    expect(keyToAction({ key: 'ArrowLeft', ctrlKey: true, shiftKey: true })).toEqual({
      type: 'nudge',
      dx: -0.1,
      dy: 0,
    });
    expect(keyToAction({ key: 'ArrowRight', ctrlKey: true, shiftKey: true })).toEqual({
      type: 'nudge',
      dx: 0.1,
      dy: 0,
    });
    expect(keyToAction({ key: 'ArrowUp', ctrlKey: true, shiftKey: true })).toEqual({
      type: 'nudge',
      dx: 0,
      dy: -0.1,
    });
    expect(keyToAction({ key: 'ArrowDown', ctrlKey: true, shiftKey: true })).toEqual({
      type: 'nudge',
      dx: 0,
      dy: 0.1,
    });
  });

  it('leaves plain navigation keys unhandled so normal listeners take them', () => {
    expect(keyToAction({ key: 'ArrowLeft' })).toBeNull();
    expect(keyToAction({ key: 'ArrowRight' })).toBeNull();
    expect(keyToAction({ key: 'Home' })).toBeNull();
    expect(keyToAction({ key: 'End' })).toBeNull();
    expect(keyToAction({ key: ' ' })).toBeNull();
    expect(keyToAction({ key: 'f' })).toBeNull();
    expect(keyToAction({ key: 'g' })).toBeNull();
    expect(keyToAction({ key: 'l' })).toBeNull();
    expect(keyToAction({ key: '[' })).toBeNull();
    expect(keyToAction({ key: ']' })).toBeNull();
  });
});
