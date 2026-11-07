// Saved contacts page, with CSV and vCard export.

const container = document.getElementById('results-container');
const exportBar = document.getElementById('export-bar');

function renderContact(entry) {
    const card = document.createElement('div');
    card.className = 'card-block';
    card.appendChild(cardImage(entry.image));
    CARD_FIELDS.forEach(([key, label]) => {
        const group = document.createElement('div');
        group.className = 'field-group';
        const labelEl = document.createElement('label');
        labelEl.textContent = label + ':';
        const value = document.createElement('span');
        value.textContent = entry.details[key] || 'N/A';
        group.append(labelEl, value);
        card.appendChild(group);
    });
    return card;
}

// Downloads through fetch (not a plain link) so an error shows a message
// instead of saving an error page as the file.
async function downloadExport(button, path, filename) {
    try {
        const response = await whileBusy(button, 'Preparing…', () => api(path, { raw: true }));
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        showMessage(`Downloaded ${filename}.`, 'success');
    } catch (error) {
        showMessage(errorText(error));
    }
}

document.getElementById('export-csv').addEventListener('click', event =>
    downloadExport(event.currentTarget, '/export/contacts.csv', 'contacts.csv'));
document.getElementById('export-vcf').addEventListener('click', event =>
    downloadExport(event.currentTarget, '/export/contacts.vcf', 'contacts.vcf'));

async function loadResults() {
    try {
        const contacts = await api('/final_results');
        contacts.forEach(entry => container.appendChild(renderContact(entry)));
        exportBar.hidden = contacts.length === 0;
        if (contacts.length === 0) showMessage('No saved contacts yet. Scan a card from the Upload tab.', 'info');
    } catch (error) {
        showMessage(errorText(error));
    }
}

loadResults();
