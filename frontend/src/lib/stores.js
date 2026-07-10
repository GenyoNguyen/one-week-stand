import { writable } from 'svelte/store';

// active view (simple in-app navigation, synced to location.hash by App)
export const currentView = writable('daily');

// single navigation entry point — keeps store and URL hash in step so
// refresh/back always land on the view the user was looking at
export function navigate(view) {
  currentView.set(view);
  if (typeof location !== 'undefined') location.hash = view;
}

// property opened in the Property view
export const selectedProperty = writable('ACR');

// global filter state — FilterBar writes, every view reads
export const propertyFilter = writable('ALL'); // 'ALL' | property id
export const horizon = writable(30); // 30 | 60 | 90 days
export const compareMode = writable('budget'); // 'budget' | 'ly'

// alert workflow state: id -> 'accepted' | 'dismissed'
export const alertStatus = writable({});

export function setAlertStatus(id, status) {
  alertStatus.update((s) => {
    const next = { ...s };
    if (status) next[id] = status;
    else delete next[id]; // undo — back to the open queue
    return next;
  });
}
