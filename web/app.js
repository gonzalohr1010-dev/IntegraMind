// INTEGRA MIND ENERGY - CORPORATE INTERACTIVITY

document.addEventListener('DOMContentLoaded', () => {
    // 0. THEME MANAGEMENT
    const initTheme = () => {
        // Check for saved theme preference or default to light
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
    };

    const toggleTheme = () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    };

    // Initialize theme on page load
    initTheme();

    // Theme toggle button
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }

    // 1. NOTIFICATION SYSTEM
    const notificationBell = document.getElementById('notification-bell');
    const notificationDropdown = document.getElementById('notification-dropdown');
    const notificationList = document.getElementById('notification-list');
    const notificationCount = document.getElementById('notification-count');
    const markAllReadBtn = document.getElementById('mark-all-read');

    let notifications = [];
    let unreadCount = 0;

    // Toggle notification dropdown
    if (notificationBell) {
        notificationBell.addEventListener('click', (e) => {
            e.stopPropagation();
            notificationDropdown.classList.toggle('show');
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.notification-container')) {
            notificationDropdown?.classList.remove('show');
        }
    });

    // Add notification function
    function addNotification(type, title, message, autoClose = false) {
        const notification = {
            id: Date.now(),
            type: type, // 'info', 'success', 'warning', 'error'
            title: title,
            message: message,
            time: new Date(),
            read: false
        };

        notifications.unshift(notification);
        unreadCount++;
        updateNotificationUI();

        // Show bell animation
        notificationBell?.classList.add('has-notifications');
        setTimeout(() => notificationBell?.classList.remove('has-notifications'), 2000);

        // Auto-close after 5 seconds if specified
        if (autoClose) {
            setTimeout(() => {
                markAsRead(notification.id);
            }, 5000);
        }

        return notification.id;
    }

    // Update notification UI
    function updateNotificationUI() {
        // Update badge
        if (unreadCount > 0) {
            notificationCount.textContent = unreadCount > 99 ? '99+' : unreadCount;
            notificationCount.classList.add('show');
        } else {
            notificationCount.classList.remove('show');
        }

        // Update list
        if (notifications.length === 0) {
            notificationList.innerHTML = `
                <div class="notification-empty">
                    <span style="font-size: 3rem;">📭</span>
                    <p>No hay notificaciones nuevas</p>
                </div>
            `;
        } else {
            notificationList.innerHTML = notifications.map(notif => {
                const icon = getNotificationIcon(notif.type);
                const timeAgo = getTimeAgo(notif.time);

                return `
                    <div class="notification-item ${notif.type} ${notif.read ? '' : 'unread'}" data-id="${notif.id}">
                        <div class="notification-item-content">
                            <div class="notification-icon">${icon}</div>
                            <div class="notification-text">
                                <div class="notification-title">${notif.title}</div>
                                <div class="notification-message">${notif.message}</div>
                                <div class="notification-time">${timeAgo}</div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');

            // Add click handlers to notification items
            document.querySelectorAll('.notification-item').forEach(item => {
                item.addEventListener('click', () => {
                    const id = parseInt(item.dataset.id);
                    markAsRead(id);
                });
            });
        }
    }

    // Get notification icon
    function getNotificationIcon(type) {
        const icons = {
            info: 'ℹ️',
            success: '✅',
            warning: '⚠️',
            error: '❌'
        };
        return icons[type] || icons.info;
    }

    // Get time ago string
    function getTimeAgo(date) {
        const seconds = Math.floor((new Date() - date) / 1000);

        if (seconds < 60) return 'Hace un momento';
        if (seconds < 3600) return `Hace ${Math.floor(seconds / 60)} min`;
        if (seconds < 86400) return `Hace ${Math.floor(seconds / 3600)} h`;
        return `Hace ${Math.floor(seconds / 86400)} días`;
    }

    // Mark notification as read
    function markAsRead(id) {
        const notification = notifications.find(n => n.id === id);
        if (notification && !notification.read) {
            notification.read = true;
            unreadCount--;
            updateNotificationUI();
        }
    }

    // Mark all as read
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', () => {
            notifications.forEach(n => n.read = true);
            unreadCount = 0;
            updateNotificationUI();
        });
    }

    // Expose addNotification globally for demo purposes
    window.addNotification = addNotification;

    // Demo: Add some sample notifications after 2 seconds
    setTimeout(() => {
        addNotification('success', 'Sistema Iniciado', 'El dashboard se ha cargado correctamente', true);

        setTimeout(() => {
            addNotification('info', 'Predicción Actualizada', 'Nueva predicción de demanda disponible para las próximas 24h');
        }, 3000);

        setTimeout(() => {
            addNotification('warning', 'Mantenimiento Programado', 'El transformador T-04 requiere inspección en 48 horas');
        }, 6000);
    }, 2000);

    // 2. SCROLL REVEAL ANIMATION
    const observerOptions = {
        threshold: 0.1,
        rootMargin: "0px"
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');

                // If it's a number, start counting
                if (entry.target.classList.contains('stat-item') || entry.target.querySelector('.stat-number')) {
                    const numElement = entry.target.querySelector('.stat-number') || entry.target;
                    startCounting(numElement);
                }
            }
        });
    }, observerOptions);

    document.querySelectorAll('.fade-in').forEach(el => {
        observer.observe(el);
    });

    // 2. NUMBER COUNTER ANIMATION
    function startCounting(element) {
        if (element.dataset.counting === "true") return; // Prevent double count
        element.dataset.counting = "true";

        const target = parseFloat(element.dataset.target);
        const isMoney = element.textContent.includes('$');
        const isPercent = element.nextElementSibling && element.nextElementSibling.textContent.includes('ROI') || element.textContent.includes('%') || element.dataset.target.includes('.');

        let start = 0;
        const duration = 2000; // 2 seconds
        const startTime = performance.now();

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function (easeOutExpo)
            const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);

            const current = start + (target - start) * ease;

            if (isMoney) {
                element.textContent = '$' + Math.floor(current).toLocaleString();
            } else if (target % 1 !== 0) { // Decimal
                element.textContent = current.toFixed(1) + '%';
            } else {
                element.textContent = Math.floor(current).toLocaleString() + '%';
            }

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                // Final fix to ensure exact number
                if (isMoney) element.textContent = '$' + target.toLocaleString();
                else if (target % 1 !== 0) element.textContent = target + '%';
                else element.textContent = target.toLocaleString() + '%';
            }
        }

        requestAnimationFrame(update);
    }

    // 3. CONTACT FORM HANDLING
    const leadForm = document.getElementById('leadForm');
    if (leadForm) {
        leadForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const btn = leadForm.querySelector('button');
            const originalText = btn.innerText;
            btn.innerText = "ENVIANDO...";
            btn.disabled = true;

            const formData = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                company: document.getElementById('company').value,
                role: document.getElementById('role').value,
                interest: document.getElementById('interest').value
            };

            try {
                // Determine API URL (dynamic check)
                const apiUrl = window.location.hostname === 'localhost' || window.location.protocol === 'file:'
                    ? 'http://localhost:8000/api/register-lead'
                    : '/api/register-lead'; // Relative for production

                const response = await fetch(apiUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();

                if (response.ok) {
                    leadForm.style.display = 'none';
                    document.getElementById('formSuccess').style.display = 'block';
                } else {
                    alert('Error: ' + (data.error || 'No se pudo enviar'));
                    btn.innerText = originalText;
                    btn.disabled = false;
                }
            } catch (error) {
                console.error('Error submitting form:', error);
                alert('Error de conexión con el servidor. Asegúrate de que la API esté corriendo en el puerto 8000.');
                btn.innerText = originalText;
                btn.disabled = false;
            }
        });
    }

    // 4. FAQ ACCORDION
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach(item => {
        item.addEventListener('click', () => {
            const answer = item.querySelector('.faq-answer');
            const icon = item.querySelector('span:last-child');

            // Toggle current item
            if (answer.style.display === 'block') {
                answer.style.display = 'none';
                icon.textContent = '+';
            } else {
                // Close all other FAQs
                faqItems.forEach(otherItem => {
                    const otherAnswer = otherItem.querySelector('.faq-answer');
                    const otherIcon = otherItem.querySelector('span:last-child');
                    otherAnswer.style.display = 'none';
                    otherIcon.textContent = '+';
                });

                // Open clicked item
                answer.style.display = 'block';
                icon.textContent = '−';
            }
        });
    });

    // 5. SMOOTH SCROLL FOR ANCHOR LINKS
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href !== '#' && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });

    // 6. LAZY LOADING FOR IMAGES
    const lazyImages = document.querySelectorAll('img[data-src]');
    if (lazyImages.length > 0) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    img.classList.add('loaded');
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: '50px'
        });

        lazyImages.forEach(img => imageObserver.observe(img));
    }

    // 7. PERFORMANCE: Debounce scroll events
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (scrollTimeout) {
            window.cancelAnimationFrame(scrollTimeout);
        }
        scrollTimeout = window.requestAnimationFrame(() => {
            // Scroll-dependent operations here
        });
    }, { passive: true });
});
