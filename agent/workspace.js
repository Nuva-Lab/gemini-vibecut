/**
 * Workspace — Persistent Asset Storage for Creative Universe
 *
 * The workspace accumulates user's creative assets across sessions:
 * - Generated characters (anime images)
 * - Reference photos user selected
 * - Ideas and creations for future video generation
 *
 * Storage Strategy:
 * - IndexedDB: Binary image blobs (can be several MB each)
 * - localStorage: Metadata, asset lists, quick lookups
 *
 * @module workspace
 */

const DB_NAME_PREFIX = 'vibecut-ws-';
const DB_VERSION = 3;
const STORE_IMAGES = 'images';
const STORE_CHARACTERS = 'characters';
const STORE_VIDEOS = 'videos';

/**
 * Workspace class — manages persistent creative assets
 * Each session gets its own IndexedDB database for isolation.
 */
export class Workspace {
    constructor(sessionId) {
        this.db = null;
        this.initialized = false;
        this.sessionId = sessionId || 'default';
        this.dbName = `${DB_NAME_PREFIX}${this.sessionId}`;
        this.metaKey = `ws_meta_${this.sessionId}`;
    }

    /**
     * Initialize the workspace (open IndexedDB)
     * @returns {Promise<void>}
     */
    async init() {
        if (this.initialized) return;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, DB_VERSION);

            request.onerror = () => {
                console.error('[Workspace] Failed to open IndexedDB:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                this.initialized = true;
                console.log('[Workspace] Initialized successfully');
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Store for image blobs
                if (!db.objectStoreNames.contains(STORE_IMAGES)) {
                    db.createObjectStore(STORE_IMAGES, { keyPath: 'id' });
                    console.log('[Workspace] Created images store');
                }

                // Store for character metadata + image references
                if (!db.objectStoreNames.contains(STORE_CHARACTERS)) {
                    const charStore = db.createObjectStore(STORE_CHARACTERS, { keyPath: 'id' });
                    charStore.createIndex('name', 'name', { unique: false });
                    charStore.createIndex('createdAt', 'createdAt', { unique: false });
                    console.log('[Workspace] Created characters store');
                }

                // Store for generated videos
                if (!db.objectStoreNames.contains(STORE_VIDEOS)) {
                    const videoStore = db.createObjectStore(STORE_VIDEOS, { keyPath: 'id' });
                    videoStore.createIndex('createdAt', 'createdAt', { unique: false });
                    console.log('[Workspace] Created videos store');
                }
            };
        });
    }

    // =========================================================================
    // CHARACTER OPERATIONS
    // =========================================================================

    /**
     * Save a generated character to the workspace
     *
     * @param {object} characterData - Data from create-character API response
     * @param {string} characterData.character_id - Unique ID
     * @param {string} characterData.name - Character name
     * @param {string} characterData.style - Art style (e.g., "anime")
     * @param {Array} characterData.generated_images - Array of {variant, url}
     * @param {object} options - Additional options
     * @param {Array<string>} options.referencePhotos - URLs of reference photos used
     * @param {object} options.sourceAnalysis - Original analysis data (life_character)
     * @param {string} options.persona - User-provided persona (one line description)
     * @returns {Promise<object>} - Saved character with local image IDs
     */
    async saveCharacter(characterData, options = {}) {
        await this.init();

        const characterId = characterData.character_id;
        const now = new Date().toISOString();

        // Fetch and store each generated image as a blob
        const localImages = [];
        for (const img of characterData.generated_images) {
            try {
                const imageId = `${characterId}_${img.variant}`;
                const blob = await this._fetchImageAsBlob(img.url);
                await this._storeImage(imageId, blob, img.url);

                localImages.push({
                    variant: img.variant,
                    imageId: imageId,
                    originalUrl: img.url
                });

                console.log(`[Workspace] Stored image: ${imageId}`);
            } catch (error) {
                console.error(`[Workspace] Failed to store image ${img.variant}:`, error);
            }
        }

        // Store reference photos as blobs too (for offline access)
        const localReferences = [];
        if (options.referencePhotos) {
            for (let i = 0; i < options.referencePhotos.length; i++) {
                const refUrl = options.referencePhotos[i];
                try {
                    const refId = `${characterId}_ref_${i}`;
                    const blob = await this._fetchImageAsBlob(refUrl);
                    await this._storeImage(refId, blob, refUrl);
                    localReferences.push({ imageId: refId, originalUrl: refUrl });
                } catch (error) {
                    console.warn(`[Workspace] Failed to store reference ${i}:`, error);
                }
            }
        }

        // Create character record
        const character = {
            id: characterId,
            name: characterData.name,
            persona: options.persona || '',  // User-provided persona
            style: characterData.style,
            generatedImages: localImages,
            referencePhotos: localReferences,
            sourceAnalysis: options.sourceAnalysis || null,
            generationTime: characterData.generation_time_seconds,
            createdAt: now,
            updatedAt: now,
            // For future video generation
            usedInVideos: [],
            notes: ''
        };

        // Store character metadata in IndexedDB
        await this._storeCharacter(character);

        // Update quick-access metadata in localStorage
        this._updateMetadata('characterAdded', character);

        console.log(`[Workspace] Saved character: ${character.name} (${characterId})`);
        return character;
    }

    /**
     * Get all characters in the workspace
     * @returns {Promise<Array>} - Array of character objects
     */
    async getCharacters() {
        await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_CHARACTERS], 'readonly');
            const store = transaction.objectStore(STORE_CHARACTERS);
            const request = store.index('createdAt').getAll();

            request.onsuccess = () => {
                // Return in reverse chronological order (newest first)
                const characters = request.result.reverse();
                resolve(characters);
            };

            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get a specific character by ID
     * @param {string} characterId
     * @returns {Promise<object|null>}
     */
    async getCharacter(characterId) {
        await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_CHARACTERS], 'readonly');
            const store = transaction.objectStore(STORE_CHARACTERS);
            const request = store.get(characterId);

            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get an image blob URL for display
     * @param {string} imageId - The stored image ID
     * @returns {Promise<string|null>} - Object URL for the blob, or null
     */
    async getImageUrl(imageId) {
        await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_IMAGES], 'readonly');
            const store = transaction.objectStore(STORE_IMAGES);
            const request = store.get(imageId);

            request.onsuccess = () => {
                const record = request.result;
                if (record && record.blob) {
                    const url = URL.createObjectURL(record.blob);
                    resolve(url);
                } else {
                    resolve(null);
                }
            };

            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Delete a character and its images
     * @param {string} characterId
     * @returns {Promise<void>}
     */
    async deleteCharacter(characterId) {
        await this.init();

        // First get the character to find associated images
        const character = await this.getCharacter(characterId);
        if (!character) return;

        // Delete all associated images
        const imageIds = [
            ...character.generatedImages.map(img => img.imageId),
            ...character.referencePhotos.map(ref => ref.imageId)
        ];

        for (const imageId of imageIds) {
            await this._deleteImage(imageId);
        }

        // Delete the character record
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_CHARACTERS], 'readwrite');
            const store = transaction.objectStore(STORE_CHARACTERS);
            const request = store.delete(characterId);

            request.onsuccess = () => {
                this._updateMetadata('characterDeleted', { id: characterId });
                console.log(`[Workspace] Deleted character: ${characterId}`);
                resolve();
            };

            request.onerror = () => reject(request.error);
        });
    }

    // =========================================================================
    // VIDEO OPERATIONS
    // =========================================================================

    /**
     * Save a generated video to the workspace
     *
     * @param {object} videoData - Video data from animation complete event
     * @param {string} videoData.id - Unique ID (story_id)
     * @param {string} videoData.title - Video title
     * @param {string} videoData.video_url - URL path to video file
     * @param {number} videoData.duration - Video duration in seconds
     * @param {number} videoData.clip_count - Number of clips in video
     * @param {string} videoData.thumbnail_url - Optional thumbnail image URL
     * @param {Array<string>} videoData.character_ids - Character IDs used
     * @param {string} videoData.manga_id - Source manga ID
     * @returns {Promise<object>} - Saved video record
     */
    async saveVideo(videoData) {
        await this.init();

        const now = new Date().toISOString();

        const video = {
            id: videoData.id,
            title: videoData.title || `Story ${videoData.id}`,
            videoUrl: videoData.video_url,
            thumbnailUrl: videoData.thumbnail_url || null,
            duration: videoData.duration || 0,
            clipCount: videoData.clip_count || 0,
            characterIds: videoData.character_ids || [],
            mangaId: videoData.manga_id || null,
            createdAt: now,
        };

        // Store video metadata in IndexedDB
        await this._storeVideo(video);

        // Update quick-access metadata in localStorage
        this._updateMetadata('videoAdded', video);

        console.log(`[Workspace] Saved video: ${video.title} (${video.id})`);
        return video;
    }

    /**
     * Get all videos in the workspace
     * @returns {Promise<Array>} - Array of video objects
     */
    async getVideos() {
        await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_VIDEOS], 'readonly');
            const store = transaction.objectStore(STORE_VIDEOS);
            const request = store.index('createdAt').getAll();

            request.onsuccess = () => {
                // Return in reverse chronological order (newest first)
                const videos = request.result.reverse();
                resolve(videos);
            };

            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Get a specific video by ID
     * @param {string} videoId
     * @returns {Promise<object|null>}
     */
    async getVideo(videoId) {
        await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_VIDEOS], 'readonly');
            const store = transaction.objectStore(STORE_VIDEOS);
            const request = store.get(videoId);

            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Delete a video
     * @param {string} videoId
     * @returns {Promise<void>}
     */
    async deleteVideo(videoId) {
        await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_VIDEOS], 'readwrite');
            const store = transaction.objectStore(STORE_VIDEOS);
            const request = store.delete(videoId);

            request.onsuccess = () => {
                this._updateMetadata('videoDeleted', { id: videoId });
                console.log(`[Workspace] Deleted video: ${videoId}`);
                resolve();
            };

            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Store a video record in IndexedDB
     * @private
     */
    async _storeVideo(video) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_VIDEOS], 'readwrite');
            const store = transaction.objectStore(STORE_VIDEOS);
            const request = store.put(video);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    // =========================================================================
    // METADATA & STATS
    // =========================================================================

    /**
     * Get workspace summary statistics
     * @returns {Promise<object>}
     */
    async getStats() {
        const characters = await this.getCharacters();
        const videos = await this.getVideos();

        return {
            characterCount: characters.length,
            videoCount: videos.length,
            totalImages: characters.reduce(
                (sum, c) => sum + c.generatedImages.length,
                0
            ),
            characters: characters.map(c => ({
                id: c.id,
                name: c.name,
                style: c.style,
                createdAt: c.createdAt
            })),
            videos: videos.map(v => ({
                id: v.id,
                title: v.title,
                duration: v.duration,
                createdAt: v.createdAt
            }))
        };
    }

    /**
     * Clear the entire workspace
     * @returns {Promise<void>}
     */
    async clear() {
        await this.init();

        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction(
                [STORE_IMAGES, STORE_CHARACTERS, STORE_VIDEOS],
                'readwrite'
            );

            transaction.objectStore(STORE_IMAGES).clear();
            transaction.objectStore(STORE_CHARACTERS).clear();
            transaction.objectStore(STORE_VIDEOS).clear();

            transaction.oncomplete = () => {
                localStorage.removeItem(this.metaKey);
                console.log('[Workspace] Cleared all data');
                resolve();
            };

            transaction.onerror = () => reject(transaction.error);
        });
    }

    // =========================================================================
    // PRIVATE HELPERS
    // =========================================================================

    /**
     * Fetch an image URL and return as a Blob
     * @private
     */
    async _fetchImageAsBlob(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Failed to fetch image: ${response.status}`);
        }
        return response.blob();
    }

    /**
     * Store an image blob in IndexedDB
     * @private
     */
    async _storeImage(imageId, blob, originalUrl) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_IMAGES], 'readwrite');
            const store = transaction.objectStore(STORE_IMAGES);

            const record = {
                id: imageId,
                blob: blob,
                originalUrl: originalUrl,
                storedAt: new Date().toISOString()
            };

            const request = store.put(record);
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Delete an image from IndexedDB
     * @private
     */
    async _deleteImage(imageId) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_IMAGES], 'readwrite');
            const store = transaction.objectStore(STORE_IMAGES);
            const request = store.delete(imageId);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Store a character record in IndexedDB
     * @private
     */
    async _storeCharacter(character) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([STORE_CHARACTERS], 'readwrite');
            const store = transaction.objectStore(STORE_CHARACTERS);
            const request = store.put(character);

            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    /**
     * Update quick-access metadata in localStorage
     * @private
     */
    _updateMetadata(event, data) {
        try {
            const meta = JSON.parse(localStorage.getItem(this.metaKey) || '{}');

            meta.lastEvent = event;
            meta.lastEventTime = new Date().toISOString();

            if (event === 'characterAdded') {
                if (!meta.characterIds) meta.characterIds = [];
                meta.characterIds.push(data.id);
                meta.characterCount = meta.characterIds.length;
            } else if (event === 'characterDeleted') {
                if (meta.characterIds) {
                    meta.characterIds = meta.characterIds.filter(id => id !== data.id);
                    meta.characterCount = meta.characterIds.length;
                }
            } else if (event === 'videoAdded') {
                if (!meta.videoIds) meta.videoIds = [];
                meta.videoIds.push(data.id);
                meta.videoCount = meta.videoIds.length;
            } else if (event === 'videoDeleted') {
                if (meta.videoIds) {
                    meta.videoIds = meta.videoIds.filter(id => id !== data.id);
                    meta.videoCount = meta.videoIds.length;
                }
            }

            localStorage.setItem(this.metaKey, JSON.stringify(meta));
        } catch (error) {
            console.warn('[Workspace] Failed to update metadata:', error);
        }
    }
}

/**
 * Singleton workspace instance (per session)
 */
let workspaceInstance = null;
let workspaceSessionId = null;

/**
 * Get the workspace instance for a session
 * @param {string} sessionId - Session ID for isolation
 * @returns {Workspace}
 */
export function getWorkspace(sessionId) {
    if (!workspaceInstance || workspaceSessionId !== sessionId) {
        workspaceInstance = new Workspace(sessionId);
        workspaceSessionId = sessionId;
    }
    return workspaceInstance;
}

/**
 * Quick check if workspace has any content (fast, uses localStorage)
 * @param {string} sessionId - Session ID to check
 * @returns {boolean}
 */
export function hasWorkspaceContent(sessionId) {
    try {
        const metaKey = sessionId ? `ws_meta_${sessionId}` : 'ws_meta_default';
        const meta = JSON.parse(localStorage.getItem(metaKey) || '{}');
        return (meta.characterCount || 0) > 0;
    } catch {
        return false;
    }
}
