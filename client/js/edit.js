// Review page: edit or remove the extracted cards, then save them all.

const container = document.getElementById('cards-container');
const saveAllBtn = document.getElementById('save');

function actionButton(text, className, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = text;
    button.addEventListener('click', () => handler(button));
    return button;
}

function renderCard(entry) {
    const card = document.createElement('div');
    card.className = 'card-block';
    card.dataset.id = String(entry.id);
    card.appendChild(cardImage(entry.image));

    const missing = CARD_FIELDS.every(([key]) => !entry.details[key]);
    if (missing) {
        const note = document.createElement('p');
        note.className = 'card-note';
        note.textContent = "The AI couldn't read this card. Type the details in, or remove it.";
        card.appendChild(note);
    }

    CARD_FIELDS.forEach(([key, label]) => {
        const group = document.createElement('div');
        group.className = 'field-group';
        const input = document.createElement('input');
        input.type = 'text';
        input.maxLength = 200;
        input.dataset.field = key;
        input.id = `card-${entry.id}-${key}`;
        input.value = entry.details[key] || '';
        const labelEl = document.createElement('label');
        labelEl.htmlFor = input.id;
        labelEl.textContent = label + ':';
        group.append(labelEl, input);
        card.appendChild(group);
    });
    card.appendChild(actionButton('Save Changes', 'save-btn', saveCard));
    card.appendChild(actionButton('Remove', 'remove-btn', removeCard));
    return card;
}

function updateEmptyState() {
    const hasCards = container.querySelector('.card-block') !== null;
    saveAllBtn.hidden = !hasCards;
    if (!hasCards) showMessage('No cards to review. Go to Upload and scan a business card first.', 'info');
}

function cardDetails(cardBlock) {
    const details = {};
    cardBlock.querySelectorAll('input[data-field]').forEach(input => {
        details[input.dataset.field] = input.value;
    });
    return details;
}

async function saveCard(button) {
    const cardBlock = button.closest('.card-block');
    const body = { id: Number(cardBlock.dataset.id), details: cardDetails(cardBlock) };
    try {
        await whileBusy(button, 'Saving…', () => api('/update_card', { method: 'PUT', body }));
        showMessage('Changes saved.', 'success');
    } catch (error) {
        showMessage(errorText(error));
    }
}

async function removeCard(button) {
    const cardBlock = button.closest('.card-block');
    try {
        await whileBusy(button, 'Removing…', () =>
            api('/remove_card', { method: 'DELETE', body: { id: Number(cardBlock.dataset.id) } }));
        cardBlock.remove();
        showMessage('Card removed.', 'success');
        updateEmptyState();
    } catch (error) {
        showMessage(errorText(error));
    }
}

saveAllBtn.addEventListener('click', async () => {
    try {
        // Send any unsaved edits first, so "Save All" saves what's on screen.
        await whileBusy(saveAllBtn, 'Saving…', async () => {
            for (const cardBlock of container.querySelectorAll('.card-block')) {
                await api('/update_card', {
                    method: 'PUT',
                    body: { id: Number(cardBlock.dataset.id), details: cardDetails(cardBlock) },
                });
            }
            await api('/save_final', { method: 'POST' });
        });
        window.location.href = 'results.html';
    } catch (error) {
        showMessage(errorText(error));
    }
});

async function loadCards() {
    try {
        const cards = await api('/extract');
        cards.forEach(entry => container.appendChild(renderCard(entry)));
        updateEmptyState();
    } catch (error) {
        saveAllBtn.hidden = true;
        showMessage(errorText(error));
    }
}

loadCards();
