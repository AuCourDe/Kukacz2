/* Gacek 🦇 - Whisper Analyzer JavaScript */

// ====================================
// Color Schemes (Warianty kolorystyczne)
// ====================================

const colorSchemes = {
    light: [
        { id: 'light-default', name: 'Standardowy', class: '' },
        { id: 'light-masculine', name: 'Męski', class: 'light-masculine' },
        { id: 'light-feminine', name: 'Kobiecy', class: 'light-feminine' }
    ],
    dark: [
        { id: 'dark-default', name: 'Standardowy', class: '' },
        { id: 'dark-masculine', name: 'Męski', class: 'dark-masculine' },
        { id: 'dark-feminine', name: 'Kobiecy', class: 'dark-feminine' }
    ]
};

// ====================================
// Theme Toggle (Jasny/Ciemny)
// ====================================

function initThemeToggle() {
    const toggle = document.getElementById('theme-toggle');
    if (!toggle) return;
    
    // Sprawdź zapisany motyw
    const savedTheme = localStorage.getItem('gacek-theme');
    const savedScheme = localStorage.getItem('gacek-color-scheme');
    
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        toggle.checked = true;
    }
    
    // Ustaw ikonę w zależności od trybu
    updateThemeIcon();
    
    // Inicjalizuj selektor kolorów
    initColorSchemeSelector();
    
    // Przywróć zapisany wariant
    if (savedScheme) {
        applyColorScheme(savedScheme);
    }
    
    toggle.addEventListener('change', function() {
        // Pobierz aktualny wariant kolorystyczny przed zmianą
        const currentScheme = localStorage.getItem('gacek-color-scheme');
        const currentVariant = currentScheme ? currentScheme.replace('light-', '').replace('dark-', '') : 'default';
        
        // Usuń wszystkie warianty kolorystyczne
        clearColorSchemes();
        
        if (this.checked) {
            document.body.classList.add('dark-mode');
            localStorage.setItem('gacek-theme', 'dark');
            // Zachowaj wariant kolorystyczny dla ciemnego motywu
            const newScheme = 'dark-' + currentVariant;
            localStorage.setItem('gacek-color-scheme', newScheme);
            applyColorScheme(newScheme);
            showThemeMessage('Tryb ciemny włączony');
        } else {
            document.body.classList.remove('dark-mode');
            localStorage.setItem('gacek-theme', 'light');
            // Zachowaj wariant kolorystyczny dla jasnego motywu
            const newScheme = 'light-' + currentVariant;
            localStorage.setItem('gacek-color-scheme', newScheme);
            applyColorScheme(newScheme);
            showThemeMessage('Tryb jasny włączony');
        }
        
        // Zaktualizuj ikonę
        updateThemeIcon();
        
        // Odśwież przełącznik kolorów
        initColorSchemeSelector();
    });
}

function updateThemeIcon() {
    const icon = document.querySelector('.theme-toggle-icon');
    if (!icon) return;
    
    const isDark = document.body.classList.contains('dark-mode');
    // Czarno-białe ikony (nie emoji)
    // W trybie jasnym pokazuj księżyc (przejście do ciemnego)
    // W trybie ciemnym pokazuj słoneczko (przejście do jasnego)
    icon.textContent = isDark ? '☉' : '☽';
}

// Inicjalizacja przełącznika wariantów kolorystycznych
function initColorSchemeSelector() {
    const container = document.getElementById('color-scheme-selector');
    if (!container) return;
    
    const isDark = document.body.classList.contains('dark-mode');
    const schemes = isDark ? colorSchemes.dark : colorSchemes.light;
    const savedScheme = localStorage.getItem('gacek-color-scheme');
    
    container.innerHTML = '';
    
    schemes.forEach((scheme, index) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'color-scheme-btn';
        btn.dataset.scheme = scheme.id;
        btn.title = scheme.name;
        
        // Zaznacz aktywny lub pierwszy
        if (savedScheme === scheme.id || (!savedScheme && index === 0)) {
            btn.classList.add('active');
        }
        
        btn.addEventListener('click', () => {
            container.querySelectorAll('.color-scheme-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyColorScheme(scheme.id);
        });
        
        container.appendChild(btn);
    });
}

// Zastosowanie wariantu kolorystycznego
function applyColorScheme(schemeId) {
    const body = document.body;
    const isDark = body.classList.contains('dark-mode');
    
    // Usuń wszystkie klasy wariantów
    clearColorSchemes();
    
    // Znajdź wariant
    const schemes = isDark ? colorSchemes.dark : colorSchemes.light;
    const scheme = schemes.find(s => s.id === schemeId);
    
    if (scheme && scheme.class) {
        body.classList.add(scheme.class);
    }
    
    localStorage.setItem('gacek-color-scheme', schemeId);
}

// Usuń wszystkie klasy wariantów kolorystycznych
function clearColorSchemes() {
    const body = document.body;
    const allClasses = [
        ...colorSchemes.light.map(s => s.class),
        ...colorSchemes.dark.map(s => s.class)
    ].filter(c => c);
    
    allClasses.forEach(cls => body.classList.remove(cls));
}

function showThemeMessage(message) {
    const msgEl = document.getElementById('theme-message');
    if (!msgEl) return;
    
    msgEl.textContent = message;
    msgEl.classList.add('show');
    
    setTimeout(() => {
        msgEl.classList.remove('show');
    }, 2000);
}

// ====================================
// Toast Notifications
// ====================================

function showToast(message, type = 'info', duration = 5000) {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ',
        warning: '⚠'
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${message}</span>`;
    
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ====================================
// Queue Refresh
// ====================================

const statusLabels = {
    'queued': 'W kolejce',
    'processing': 'Przetwarzanie',
    'completed': 'Zakończone',
    'failed': 'Błąd'
};
const preprocessReasonLabels = window.PREPROCESS_REASON_LABELS || {};

const processingStarts = new Map();
const countdownIntervals = new Map();

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 0) {
        return `${mins}m ${secs}s`;
    }
    return `${secs}s`;
}

function updateCountdown(itemId, estimatedMinutes, startedAt) {
    if (!startedAt) return;

    const startTime = new Date(startedAt).getTime();
    const estimatedMs = estimatedMinutes * 60 * 1000;
    const endTime = startTime + estimatedMs;

    function update() {
        const now = Date.now();
        const elapsed = Math.floor((now - startTime) / 1000);
        const remaining = Math.max(0, Math.floor((endTime - now) / 1000));

        const countdownEl = document.getElementById(`countdown-${itemId}`);
        if (countdownEl) {
            if (remaining > 0) {
                countdownEl.textContent = `Pozostało: ~${formatTime(remaining)}`;
            } else {
                countdownEl.textContent = `Przetwarzanie... (${formatTime(elapsed)})`;
            }
        }
    }

    update();

    if (countdownIntervals.has(itemId)) {
        clearInterval(countdownIntervals.get(itemId));
    }
    const interval = setInterval(update, 1000);
    countdownIntervals.set(itemId, interval);
}

function stopCountdown(itemId) {
    if (countdownIntervals.has(itemId)) {
        clearInterval(countdownIntervals.get(itemId));
        countdownIntervals.delete(itemId);
    }
    processingStarts.delete(itemId);
}

async function refreshQueue() {
    const queueBody = document.getElementById('queue-body');
    if (!queueBody) return;
    
    try {
        const response = await fetch('/queue.json', { cache: 'no-store' });
        if (!response.ok) return;
        const data = await response.json();
        renderQueue(data.items || []);
    } catch (err) {
        console.error('Nie udało się pobrać kolejki:', err);
    }
}

function renderQueue(items) {
    const queueBody = document.getElementById('queue-body');
    if (!queueBody) return;
    
    if (!items.length) {
        queueBody.innerHTML = '<tr class="queue-empty"><td colspan="5">Brak zadań w kolejce.</td></tr>';
        return;
    }
    
    queueBody.innerHTML = items.map(item => {
        const downloads = item.status === 'completed'
            ? `<a href="/download/${item.id}/transcription">Transkrypcja</a>
               <a href="/download/${item.id}/analysis">Analiza</a>`
            : '<small>–</small>';
        
        const preprocessKey = item.preprocess_reason
            || (item.preprocess_requested ? 'default_preprocess' : 'default_process_original');
        const preprocessLabel = preprocessReasonLabels[preprocessKey] || preprocessKey;
        const preprocessApplied = !!item.preprocess_applied;
        const preprocessHtml = `
            <td class="preprocess-info">
                <span class="preprocess-pill ${preprocessApplied ? 'on' : 'off'}">
                    ${preprocessApplied ? 'Poprawione' : 'Oryginał'}
                </span>
                <small>${preprocessLabel}</small>
            </td>
        `;
        
        let statusHtml = `<span class="status ${item.status}">${statusLabels[item.status] || item.status}</span>`;
        
        if (item.status === 'processing' && item.started_at) {
            if (!processingStarts.has(item.id)) {
                processingStarts.set(item.id, { start: item.started_at, estimated: item.estimated_minutes });
                updateCountdown(item.id, item.estimated_minutes, item.started_at);
            }
            statusHtml += `<br/><small id="countdown-${item.id}">Obliczanie...</small>`;
        } else if (item.status === 'completed' && item.processing_time) {
            stopCountdown(item.id);
            statusHtml += `<br/><small>Przetworzone w czasie: ${item.processing_time}</small>`;
            
            // Dodaj status promptu jeśli dostępny
            if (item.status_check) {
                const statusCheck = item.status_check;
                statusHtml += `<br/><span class="status-check" style="background-color: ${getColorCode(statusCheck.color)}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-top: 4px; display: inline-block;">${escapeHtml(statusCheck.status)}: ${escapeHtml(statusCheck.description)}</span>`;
            }
        } else if (item.status === 'failed') {
            stopCountdown(item.id);
            if (item.error) {
                statusHtml += `<br/><small style="color: #dc3545;">${item.error}</small>`;
            }
        } else {
            stopCountdown(item.id);
        }

        return `<tr data-id="${item.id}">
            <td>${escapeHtml(item.filename)}<br/><small>Dodano: ${item.created_at_formatted || '-'}</small></td>
            <td>${item.size_mb} MB</td>
            <td>${statusHtml}</td>
            ${preprocessHtml}
            <td class="downloads">${downloads}</td>
        </tr>`;
    }).join('');
}

function escapeHtml(value) {
    if (value === undefined || value === null) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getColorCode(colorName) {
    // Mapowanie nazw kolorów na kody hex
    const colorMap = {
        'biały': '#ffffff',
        'czarny': '#000000',
        'czerwony': '#dc3545',
        'zielony': '#28a745',
        'niebieski': '#007bff',
        'żółty': '#ffc107',
        'fioletowy': '#6f42c1',
        'różowy': '#e83e8c',
        'pomarańczowy': '#fd7e14',
        'brązowy': '#8b4513',
        'szary': '#6c757d',
        'cyjan': '#17a2b8',
        'magenta': '#e83e8c',
        'limonkowy': '#20c997',
        'malinowy': '#d63384',
        'indygo': '#6610f2'
    };
    
    // Jeśli kolor jest w mapie, zwróć kod hex
    if (colorMap[colorName.toLowerCase()]) {
        return colorMap[colorName.toLowerCase()];
    }
    
    // Jeśli kolor wygląda jak kod hex, zwróć go
    if (colorName.startsWith('#') && (colorName.length === 7 || colorName.length === 4)) {
        return colorName;
    }
    
    // Domyślnie czerwony dla błędów
    return '#dc3545';
}

// ====================================
// Tabs functionality
// ====================================

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            // Don't prevent default for link-type tabs (allow navigation)
            if (this.classList.contains('tab-link') || this.tagName === 'A') {
                return; // Let the link navigate normally
            }
            
            e.preventDefault();
            
            const tabId = this.getAttribute('data-tab') || this.getAttribute('onclick')?.match(/'([^']+)'/)?.[1];
            if (!tabId) return;
            
            // Remove active from all tabs and contents
            document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active to clicked tab
            this.classList.add('active');
            
            // Show corresponding content
            const content = document.getElementById('tab-' + tabId);
            if (content) {
                content.classList.add('active');
            }
        });
    });
}

// ====================================
// Prompt toggle functionality
// ====================================

function togglePrompt(number) {
    const body = document.getElementById('prompt-body-' + number);
    const icon = document.getElementById('toggle-icon-' + number);
    
    if (!body) return;
    
    if (body.classList.contains('open')) {
        body.classList.remove('open');
        if (icon) icon.textContent = '▼';
    } else {
        body.classList.add('open');
        if (icon) icon.textContent = '▲';
    }
}

function confirmDelete(number) {
    const formattedNum = number.toString().padStart(2, '0');
    if (confirm(`Czy na pewno chcesz usunąć prompt ${formattedNum}? Ta operacja jest nieodwracalna.`)) {
        document.getElementById('delete-form-' + number).submit();
    }
}

function confirmReload() {
    if (confirm('Czy na pewno chcesz przeładować ustawienia? Nowe wartości zostaną zastosowane.')) {
        document.getElementById('reload-form').submit();
    }
}

// ====================================
// File input display
// ====================================

function initFileInput() {
    const fileInput = document.querySelector('input[type="file"]');
    const fileLabel = document.querySelector('.file-label-text');
    
    if (fileInput && fileLabel) {
        const originalText = fileLabel.textContent;
        
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                const names = Array.from(this.files).map(f => f.name).join(', ');
                fileLabel.textContent = `Wybrano: ${names}`;
            } else {
                fileLabel.textContent = originalText;
            }
        });
    }
}

// ====================================
// Checkbox label update
// ====================================

function initCheckboxLabels() {
    document.querySelectorAll('.checkbox-wrapper input[type="checkbox"]').forEach(checkbox => {
        const label = checkbox.nextElementSibling;
        if (label) {
            checkbox.addEventListener('change', function() {
                label.textContent = this.checked ? 'Włączone' : 'Wyłączone';
            });
        }
    });
}

// ====================================
// Initialize on page load
// ====================================

document.addEventListener('DOMContentLoaded', function() {
    initThemeToggle();
    initTabs();
    initFileInput();
    initCheckboxLabels();
    initChat();
    
    // Start queue refresh if on dashboard
    if (document.getElementById('queue-body')) {
        refreshQueue();
        setInterval(refreshQueue, 5000);
    }
});

// ====================================
// Chat functionality
// ====================================

let currentConversation = null;
let conversations = [];

async function loadConversations() {
    try {
        const response = await fetch('/api/chat/conversations');
        if (!response.ok) throw new Error('Failed to load conversations');
        const data = await response.json();
        conversations = data.conversations || [];
        renderConversations();
    } catch (error) {
        console.error('Error loading conversations:', error);
        showToast('Błąd ładowania rozmów: ' + error.message, 'error');
    }
}

function renderConversations() {
    const listElement = document.getElementById('conversation-list');
    if (!listElement) return;
    
    if (conversations.length === 0) {
        listElement.innerHTML = `
            <div class="chat-conversation-placeholder">
                <p>Brak rozmów. Wybierz plik w kolejce, aby rozpocząć konwersację.</p>
            </div>
        `;
        return;
    }
    
    // Filter completed queue items for starting new conversations
    const completedItems = window.QUEUE_ITEMS?.filter(item => item.status === 'completed') || [];
    
    listElement.innerHTML = `
        ${conversations.map(conv => `
            <div class="chat-conversation-item ${currentConversation?.id === conv.id ? 'active' : ''}" 
                 data-id="${conv.id}" 
                 onclick="selectConversation('${conv.id}')">
                <div class="chat-conversation-title">${escapeHtml(conv.filename)}</div>
                <div class="chat-conversation-meta">
                    <span class="chat-conversation-date">${formatDate(conv.updated_at)}</span>
                    <span class="chat-conversation-messages">${conv.message_count} wiad.</span>
                </div>
            </div>
        `).join('')}
        
        ${(completedItems.length > 0) ? `
            <div class="chat-section-header">Rozpocznij nową rozmowę</div>
            ${completedItems.map(item => `
                <div class="chat-queue-item" data-queue-id="${item.id}">
                    <div class="chat-queue-title">${escapeHtml(item.filename)}</div>
                    <button class="btn btn-small btn-primary" 
                            onclick="startConversation('${item.id}')">
                        Rozpocznij czat
                    </button>
                </div>
            `).join('')}
        ` : ''}
    `;
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) return 'dzisiaj';
    if (diffDays === 2) return 'wczoraj';
    if (diffDays <= 7) return `${diffDays - 1} dni temu`;
    
    return date.toLocaleDateString('pl-PL');
}

async function startConversation(queueId) {
    try {
        const response = await fetch('/api/chat/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ queue_id: queueId })
        });
        
        if (!response.ok) throw new Error('Failed to start conversation');
        
        const data = await response.json();
        
        // Add to conversations list
        conversations.unshift(data.conversation);
        
        // Select the new conversation
        await selectConversation(data.conversation.id);
        
        // Refresh the conversation list
        renderConversations();
        
        showToast('Rozmowa rozpoczęta pomyślnie', 'success');
    } catch (error) {
        console.error('Error starting conversation:', error);
        showToast('Błąd rozpoczęcia rozmowy: ' + error.message, 'error');
    }
}

async function selectConversation(conversationId) {
    try {
        const response = await fetch(`/api/chat/conversation/${conversationId}`);
        if (!response.ok) throw new Error('Failed to load conversation');
        
        const data = await response.json();
        currentConversation = data.conversation;
        
        // Update UI
        updateConversationUI();
        renderMessages();
        renderConversations(); // Update active state
        
        // Enable chat input
        const textarea = document.querySelector('#chat-composer textarea');
        const sendButton = document.querySelector('#chat-composer button[type="submit"]');
        if (textarea && sendButton) {
            textarea.disabled = false;
            sendButton.disabled = false;
            textarea.placeholder = 'Napisz wiadomość do Agenta...';
        }
    } catch (error) {
        console.error('Error selecting conversation:', error);
        showToast('Błąd ładowania rozmowy: ' + error.message, 'error');
    }
}

function updateConversationUI() {
    if (!currentConversation) return;
    
    // Update title
    const titleElement = document.getElementById('chat-selected-title');
    if (titleElement) {
        titleElement.textContent = currentConversation.filename;
    }
    
    // Update meta
    const metaElement = document.getElementById('selected-conversation-meta');
    if (metaElement) {
        metaElement.innerHTML = `
            <strong>${escapeHtml(currentConversation.filename)}</strong>
            <p>Rozmowa z ${formatDate(currentConversation.created_at)}</p>
        `;
    }
}

function renderMessages() {
    const historyElement = document.getElementById('chat-history');
    if (!historyElement) return;
    
    if (!currentConversation || !currentConversation.messages) {
        historyElement.innerHTML = `
            <div class="chat-empty-state">
                <h4>Wybierz transkrypcję aby rozpocząć</h4>
                <p>Po lewej stronie znajdziesz listę ukończonych zadań. Wybierz interesującą konwersację lub rozpocznij nową, aby zadać pytania modelowi.</p>
                <ul>
                    <li>Pytaj o kontekst rozmowy (np. „co było podstawą włączenia alarmu?”).</li>
                    <li>Dodawaj pliki porównawcze, aby zweryfikować zgodność treści.</li>
                    <li>Proś o streszczenia, analizę sentymentu, listy zadań.</li>
                </ul>
            </div>
        `;
        return;
    }
    
    if (currentConversation.messages.length === 0) {
        historyElement.innerHTML = `
            <div class="chat-welcome">
                <h4>Witaj w rozmowie o „${escapeHtml(currentConversation.filename)}”</h4>
                <p>Możesz zadać pytania dotyczące tej transkrypcji i analizy. Na przykład:</p>
                <ul>
                    <li>Co było podstawą włączenia alarmu?</li>
                    <li>Jakie nazwiska osób padają w rozmowie?</li>
                    <li>Czy rozmowa miała charakter oficjalny?</li>
                </ul>
            </div>
        `;
        return;
    }
    
    historyElement.innerHTML = `
        <div class="chat-messages">
            ${currentConversation.messages.map(msg => `
                <div class="chat-message ${msg.role}">
                    <div class="chat-message-content">
                        ${escapeHtml(msg.content).replace(/\n/g, '<br>')}
                    </div>
                    <div class="chat-message-meta">
                        ${formatTime(msg.created_at)}
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    
    // Scroll to bottom
    historyElement.scrollTop = historyElement.scrollHeight;
}

function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('pl-PL', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

async function sendMessage() {
    if (!currentConversation) return;
    
    const textarea = document.querySelector('#chat-composer textarea');
    if (!textarea) return;
    
    const message = textarea.value.trim();
    if (!message) return;
    
    // Disable input during sending
    textarea.disabled = true;
    const sendButton = document.querySelector('#chat-composer button[type="submit"]');
    if (sendButton) sendButton.disabled = true;
    
    const originalValue = textarea.value;
    textarea.value = '';
    
    try {
        const response = await fetch('/api/chat/message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                conversation_id: currentConversation.id,
                message: message
            })
        });
        
        if (!response.ok) throw new Error('Failed to send message');
        
        const data = await response.json();
        
        // Add messages to current conversation
        if (data.user_message) {
            currentConversation.messages.push(data.user_message);
        }
        if (data.assistant_message) {
            currentConversation.messages.push(data.assistant_message);
        }
        
        // Update UI
        renderMessages();
        
        // Update conversation in list
        const convIndex = conversations.findIndex(c => c.id === currentConversation.id);
        if (convIndex !== -1) {
            conversations[convIndex] = {
                ...conversations[convIndex],
                updated_at: new Date().toISOString(),
                message_count: currentConversation.messages.length
            };
            renderConversations();
        }
    } catch (error) {
        console.error('Error sending message:', error);
        textarea.value = originalValue; // Restore message
        showToast('Błąd wysyłania wiadomości: ' + error.message, 'error');
    } finally {
        // Re-enable input
        textarea.disabled = false;
        if (sendButton) sendButton.disabled = false;
        textarea.focus();
    }
}

function initChat() {
    // Set up chat form submission
    const chatForm = document.getElementById('chat-composer');
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            sendMessage();
        });
    }
    
    // Load conversations when chat tab is active
    document.addEventListener('click', function(e) {
        if (e.target.closest('[data-tab="chat"]')) {
            setTimeout(loadConversations, 100);
        }
    });
}

// Make functions globally available
window.togglePrompt = togglePrompt;
window.confirmDelete = confirmDelete;
window.confirmReload = confirmReload;
window.showToast = showToast;
window.selectConversation = selectConversation;
window.startConversation = startConversation;
