import { describe, it, expect } from 'vitest';
import { computeGhostVisible, GhostStateInput } from './ghost';

describe('computeGhostVisible', () => {
  it('returns true when allowed, not blind, and at least one ghost overlay is on', () => {
    const s1: GhostStateInput = {
      ghostAllowed: true,
      blindToggle: false,
      overlays: { ghostTrajectory: true, ghostEvents: false },
    };
    expect(computeGhostVisible(s1)).toBe(true);

    const s2: GhostStateInput = {
      ghostAllowed: true,
      blindToggle: false,
      overlays: { ghostTrajectory: false, ghostEvents: true },
    };
    expect(computeGhostVisible(s2)).toBe(true);
  });

  it('returns false if ghostAllowed is false', () => {
    const s: GhostStateInput = {
      ghostAllowed: false,
      blindToggle: false,
      overlays: { ghostTrajectory: true, ghostEvents: true },
    };
    expect(computeGhostVisible(s)).toBe(false);
  });

  it('returns false if blindToggle is true', () => {
    const s: GhostStateInput = {
      ghostAllowed: true,
      blindToggle: true,
      overlays: { ghostTrajectory: true, ghostEvents: true },
    };
    expect(computeGhostVisible(s)).toBe(false);
  });

  it('returns false if neither ghostTrajectory nor ghostEvents overlay is enabled', () => {
    const s: GhostStateInput = {
      ghostAllowed: true,
      blindToggle: false,
      overlays: { ghostTrajectory: false, ghostEvents: false },
    };
    expect(computeGhostVisible(s)).toBe(false);
  });
});
