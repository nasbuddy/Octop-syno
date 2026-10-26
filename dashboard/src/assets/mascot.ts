import { getAppUrl } from "../api/config";

/**
 * Shared empty-state mascot (served from ``dashboard/public``).
 * Prefer ``OctopEmptyMascot`` / ``EmptyState variant="mascot"`` over hardcoding.
 */
export const OCTOP_EMPTY_MASCOT_SRC = getAppUrl("/octop-mascot-empty.png");
