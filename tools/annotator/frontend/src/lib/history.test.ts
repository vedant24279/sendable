import { describe, it, expect } from 'vitest';
import { HistoryStack } from './history';

describe('HistoryStack', () => {
  it('handles basic push, undo, and redo sequence', () => {
    const history = new HistoryStack<string>('state_0');
    expect(history.current).toBe('state_0');
    expect(history.canUndo).toBe(false);
    expect(history.canRedo).toBe(false);

    history.push('state_1');
    expect(history.current).toBe('state_1');
    expect(history.canUndo).toBe(true);
    expect(history.canRedo).toBe(false);

    history.push('state_2');
    expect(history.current).toBe('state_2');

    // Undo to state_1
    const s1 = history.undo();
    expect(s1).toBe('state_1');
    expect(history.current).toBe('state_1');
    expect(history.canUndo).toBe(true);
    expect(history.canRedo).toBe(true);

    // Undo to state_0
    const s0 = history.undo();
    expect(s0).toBe('state_0');
    expect(history.canUndo).toBe(false);
    expect(history.canRedo).toBe(true);

    // Redo to state_1
    const r1 = history.redo();
    expect(r1).toBe('state_1');
    expect(history.current).toBe('state_1');

    // Redo to state_2
    const r2 = history.redo();
    expect(r2).toBe('state_2');
    expect(history.current).toBe('state_2');
    expect(history.canRedo).toBe(false);
  });

  it('pushing after undo clears redo future', () => {
    const history = new HistoryStack<number>(1);
    history.push(2);
    history.push(3);

    history.undo(); // back to 2
    expect(history.canRedo).toBe(true);

    history.push(4); // replaces redo branch
    expect(history.canRedo).toBe(false);
    expect(history.current).toBe(4);

    history.undo();
    expect(history.current).toBe(2);
  });

  it('caps history at maxEntries (200)', () => {
    const history = new HistoryStack<number>(0, 200);

    for (let i = 1; i <= 250; i++) {
      history.push(i);
    }

    expect(history.current).toBe(250);

    // Can only undo 200 times
    let undoCount = 0;
    while (history.canUndo) {
      history.undo();
      undoCount++;
    }

    expect(undoCount).toBe(200);
    // Oldest reachable state is 250 - 200 = 50
    expect(history.current).toBe(50);
  });

  it('clear resets the stack', () => {
    const history = new HistoryStack<string>('init');
    history.push('s1');
    history.push('s2');

    history.clear('fresh');
    expect(history.current).toBe('fresh');
    expect(history.canUndo).toBe(false);
    expect(history.canRedo).toBe(false);
  });
});
