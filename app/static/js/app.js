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
        // Usuń wszystkie warianty kolorystyczne
        clearColorSchemes();
        
        if (this.checked) {
            document.body.classList.add('dark-mode');
            localStorage.setItem('gacek-theme', 'dark');
            showThemeMessage('Tryb ciemny włączony');
        } else {
            document.body.classList.remove('dark-mode');
            localStorage.setItem('gacek-theme', 'light');
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
    // W trybie jasnym pokazuj księżyc (przejście do ciemnego)
    // W trybie ciemnym pokazuj słoneczko (przejście do jasnego)
    icon.textContent = isDark ? '☀️' : '🌙';
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
        queueBody.innerHTML = '<tr class="queue-empty"><td colspan="4">Brak zadań w kolejce.</td></tr>';
        return;
    }
    
    queueBody.innerHTML = items.map(item => {
        const downloads = item.status === 'completed'
            ? `<a href="/download/${item.id}/transcription">📄 Transkrypcja</a>
               <a href="/download/${item.id}/analysis">📊 Analiza</a>`
            : '<small>–</small>';
        
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

// ====================================
// Tabs functionality
// ====================================

function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
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

function confirmRestart() {
    if (confirm('Czy na pewno chcesz zrestartować system? Wszystkie niezapisane zmiany zostaną utracone.')) {
        document.getElementById('restart-form').submit();
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
    
    // Start queue refresh if on dashboard
    if (document.getElementById('queue-body')) {
        refreshQueue();
        setInterval(refreshQueue, 5000);
    }
});

// Make functions globally available
window.togglePrompt = togglePrompt;
window.confirmDelete = confirmDelete;
window.confirmRestart = confirmRestart;
window.showToast = showToast;
