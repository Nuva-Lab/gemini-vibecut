/**
 * UI Renderers — Card and Widget Rendering Functions
 *
 * These functions handle the visual representation of subjects
 * and agent responses. They are called by the agent brain via callbacks.
 *
 * Design principle: Renderers are pure UI — no business logic.
 */

/**
 * Renderer configuration
 * Set this up before using renderers
 */
export const rendererConfig = {
    /** Function to get photo URL by index */
    getPhotoUrl: (index) => null,
    /** Function to handle reaction clicks */
    onReaction: (type, index, reaction) => {},
    /** Function to handle Next button clicks */
    onNext: (subjectId, name) => {},
    /** Function to handle idea action clicks */
    onIdeaAction: (spark, action) => {},
    /** Current device ('android' or 'iphone') */
    device: 'android'
};

/**
 * Configure the renderers
 * @param {object} config - Partial config to merge
 */
export function configureRenderers(config) {
    Object.assign(rendererConfig, config);
}

/**
 * Get the chat messages container for current device
 * @returns {HTMLElement}
 */
function getMessagesContainer() {
    return document.getElementById(`${rendererConfig.device}-chat-messages`);
}

/**
 * Render a character card
 *
 * @param {object} char - Character data from analysis
 * @param {number} index - Character index
 * @param {boolean} showNext - Whether to show Next button
 */
export function renderCharacterCard(char, index, showNext) {
    const container = getMessagesContainer();
    const card = document.createElement('div');
    card.className = 'chat-msg assistant';

    const name = char.name_suggestion || char.who_they_are;
    const cardId = `char-card-${index}`;
    const subjectId = `char_${index}`;
    const emoji = char.type === 'pet' ? '🐱' : (char.type === 'person' ? '👤' : '✨');

    // Get thumbnail
    const bestPhotoIdx = char.image_indices?.[0];
    const thumbUrl = bestPhotoIdx !== undefined ? rendererConfig.getPhotoUrl(bestPhotoIdx) : null;
    const thumbHtml = thumbUrl
        ? `<img src="${thumbUrl}" class="card-thumb" alt="${name}">`
        : '';

    // Next button
    const nextHtml = showNext
        ? `<button class="next-btn" id="next-${cardId}">Next →</button>`
        : '';

    card.innerHTML = `
        <div class="chat-msg-bubble" style="padding: 10px 12px;" id="${cardId}">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span style="font-size: 20px;">${emoji}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 14px;">${name}</div>
                    <div style="font-size: 11px; color: var(--on-surface-variant);">${char.appearances || char.image_indices?.length || 0} photos</div>
                </div>
            </div>
            ${thumbHtml}
            <div style="font-size: 13px; color: var(--on-surface); line-height: 1.5; margin-bottom: 8px;">
                ${char.what_you_notice || ''}
            </div>
            <div class="reaction-bar">
                <div class="reactions">
                    <button class="reaction-btn love" data-reaction="love" title="Love it!"></button>
                    <button class="reaction-btn haha" data-reaction="haha" title="Haha, fun!"></button>
                    <button class="reaction-btn angry" data-reaction="angry" title="Skip this"></button>
                </div>
                ${nextHtml}
            </div>
        </div>
    `;

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;

    // Attach reaction handlers
    card.querySelectorAll('.reaction-btn').forEach(btn => {
        btn.onclick = () => {
            // Visual feedback
            card.querySelectorAll('.reaction-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            // Callback
            rendererConfig.onReaction('character', index, btn.dataset.reaction);
        };
    });

    // Attach next handler
    if (showNext) {
        const nextBtn = card.querySelector(`#next-${cardId}`);
        if (nextBtn) {
            nextBtn.onclick = () => rendererConfig.onNext(subjectId, name);
        }
    }
}

/**
 * Render a place card
 *
 * @param {object} place - Place data from analysis
 * @param {number} index - Place index
 * @param {boolean} showNext - Whether to show Next button
 */
export function renderPlaceCard(place, index, showNext) {
    const container = getMessagesContainer();
    const card = document.createElement('div');
    card.className = 'chat-msg assistant';

    const name = place.place_description;
    const cardId = `place-card-${index}`;
    const subjectId = `place_${index}`;

    // Get thumbnail
    const bestPhotoIdx = place.image_indices?.[0];
    const thumbUrl = bestPhotoIdx !== undefined ? rendererConfig.getPhotoUrl(bestPhotoIdx) : null;
    const thumbHtml = thumbUrl
        ? `<img src="${thumbUrl}" class="card-thumb" alt="${name}">`
        : '';

    // Next button
    const nextHtml = showNext
        ? `<button class="next-btn" id="next-${cardId}">Next →</button>`
        : '';

    card.innerHTML = `
        <div class="chat-msg-bubble" style="padding: 10px 12px;" id="${cardId}">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <span style="font-size: 20px;">🌍</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600; font-size: 14px;">${name}</div>
                    <div style="font-size: 11px; color: var(--on-surface-variant);">${place.mood || ''}</div>
                </div>
            </div>
            ${thumbHtml}
            <div style="font-size: 13px; color: var(--on-surface); line-height: 1.5; margin-bottom: 8px;">
                ${place.why_it_seems_to_matter || ''}
            </div>
            <div class="reaction-bar">
                <div class="reactions">
                    <button class="reaction-btn love" data-reaction="love" title="Love it!"></button>
                    <button class="reaction-btn haha" data-reaction="haha" title="Haha, fun!"></button>
                    <button class="reaction-btn angry" data-reaction="angry" title="Skip this"></button>
                </div>
                ${nextHtml}
            </div>
        </div>
    `;

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;

    // Attach reaction handlers
    card.querySelectorAll('.reaction-btn').forEach(btn => {
        btn.onclick = () => {
            card.querySelectorAll('.reaction-btn').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            rendererConfig.onReaction('place', index, btn.dataset.reaction);
        };
    });

    // Attach next handler
    if (showNext) {
        const nextBtn = card.querySelector(`#next-${cardId}`);
        if (nextBtn) {
            nextBtn.onclick = () => rendererConfig.onNext(subjectId, name);
        }
    }
}

/**
 * Render an idea card
 *
 * @param {object} spark - Idea/spark data from analysis
 * @param {number} index - Idea index
 * @param {boolean} showNext - Whether to show Next button
 */
export function renderIdeaCard(spark, index, showNext) {
    const container = getMessagesContainer();
    const card = document.createElement('div');
    card.className = 'chat-msg assistant';

    const name = spark.idea;
    const cardId = `idea-card-${index}`;
    const subjectId = `idea_${index}`;

    // Next button
    const nextHtml = showNext
        ? `<button class="next-btn" id="next-${cardId}" style="margin-left: auto;">Next →</button>`
        : '';

    card.innerHTML = `
        <div class="chat-msg-bubble" style="padding: 10px 12px;" id="${cardId}">
            <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 6px;">
                <span style="font-size: 24px;">💡</span>
                <div style="font-weight: 600; font-size: 14px; line-height: 1.4;">${name}</div>
            </div>
            <div style="font-size: 13px; color: var(--on-surface); line-height: 1.5; margin-bottom: 8px;">
                ${spark.why_this_fits || ''}
            </div>
            <div class="idea-actions" style="display: flex; gap: 8px; padding-top: 8px; border-top: 1px solid var(--outline); align-items: center;">
                <button class="a2ui-chip" style="margin: 0; font-size: 11px; padding: 4px 10px;" id="try-${cardId}">
                    Let's try this ✨
                </button>
                <button class="a2ui-chip" style="margin: 0; font-size: 11px; padding: 4px 10px; background: var(--surface-variant);" id="more-${cardId}">
                    Tell me more
                </button>
                ${nextHtml}
            </div>
        </div>
    `;

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;

    // Attach handlers
    card.querySelector(`#try-${cardId}`).onclick = () => rendererConfig.onIdeaAction(spark, 'try');
    card.querySelector(`#more-${cardId}`).onclick = () => rendererConfig.onIdeaAction(spark, 'more');

    // Attach next handler
    if (showNext) {
        const nextBtn = card.querySelector(`#next-${cardId}`);
        if (nextBtn) {
            nextBtn.onclick = () => rendererConfig.onNext(subjectId, name);
        }
    }
}

/**
 * Render a chat message bubble
 *
 * @param {string} role - 'assistant' or 'user'
 * @param {string} text - Message text
 * @param {boolean} scroll - Whether to scroll to bottom
 */
export function renderChatMessage(role, text, scroll = true) {
    const container = getMessagesContainer();
    const msg = document.createElement('div');
    msg.className = `chat-msg ${role}`;
    msg.innerHTML = `<div class="chat-msg-bubble">${text}</div>`;
    container.appendChild(msg);
    if (scroll) container.scrollTop = container.scrollHeight;
}

/**
 * Render a skill suggestion card (e.g., "Turn X into anime?")
 *
 * @param {object} character - Character data
 * @param {number} charIndex - Character index
 * @param {function} onAccept - Callback when user accepts
 * @param {function} onDecline - Callback when user declines
 */
export function renderSkillSuggestionCard(character, charIndex, onAccept, onDecline) {
    const container = getMessagesContainer();
    const card = document.createElement('div');
    card.className = 'chat-msg assistant';
    card.id = `skill-suggest-${charIndex}`;

    const charName = character.name_suggestion || 'this character';
    const photoCount = character.image_indices?.length || 0;

    card.innerHTML = `
        <div class="chat-msg-bubble skill-suggestion-card">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="font-size: 20px;">✨</span>
                <div style="font-weight: 600; font-size: 14px;">Turn ${charName} into anime?</div>
            </div>
            <div style="font-size: 12px; color: var(--on-surface-variant); line-height: 1.5;">
                I can generate an anime character sheet using ${photoCount} photos of ${charName}.
                You'll pick 3 reference photos for the best result.
            </div>
            <div style="display: flex; gap: 8px; margin-top: 10px;">
                <button class="skill-btn accept">✨ Let's do it!</button>
                <button class="skill-btn decline" style="background: var(--surface-variant); color: var(--on-surface-variant);">Maybe later</button>
            </div>
        </div>
    `;

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;

    // Attach handlers
    card.querySelector('.skill-btn.accept').onclick = () => {
        card.remove();
        onAccept();
    };
    card.querySelector('.skill-btn.decline').onclick = () => {
        card.remove();
        onDecline();
    };
}

/**
 * Add typing indicator
 * @returns {HTMLElement} - The typing indicator element (for removal)
 */
export function addTypingIndicator() {
    const container = getMessagesContainer();
    const typing = document.createElement('div');
    typing.className = 'chat-msg assistant';
    typing.id = `${rendererConfig.device}-typing`;
    typing.innerHTML = `
        <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;
    return typing;
}

/**
 * Remove typing indicator
 */
export function removeTypingIndicator() {
    const typing = document.getElementById(`${rendererConfig.device}-typing`);
    if (typing) typing.remove();
}
