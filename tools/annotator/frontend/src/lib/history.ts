/**
 * Generic undo/redo history stack with fixed max capacity.
 */

export class HistoryStack<T> {
  private past: T[] = [];
  private present: T;
  private future: T[] = [];
  private readonly maxEntries: number;

  constructor(initialState: T, maxEntries = 200) {
    this.present = initialState;
    this.maxEntries = maxEntries;
  }

  get current(): T {
    return this.present;
  }

  get canUndo(): boolean {
    return this.past.length > 0;
  }

  get canRedo(): boolean {
    return this.future.length > 0;
  }

  /**
   * Pushes a new state. Clears future redo stack and evicts oldest history if capacity exceeded.
   */
  push(state: T): void {
    this.past.push(this.present);
    if (this.past.length > this.maxEntries) {
      this.past.shift();
    }
    this.present = state;
    this.future = [];
  }

  /**
   * Undoes the last operation, moving current state to future and returning previous state.
   */
  undo(): T | null {
    if (!this.canUndo) {
      return null;
    }
    const previous = this.past.pop()!;
    this.future.unshift(this.present);
    this.present = previous;
    return this.present;
  }

  /**
   * Redoes the previously undone operation, moving state from future to past.
   */
  redo(): T | null {
    if (!this.canRedo) {
      return null;
    }
    const next = this.future.shift()!;
    this.past.push(this.present);
    this.present = next;
    return this.present;
  }

  /**
   * Clears all history and sets a new baseline present state.
   */
  clear(initialState: T): void {
    this.past = [];
    this.present = initialState;
    this.future = [];
  }
}
