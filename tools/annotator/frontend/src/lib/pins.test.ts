import { describe, it, expect } from 'vitest';
import { pinsForFrame, hitTestPin, Pin } from './pins';
import { emptyLabel, placeEvent, setImpactType } from './labelModel';

describe('pins helper', () => {
  it('pinsForFrame returns pins strictly matching current frame unless showAll is true', () => {
    let label = emptyLabel({ clip_id: 'c1' }, null, 'tester');
    label = placeEvent(label, 'release', 5, 100, 200, { ghostVisible: false });
    label = placeEvent(label, 'bounce', 15, 300, 400, { ghostVisible: false });
    label = setImpactType(label, 'bat');
    label = placeEvent(label, 'impact', 25, 500, 600, { ghostVisible: false });

    // Frame 5 only has release
    const pinsF5 = pinsForFrame(label, 5, false);
    expect(pinsF5).toHaveLength(1);
    expect(pinsF5[0].kind).toBe('release');

    // Frame 15 only has bounce
    const pinsF15 = pinsForFrame(label, 15, false);
    expect(pinsF15).toHaveLength(1);
    expect(pinsF15[0].kind).toBe('bounce');

    // Frame 20 has none
    const pinsF20 = pinsForFrame(label, 20, false);
    expect(pinsF20).toHaveLength(0);

    // showAll returns all 3 pins regardless of frame
    const allPins = pinsForFrame(label, 20, true);
    expect(allPins).toHaveLength(3);
    expect(allPins.map((p) => p.kind)).toEqual(['release', 'bounce', 'impact']);
  });

  it('hitTestPin returns nearest pin within screen radius', () => {
    const pins: Pin[] = [
      { kind: 'release', frame: 5, x: 100, y: 100 },
      { kind: 'bounce', frame: 15, x: 200, y: 200 },
    ];

    // At scale = 1.0, distance is image pixels
    // Point at (105, 100) -> distance 5px <= 10px
    const hit = hitTestPin(pins, 105, 100, 1.0, 10);
    expect(hit?.kind).toBe('release');

    // Point at (115, 100) -> distance 15px > 10px -> null
    const miss = hitTestPin(pins, 115, 100, 1.0, 10);
    expect(miss).toBeNull();
  });

  it('hitTestPin scales screen distance with viewport zoom', () => {
    const pins: Pin[] = [
      { kind: 'release', frame: 5, x: 100, y: 100 },
    ];

    // Image distance is 3px. At scale 2.0, screen distance is 6px <= 10px -> hit
    const hit = hitTestPin(pins, 103, 100, 2.0, 10);
    expect(hit).toBeDefined();

    // Image distance is 3px. At scale 4.0, screen distance is 12px > 10px -> miss
    const miss = hitTestPin(pins, 103, 100, 4.0, 10);
    expect(miss).toBeNull();
  });

  it('hitTestPin picks the nearest when multiple are within radius', () => {
    const pins: Pin[] = [
      { kind: 'release', frame: 5, x: 100, y: 100 },
      { kind: 'bounce', frame: 5, x: 102, y: 100 },
    ];

    // Click at (101.5, 100): closer to bounce (dist 0.5) than release (dist 1.5)
    const hit = hitTestPin(pins, 101.5, 100, 1.0, 10);
    expect(hit?.kind).toBe('bounce');
  });
});
