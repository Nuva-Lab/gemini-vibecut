/**
 * Mock Gemini API responses for testing
 *
 * These simulate what Gemini's gallery analysis returns.
 * Tests can use these to verify agent behavior without making API calls.
 */

/**
 * Create a mock gallery analysis response
 *
 * @param {object} options - Configuration for the mock response
 * @param {number} options.characterCount - Number of characters to include
 * @param {number} options.placeCount - Number of places to include
 * @param {number} options.sparkCount - Number of creative sparks to include
 * @param {string} options.characterType - Type of characters ('pet' or 'person')
 * @param {number} options.photosPerCharacter - Photos per character (affects creation eligibility)
 * @returns {object} Mock analysis result matching the expected schema
 */
export function createMockAnalysisResponse(options = {}) {
  const {
    characterCount = 2,
    placeCount = 1,
    sparkCount = 2,
    characterType = 'pet',
    photosPerCharacter = 4
  } = options;

  return {
    opening_reaction: `What a wonderful collection! I see ${characterCount} special ${characterType === 'pet' ? 'companions' : 'people'} here...`,

    life_characters: Array.from({ length: characterCount }, (_, i) => ({
      name_suggestion: characterType === 'pet'
        ? ['Whiskers', 'Shadow', 'Mochi', 'Luna', 'Ginger'][i % 5]
        : ['Alex', 'Jordan', 'Sam', 'Taylor', 'Morgan'][i % 5],
      who_they_are: characterType === 'pet'
        ? `Your beloved ${['orange tabby', 'black cat', 'golden retriever', 'calico cat', 'husky'][i % 5]} companion`
        : `A special person in your life`,
      appearances: photosPerCharacter,
      what_you_notice: characterType === 'pet'
        ? 'Always capturing the coziest moments'
        : 'Lots of happy memories together',
      type: characterType,
      image_indices: Array.from({ length: photosPerCharacter }, (_, j) => i * photosPerCharacter + j)
    })),

    meaningful_places: Array.from({ length: placeCount }, (_, i) => ({
      place_description: ['Cozy living room', 'Sunny backyard', 'Kitchen nook', 'Window perch'][i % 4],
      why_it_seems_to_matter: 'A place where memories are made',
      mood: ['warm', 'peaceful', 'playful', 'cozy'][i % 4],
      appearances: 2,
      image_indices: [10 + i * 2, 11 + i * 2]
    })),

    gallery_story: characterType === 'pet'
      ? 'A beautiful story of daily life with your furry companions'
      : 'A collection of precious moments with loved ones',

    patterns_noticed: [
      'Golden hour lighting',
      'Candid moments',
      characterType === 'pet' ? 'Close-up portraits' : 'Group shots'
    ],

    emotional_moments: [
      {
        description: characterType === 'pet'
          ? 'A peaceful nap in the sunbeam'
          : 'A genuine laugh captured perfectly',
        mood: 'peaceful'
      }
    ],

    creative_sparks: Array.from({ length: sparkCount }, (_, i) => ({
      idea: [
        'A cozy day at home comic',
        'An adventure in the garden',
        'A magical evening scene',
        'A slice-of-life montage'
      ][i % 4],
      why_this_fits: 'Based on the warmth in your photos',
      based_on: 'Overall gallery mood'
    })),

    image_details: []
  };
}

/**
 * Create mock story options for comic/scene development
 *
 * @param {string} storyType - 'comic' or 'scene'
 * @param {string} characterName - Name of the character
 * @returns {object} Mock story options
 */
export function createMockStoryOptions(storyType = 'comic', characterName = 'Mochi') {
  if (storyType === 'comic') {
    return {
      story_type: 'comic',
      character_name: characterName,
      options: [
        {
          emoji: '🌟',
          label: 'A Day of Adventure',
          description: 'An exciting journey from morning to night',
          beats: [
            `${characterName} wakes up curious`,
            'Discovers something mysterious',
            'Faces an unexpected challenge',
            'Triumphant happy ending'
          ]
        },
        {
          emoji: '😴',
          label: 'Lazy Sunday',
          description: 'A peaceful, cozy day',
          beats: [
            'Morning stretch in the sunbeam',
            'Finding the perfect napping spot',
            'Unexpected visitor interruption',
            'Back to peaceful napping'
          ]
        },
        {
          emoji: '🎉',
          label: 'Celebration Time',
          description: 'A special occasion to remember',
          beats: [
            'A special day begins',
            'Preparation and excitement',
            'The main event',
            'Grateful moment of reflection'
          ]
        }
      ]
    };
  }

  // Scene options
  return {
    story_type: 'scene',
    character_name: characterName,
    options: [
      {
        emoji: '🌅',
        label: 'Golden Hour Portrait',
        description: 'Warm sunset lighting creates a magical atmosphere'
      },
      {
        emoji: '🌸',
        label: 'Spring Garden',
        description: 'Surrounded by blooming flowers and butterflies'
      },
      {
        emoji: '☕',
        label: 'Cozy Cafe',
        description: 'A peaceful moment with warm drinks and soft light'
      },
      {
        emoji: '🏔️',
        label: 'Mountain Summit',
        description: 'An epic vista at the top of the world'
      }
    ]
  };
}

/**
 * Create a mock saved character (from workspace)
 *
 * @param {object} options - Character options
 * @returns {object} Mock saved character
 */
export function createMockSavedCharacter(options = {}) {
  const {
    id = `char_${Date.now()}`,
    name = 'Mochi',
    style = 'anime',
    type = 'pet'
  } = options;

  return {
    id,
    name,
    style,
    createdAt: new Date().toISOString(),
    sourceAnalysis: {
      who_they_are: type === 'pet' ? 'Your beloved companion' : 'A special person',
      type,
      appearances: 5
    },
    generatedImages: [
      { url: `mock://character/${id}/main.png`, role: 'main' },
      { url: `mock://character/${id}/alt1.png`, role: 'alternate' }
    ],
    referencePhotos: [
      `mock://reference/${id}/1.webp`,
      `mock://reference/${id}/2.webp`,
      `mock://reference/${id}/3.webp`
    ]
  };
}

/**
 * Create multiple mock saved characters
 *
 * @param {number} count - Number of characters to create
 * @returns {Array} Array of mock saved characters
 */
export function createMockSavedCharacters(count = 2) {
  const names = ['Mochi', 'Whiskers', 'Luna', 'Shadow', 'Ginger'];
  return Array.from({ length: count }, (_, i) =>
    createMockSavedCharacter({
      id: `saved_char_${i}`,
      name: names[i % names.length],
      type: 'pet'
    })
  );
}
