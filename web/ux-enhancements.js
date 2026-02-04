/**
 * UX ENHANCEMENTS - Integra Mind
 * Advanced user experience components
 */

// ========================================
// COMMAND PALETTE (Ctrl+K)
// ========================================

class CommandPalette {
    constructor() {
        this.isOpen = false;
        this.selectedIndex = 0;
        this.commands = [
            {
                category: 'Navigation',
                items: [
                    { icon: '🤖', title: 'Open Assistant', description: 'AI chat interface', action: () => this.navigateTo('chat-section') },
                    { icon: '💰', title: 'Open Finance', description: 'Financial dashboard', action: () => this.navigateTo('finance-section') },
                    { icon: '📦', title: 'Open Inventory', description: 'Stock management', action: () => this.navigateTo('inventory-section') },
                    { icon: '⚙️', title: 'Open Settings', description: 'System preferences', action: () => this.navigateTo('settings-section') }
                ]
            },
            {
                category: 'Actions',
                items: [
                    { icon: '📊', title: 'Export Data', description: 'Download reports', action: () => this.exportData() },
                    { icon: '🔄', title: 'Refresh Dashboard', description: 'Reload all data', action: () => this.refreshDashboard() },
                    { icon: '🌓', title: 'Toggle Theme', description: 'Switch light/dark mode', action: () => this.toggleTheme() },
                    { icon: '🗑️', title: 'Clear Chat', description: 'Reset conversation', action: () => this.clearChat() }
                ]
            },
            {
                category: 'Data',
                items: [
                    { icon: '💵', title: 'View Transactions', description: 'Recent financial activity', action: () => this.viewTransactions() },
                    { icon: '📈', title: 'View Forecast', description: 'AI predictions', action: () => this.viewForecast() },
                    { icon: '🔍', title: 'Search Everything', description: 'Global search', action: () => this.globalSearch() }
                ]
            }
        ];
        this.filteredCommands = this.commands;
        this.init();
    }

    init() {
        this.createUI();
        this.attachEventListeners();
    }

    createUI() {
        const overlay = document.createElement('div');
        overlay.className = 'command-palette-overlay';
        overlay.id = 'command-palette-overlay';
        overlay.innerHTML = `
            <div class="command-palette">
                <input 
                    type="text" 
                    class="command-palette-input" 
                    id="command-input"
                    placeholder="Type a command or search..."
                    autocomplete="off"
                />
                <div class="command-results" id="command-results"></div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.close();
        });
    }

    attachEventListeners() {
        // Ctrl+K to open
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.toggle();
            }
            
            if (this.isOpen) {
                if (e.key === 'Escape') {
                    this.close();
                } else if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    this.selectNext();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    this.selectPrevious();
                } else if (e.key === 'Enter') {
                    e.preventDefault();
                    this.executeSelected();
                }
            }
        });

        const input = document.getElementById('command-input');
        if (input) {
            input.addEventListener('input', (e) => {
                this.filter(e.target.value);
            });
        }
    }

    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    open() {
        this.isOpen = true;
        const overlay = document.getElementById('command-palette-overlay');
        overlay.classList.add('active');
        const input = document.getElementById('command-input');
        setTimeout(() => input.focus(), 100);
        this.render();
    }

    close() {
        this.isOpen = false;
        const overlay = document.getElementById('command-palette-overlay');
        overlay.classList.remove('active');
        const input = document.getElementById('command-input');
        input.value = '';
        this.filteredCommands = this.commands;
        this.selectedIndex = 0;
    }

    filter(query) {
        if (!query.trim()) {
            this.filteredCommands = this.commands;
        } else {
            const lowerQuery = query.toLowerCase();
            this.filteredCommands = this.commands.map(category => ({
                category: category.category,
                items: category.items.filter(item =>
                    item.title.toLowerCase().includes(lowerQuery) ||
                    item.description.toLowerCase().includes(lowerQuery)
                )
            })).filter(category => category.items.length > 0);
        }
        this.selectedIndex = 0;
        this.render();
    }

    render() {
        const results = document.getElementById('command-results');
        let html = '';
        let globalIndex = 0;

        this.filteredCommands.forEach(category => {
            if (category.items.length > 0) {
                html += `<div class="command-category">${category.category}</div>`;
                category.items.forEach(item => {
                    const isSelected = globalIndex === this.selectedIndex;
                    html += `
                        <div class="command-item ${isSelected ? 'selected' : ''}" data-index="${globalIndex}">
                            <span class="command-icon">${item.icon}</span>
                            <div class="command-content">
                                <div class="command-title">${item.title}</div>
                                <div class="command-description">${item.description}</div>
                            </div>
                        </div>
                    `;
                    globalIndex++;
                });
            }
        });

        results.innerHTML = html;

        // Add click handlers
        results.querySelectorAll('.command-item').forEach(item => {
            item.addEventListener('click', () => {
                const index = parseInt(item.dataset.index);
                this.selectedIndex = index;
                this.executeSelected();
            });
        });
    }

    selectNext() {
        const totalItems = this.filteredCommands.reduce((sum, cat) => sum + cat.items.length, 0);
        this.selectedIndex = (this.selectedIndex + 1) % totalItems;
        this.render();
    }

    selectPrevious() {
        const totalItems = this.filteredCommands.reduce((sum, cat) => sum + cat.items.length, 0);
        this.selectedIndex = (this.selectedIndex - 1 + totalItems) % totalItems;
        this.render();
    }

    executeSelected() {
        let globalIndex = 0;
        for (const category of this.filteredCommands) {
            for (const item of category.items) {
                if (globalIndex === this.selectedIndex) {
                    item.action();
                    this.close();
                    return;
                }
                globalIndex++;
            }
        }
    }

    // Action methods
    navigateTo(sectionId) {
        const section = document.getElementById(sectionId);
        if (section) {
            document.querySelectorAll('section').forEach(s => s.classList.add('hidden-section'));
            section.classList.remove('hidden-section');
            
            document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
            const navItem = document.querySelector(`[data-target="${sectionId}"]`);
            if (navItem) navItem.classList.add('active');
        }
    }

    exportData() {
        showNotification('Export started', 'Your data is being prepared...', 'success');
        // Trigger export logic
    }

    refreshDashboard() {
        showNotification('Refreshing...', 'Loading latest data', 'success');
        if (typeof loadFinanceDashboard === 'function') {
            loadFinanceDashboard();
        }
    }

    toggleTheme() {
        const themeBtn = document.getElementById('theme-toggle-btn');
        if (themeBtn) themeBtn.click();
    }

    clearChat() {
        const clearBtn = document.getElementById('btn-clear-chat');
        if (clearBtn) clearBtn.click();
    }

    viewTransactions() {
        this.navigateTo('finance-section');
        showNotification('Transactions', 'Viewing recent activity', 'success');
    }

    viewForecast() {
        this.navigateTo('finance-section');
        showNotification('Forecast', 'Loading AI predictions', 'success');
    }

    globalSearch() {
        showNotification('Search', 'Global search coming soon', 'warning');
    }
}

// ========================================
// INSIGHTS PANEL
// ========================================

class InsightsPanel {
    constructor() {
        this.insights = [];
        this.isOpen = false;
        this.init();
    }

    init() {
        this.createUI();
        this.generateInsights();
    }

    createUI() {
        const panel = document.createElement('div');
        panel.className = 'insights-panel';
        panel.id = 'insights-panel';
        panel.innerHTML = `
            <div class="insights-header">
                <h3>💡 Smart Insights</h3>
                <button class="icon-btn" onclick="insightsPanel.toggle()">✕</button>
            </div>
            <div class="insights-content" id="insights-content"></div>
        `;
        document.body.appendChild(panel);
    }

    toggle() {
        this.isOpen = !this.isOpen;
        const panel = document.getElementById('insights-panel');
        panel.classList.toggle('active', this.isOpen);
    }

    addInsight(insight) {
        this.insights.unshift(insight);
        this.render();
    }

    generateInsights() {
        // Example insights - these would be generated from real data
        const sampleInsights = [
            {
                type: 'success',
                icon: '📈',
                title: 'Revenue Growth',
                description: 'Your revenue increased by 15% compared to last month. Great work!',
                time: 'Just now',
                action: 'View Details'
            },
            {
                type: 'warning',
                icon: '⚠️',
                title: 'High Expenses',
                description: 'Operational costs are 20% above average this week.',
                time: '5 minutes ago',
                action: 'Review Expenses'
            },
            {
                type: 'info',
                icon: '🎯',
                title: 'Goal Progress',
                description: 'You\'re 75% towards your monthly target. Keep going!',
                time: '1 hour ago',
                action: 'Track Progress'
            }
        ];

        this.insights = sampleInsights;
        this.render();
    }

    render() {
        const content = document.getElementById('insights-content');
        if (!content) return;

        content.innerHTML = this.insights.map(insight => `
            <div class="insight-card ${insight.type}">
                <div class="insight-icon">${insight.icon}</div>
                <div class="insight-title">${insight.title}</div>
                <div class="insight-description">${insight.description}</div>
                <div class="insight-time">${insight.time}</div>
                ${insight.action ? `<button class="insight-action">${insight.action}</button>` : ''}
            </div>
        `).join('');
    }
}

// ========================================
// NOTIFICATION SYSTEM
// ========================================

function showNotification(title, message, type = 'info') {
    const container = document.getElementById('notification-container') || createNotificationContainer();
    
    const toast = document.createElement('div');
    toast.className = `notification-toast ${type}`;
    
    const icons = {
        success: '✅',
        warning: '⚠️',
        error: '❌',
        info: 'ℹ️'
    };
    
    toast.innerHTML = `
        <span class="notification-icon">${icons[type]}</span>
        <div class="notification-content">
            <div class="notification-title">${title}</div>
            <div class="notification-message">${message}</div>
        </div>
        <button class="notification-close" onclick="this.parentElement.remove()">✕</button>
    `;
    
    container.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideInUp 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.className = 'notification-container';
    container.id = 'notification-container';
    document.body.appendChild(container);
    return container;
}

// ========================================
// KEYBOARD SHORTCUTS
// ========================================

class KeyboardShortcuts {
    constructor() {
        this.shortcuts = {
            'ctrl+1': () => this.navigateTo('chat-section'),
            'ctrl+2': () => this.navigateTo('finance-section'),
            'ctrl+3': () => this.navigateTo('inventory-section'),
            'ctrl+4': () => this.navigateTo('settings-section'),
            'ctrl+i': () => insightsPanel.toggle(),
            'ctrl+shift+r': () => location.reload()
        };
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => {
            const key = this.getKeyCombo(e);
            if (this.shortcuts[key]) {
                e.preventDefault();
                this.shortcuts[key]();
            }
        });
    }

    getKeyCombo(e) {
        const parts = [];
        if (e.ctrlKey || e.metaKey) parts.push('ctrl');
        if (e.shiftKey) parts.push('shift');
        if (e.altKey) parts.push('alt');
        if (e.key && e.key.length === 1) parts.push(e.key.toLowerCase());
        return parts.join('+');
    }

    navigateTo(sectionId) {
        const section = document.getElementById(sectionId);
        if (section) {
            document.querySelectorAll('section').forEach(s => s.classList.add('hidden-section'));
            section.classList.remove('hidden-section');
            
            document.querySelectorAll('.nav-links li').forEach(li => li.classList.remove('active'));
            const navItem = document.querySelector(`[data-target="${sectionId}"]`);
            if (navItem) navItem.classList.add('active');
        }
    }
}

// ========================================
// INITIALIZE ALL COMPONENTS
// ========================================

let commandPalette, insightsPanel, keyboardShortcuts;

document.addEventListener('DOMContentLoaded', () => {
    // Initialize UX components
    commandPalette = new CommandPalette();
    insightsPanel = new InsightsPanel();
    keyboardShortcuts = new KeyboardShortcuts();
    
    // Show welcome notification
    setTimeout(() => {
        showNotification(
            'Welcome to Integra Mind',
            'Press Ctrl+K for quick commands, Ctrl+I for insights',
            'success'
        );
    }, 1000);
    
    // Auto-open insights panel after 3 seconds
    setTimeout(() => {
        insightsPanel.toggle();
    }, 3000);
});
