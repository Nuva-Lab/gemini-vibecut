/**
 * Photo set fixtures for different test scenarios
 *
 * These represent different types of photo galleries users might have.
 * Used to test how the agent behaves with varying content types.
 */

export const PHOTO_SETS = {
  petsOnly: {
    name: 'Pets Only (10 images)',
    description: 'A gallery containing only pet photos - cats and dogs',
    photos: [
      '/assets/demo_photos/pets/cat_01.webp',
      '/assets/demo_photos/pets/cat_02.webp',
      '/assets/demo_photos/pets/cat_03.webp',
      '/assets/demo_photos/pets/cat_04.webp',
      '/assets/demo_photos/pets/cat_05.webp',
      '/assets/demo_photos/pets/dog_01.webp',
      '/assets/demo_photos/pets/dog_02.webp',
      '/assets/demo_photos/pets/dog_03.webp',
      '/assets/demo_photos/pets/dog_04.webp',
      '/assets/demo_photos/pets/dog_05.webp'
    ]
  },

  peopleOnly: {
    name: 'People Only (10 images)',
    description: 'A gallery containing only photos of people/family',
    photos: Array.from({ length: 10 }, (_, i) =>
      `/assets/demo_photos/people/family_${String(i + 1).padStart(2, '0')}.webp`
    )
  },

  worldsOnly: {
    name: 'Worlds Only (8 images)',
    description: 'A gallery with travel/location photos',
    photos: Array.from({ length: 8 }, (_, i) =>
      `/assets/demo_photos/worlds/tokyo_${String(i + 1).padStart(2, '0')}.webp`
    )
  },

  mixed: {
    name: 'Mixed (pets + people + worlds)',
    description: 'A realistic mixed gallery with pets, people, and places',
    photos: [
      '/assets/demo_photos/pets/cat_01.webp',
      '/assets/demo_photos/pets/cat_02.webp',
      '/assets/demo_photos/pets/dog_01.webp',
      '/assets/demo_photos/people/family_01.webp',
      '/assets/demo_photos/people/family_02.webp',
      '/assets/demo_photos/worlds/tokyo_01.webp',
      '/assets/demo_photos/worlds/tokyo_02.webp'
    ]
  },

  singleCat: {
    name: 'Single Cat (5 images of same cat)',
    description: 'Multiple photos of the same pet - tests character recognition',
    photos: [
      '/assets/demo_photos/pets/cat_01.webp',
      '/assets/demo_photos/pets/cat_02.webp',
      '/assets/demo_photos/pets/cat_03.webp',
      '/assets/demo_photos/pets/cat_04.webp',
      '/assets/demo_photos/pets/cat_05.webp'
    ]
  },

  minimal: {
    name: 'Minimal (2 images)',
    description: 'Very few photos - tests edge cases',
    photos: [
      '/assets/demo_photos/pets/cat_01.webp',
      '/assets/demo_photos/worlds/tokyo_01.webp'
    ]
  },

  empty: {
    name: 'Empty Gallery',
    description: 'No photos - tests empty state handling',
    photos: []
  }
};

/**
 * Get all photo set names for parameterized testing
 */
export function getPhotoSetNames() {
  return Object.keys(PHOTO_SETS);
}

/**
 * Get a photo set by name
 * @param {string} name - Photo set name
 * @returns {object} Photo set configuration
 */
export function getPhotoSet(name) {
  return PHOTO_SETS[name] || null;
}
