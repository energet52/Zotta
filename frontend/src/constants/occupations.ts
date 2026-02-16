/**
 * Predefined occupations for the "Occupation / Job Title" dropdown.
 * Extracted from the standard employment status list.
 * Sorted alphabetically with "Other" at the end.
 */
export const OCCUPATIONS = [
  'Business Owner',
  'Civil Servant',
  'Clerical',
  'Commission Agent',
  'Domestic/Janitor',
  'Driver/Courier',
  'Entertainment',
  'Factory Worker',
  'Farmer',
  'Fisherman',
  'JDF',
  'Managerial',
  'Manual/Laborer',
  'Minibus/Maxi Driver',
  'Nurse',
  'Security',
  'Skilled Trade',
  'Supervisor',
  'Taxi Driver',
  'Teacher',
  'Vendor',
  'Waiter/Waitress/Bar',
] as const;

export const OCCUPATION_OTHER = 'Other';

/** All options including "Other" at the end.
 *  NOTE: When used with SearchableSelect's `allowOther` prop, do NOT include
 *  OCCUPATION_OTHER here — the component appends its own "Other" entry. */
export const OCCUPATION_OPTIONS = [...OCCUPATIONS] as string[];

/** Check if a value is a predefined occupation (not "Other" and not custom) */
export function isKnownOccupation(value: string | null | undefined): boolean {
  if (!value) return false;
  return (OCCUPATION_OPTIONS as readonly string[]).includes(value);
}
