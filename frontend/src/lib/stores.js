import { writable } from 'svelte/store';

// active view (simple in-app navigation, synced to location.hash by App)
export const currentView = writable('daily');

// property opened in the Property view
export const selectedProperty = writable('ACR');

// global filter state — FilterBar writes, every view reads
export const propertyFilter = writable('ALL'); // 'ALL' | property id
export const horizon = writable(30); // 30 | 60 | 90 days
export const compareMode = writable('budget'); // 'budget' | 'ly'

// alert workflow state: id -> 'accepted' | 'dismissed'
export const alertStatus = writable({});

export function setAlertStatus(id, status) {
  alertStatus.update((s) => ({ ...s, [id]: status }));
}
