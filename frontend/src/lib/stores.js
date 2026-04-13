/**
 * Svelte stores for application state.
 */
import { writable } from 'svelte/store';

export const models = writable([]);
export const categories = writable([]);
export const destinations = writable([]);
export const searchQuery = writable('');
export const selectedCategory = writable(null);
export const viewMode = writable('grid'); // 'grid' | 'list'
export const updateInfo = writable(null); // { latest, release_url } when update available
