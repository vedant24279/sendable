/**
 * Ghost visibility computation.
 * computeGhostVisible(s) = s.ghostAllowed && !s.blindToggle && (s.overlays.ghostTrajectory || s.overlays.ghostEvents)
 */

export interface GhostOverlayToggles {
  ghostTrajectory: boolean;
  ghostEvents: boolean;
}

export interface GhostStateInput {
  ghostAllowed: boolean;
  blindToggle?: boolean;
  overlays: GhostOverlayToggles;
}

/**
 * Computes whether ghost predictions (trajectory and event markers) should be visible.
 *
 * In store.ts, `ghostAllowed` tracks permission (true by default).
 * If `blindToggle` is present (or passed), it inverts ghost permissions.
 * Ghost is visible only when allowed, blind mode is not toggled on, and at least one ghost overlay is enabled.
 */
export function computeGhostVisible(s: GhostStateInput): boolean {
  if (!s) return false;
  const blind = Boolean(s.blindToggle);
  const overlaysActive = Boolean(s.overlays?.ghostTrajectory || s.overlays?.ghostEvents);
  return Boolean(s.ghostAllowed && !blind && overlaysActive);
}
