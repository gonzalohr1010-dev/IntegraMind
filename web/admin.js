/**
 * 🔐 INTEGRA MIND - ADMIN PANEL JAVASCRIPT
 * ⚠️ ACCESO RESTRINGIDO - SOLO ADMINISTRADOR AUTORIZADO
 * Sistema de administración con autenticación JWT y protección máxima
 */

// ============================================
// PROTECCIÓN ANTI-TAMPERING
// ============================================
(function () {
    'use strict';

    // Deshabilitar DevTools (dificulta inspección)
    const devtools = /./;
    devtools.toString = function () {
        this.opened = true;
    };

    const checkDevTools = setInterval(() => {
        if (devtools.opened) {
            alert('⚠️ ACCESO DENEGADO: Herramientas de desarrollador detectadas');
            window.location.href = '/';
        }
    }, 1000);

    // Deshabilitar clic derecho
    document.addEventListener('contextmenu', e => e.preventDefault());

    // Deshabilitar teclas de acceso rápido
    document.addEventListener('keydown', e => {
        // F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+U
        if (e.keyCode === 123 ||
            (e.ctrlKey && e.shiftKey && (e.keyCode === 73 || e.keyCode === 74)) ||
            (e.ctrlKey && e.keyCode === 85)) {
            e.preventDefault();
            return false;
        }
    });
})();

// Configuración
const API_BASE = '/api';
const LEGACY_API = '/api/admin';

// Configuración de seguridad
const SECURITY_CONFIG = {
    SESSION_TIMEOUT: 15 * 60 * 1000, // 15 minutos de inactividad
    MAX_LOGIN_ATTEMPTS: 3,
    LOCKOUT_DURATION: 30 * 60 * 1000, // 30 minutos de bloqueo
    REQUIRE_IP_VERIFICATION: false // Cambiar a true para verificar IP
};

// Estado global
let authToken = null;
let currentUser = null;
let refreshInterval = null;
let sessionTimeout = null;
let lastActivity = Date.now();
let loginAttempts = 0;
let lockoutUntil = null;

// ============================================
// PROTECCIÓN DE SESIÓN
// ============================================

function initSessionProtection() {
    // Detectar inactividad
    const resetTimer = () => {
        lastActivity = Date.now();
        if (sessionTimeout) clearTimeout(sessionTimeout);

        sessionTimeout = setTimeout(() => {
            if (authToken) {
                alert('⚠️ Sesión expirada por inactividad');
                forceLogout();
            }
        }, SECURITY_CONFIG.SESSION_TIMEOUT);
    };

    // Eventos de actividad
    ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'].forEach(event => {
        document.addEventListener(event, resetTimer, true);
    });

    // Detectar cambio de pestaña
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && authToken) {
            console.warn('⚠️ Usuario cambió de pestaña');
        }
    });

    // Detectar cierre de ventana
    window.addEventListener('beforeunload', (e) => {
        if (authToken) {
            // Limpiar sesión al cerrar
            sessionStorage.clear();
        }
    });
}

function forceLogout() {
    sessionStorage.clear();
    localStorage.clear();
    authToken = null;
    currentUser = null;
    if (refreshInterval) clearInterval(refreshInterval);
    if (sessionTimeout) clearTimeout(sessionTimeout);

    // Redirigir a página principal
    window.location.href = '/';
}

// ============================================
// VERIFICACIÓN DE ACCESO
// ============================================

function checkLockout() {
    if (lockoutUntil && Date.now() < lockoutUntil) {
        const remainingMinutes = Math.ceil((lockoutUntil - Date.now()) / 60000);
        showError(`🔒 Cuenta bloqueada. Intenta de nuevo en ${remainingMinutes} minutos.`);
        return true;
    }
    return false;
}

function recordFailedAttempt() {
    loginAttempts++;

    if (loginAttempts >= SECURITY_CONFIG.MAX_LOGIN_ATTEMPTS) {
        lockoutUntil = Date.now() + SECURITY_CONFIG.LOCKOUT_DURATION;
        localStorage.setItem('lockoutUntil', lockoutUntil.toString());
        showError(`🔒 Demasiados intentos fallidos. Cuenta bloqueada por 30 minutos.`);

        // Deshabilitar formulario
        document.getElementById('adminUsername').disabled = true;
        document.getElementById('adminPassword').disabled = true;
        document.querySelector('.login-btn').disabled = true;
    }
}

function resetLoginAttempts() {
    loginAttempts = 0;
    lockoutUntil = null;
    localStorage.removeItem('lockoutUntil');
}

// ============================================
// AUTENTICACIÓN
// ============================================

// Permitir login con Enter
document.getElementById('adminPassword').addEventListener('keypress', function (e) {
    if (e.key === 'Enter') attemptLogin();
});

async function attemptLogin() {
    // Verificar bloqueo
    if (checkLockout()) return;

    let username = document.getElementById('adminUsername').value.trim();
    const password = document.getElementById('adminPassword').value;
    const errorMsg = document.getElementById('loginError');
    const btn = document.querySelector('.login-btn');

    // Permitir acceso Legacy solo con contraseña (asumir usuario 'admin')
    if (!username && password) {
        username = 'admin';
    }

    if (!username || !password) {
        showError('Por favor ingrese usuario y contraseña');
        recordFailedAttempt();
        return;
    }

    errorMsg.style.display = 'none';
    btn.innerText = 'VERIFICANDO...';
    btn.disabled = true;

    try {
        // Intentar login con nuevo sistema JWT
        const response = await fetch(`${API_BASE}/security/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (response.ok) {
            const data = await response.json();
            authToken = data.access_token;
            currentUser = data.user;

            // Guardar en sessionStorage (MÁS SEGURO que localStorage)
            sessionStorage.setItem('authToken', authToken);
            sessionStorage.setItem('currentUser', JSON.stringify(currentUser));
            sessionStorage.setItem('loginTime', Date.now().toString());

            // Resetear intentos fallidos
            resetLoginAttempts();

            // Login exitoso
            unlockDashboard();
            loadAllData();
            startAutoRefresh();
            initSessionProtection(); // IMPORTANTE: Activar protección de sesión
        } else {
            // Si falla JWT, intentar con sistema legacy
            await attemptLegacyLogin(password);
        }
    } catch (error) {
        console.error('Error de conexión:', error);
        // Intentar sistema legacy como fallback
        await attemptLegacyLogin(password);
    } finally {
        btn.innerText = 'INGRESAR AL SISTEMA';
        btn.disabled = false;
    }
}

async function attemptLegacyLogin(password) {
    const errorMsg = document.getElementById('loginError');

    try {
        // Sistema legacy con X-Admin-Token
        const response = await fetch(`${LEGACY_API}/leads`, {
            headers: { 'X-Admin-Token': password }
        });

        if (response.ok) {
            authToken = password;
            currentUser = {
                username: 'admin',
                role: 'admin',
                email: 'admin@integramind.com'
            };

            sessionStorage.setItem('authToken', authToken);
            sessionStorage.setItem('currentUser', JSON.stringify(currentUser));
            sessionStorage.setItem('loginTime', Date.now().toString());

            // Resetear intentos fallidos
            resetLoginAttempts();

            unlockDashboard();
            loadAllData();
            startAutoRefresh();
            initSessionProtection(); // IMPORTANTE: Activar protección de sesión
        } else {
            showError('Credenciales incorrectas');
            recordFailedAttempt(); // Registrar intento fallido
        }
    } catch (error) {
        showError('Error de conexión. Verifica que el servidor esté corriendo.');
        recordFailedAttempt(); // Registrar intento fallido
    }
}

function unlockDashboard() {
    document.getElementById('loginOverlay').style.display = 'none';
    const content = document.getElementById('adminContent');

    // Forzar visibilidad inmediata
    content.style.display = 'block';

    // Pequeño timeout para permitir que el navegador procese el cambio de display antes de la opacidad
    setTimeout(() => {
        content.style.opacity = '1';
        content.style.filter = 'none';
        content.style.pointerEvents = 'all';
        content.classList.add('unlocked');
    }, 10);

    // Actualizar info de usuario
    if (currentUser) {
        document.getElementById('currentUsername').textContent = currentUser.username;
        document.getElementById('currentUserRole').textContent = currentUser.role ? currentUser.role.toUpperCase() : 'ADMIN';
    }

    console.log('✅ Dashboard desbloqueado y visible');
}

function logout() {
    if (confirm('¿Cerrar sesión?')) {
        sessionStorage.clear();
        authToken = null;
        currentUser = null;
        if (refreshInterval) clearInterval(refreshInterval);
        location.reload();
    }
}

function showError(message) {
    const errorMsg = document.getElementById('loginError');
    errorMsg.textContent = `❌ ${message}`;
    errorMsg.style.display = 'block';
    document.getElementById('adminPassword').value = '';
}

// ============================================
// GESTIÓN DE TABS
// ============================================

function switchTab(tabName) {
    // Actualizar botones
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    event.target.classList.add('active');

    // Actualizar contenido
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Cargar datos si es necesario
    switch (tabName) {
        case 'leads':
            loadLeads();
            break;
        case 'users':
            loadUsers();
            break;
        case 'files':
            loadFiles();
            break;
        case 'security':
            loadSecurityLogs();
            break;
    }
}

// ============================================
// CARGA DE DATOS
// ============================================

async function loadAllData() {
    loadLeads();
    loadStats();
}

function startAutoRefresh() {
    // Actualizar stats cada 30 segundos
    refreshInterval = setInterval(() => {
        loadStats();
    }, 30000);
}

async function loadStats() {
    try {
        // Total usuarios (si hay endpoint JWT)
        try {
            const usersRes = await fetchWithAuth(`${API_BASE}/security/users`);
            if (usersRes.ok) {
                const data = await usersRes.json();
                document.getElementById('totalUsers').textContent = data.total || 0;
            }
        } catch (e) {
            document.getElementById('totalUsers').textContent = '-';
        }

        // Total leads
        try {
            const leadsRes = await fetchWithAuth(`${LEGACY_API}/leads`);
            if (leadsRes.ok) {
                const leads = await leadsRes.json();
                document.getElementById('totalLeads').textContent = leads.length || 0;
            }
        } catch (e) {
            document.getElementById('totalLeads').textContent = '-';
        }

        // Total archivos (si hay endpoint)
        try {
            const filesRes = await fetchWithAuth(`${API_BASE}/security/files`);
            if (filesRes.ok) {
                const data = await filesRes.json();
                document.getElementById('totalFiles').textContent = data.files?.length || 0;
            }
        } catch (e) {
            document.getElementById('totalFiles').textContent = '-';
        }

        // Eventos de seguridad
        try {
            const logsRes = await fetchWithAuth(`${API_BASE}/security/logs/security?limit=100`);
            if (logsRes.ok) {
                const data = await logsRes.json();
                document.getElementById('securityEvents').textContent = data.total || 0;
            }
        } catch (e) {
            document.getElementById('securityEvents').textContent = '-';
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ============================================
// LEADS
// ============================================

async function loadLeads() {
    const tbody = document.getElementById('leadsTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div>Cargando leads...</td></tr>';

    try {
        const response = await fetchWithAuth(`${LEGACY_API}/leads`);

        if (response.ok) {
            const leads = await response.json();
            renderLeadsTable(leads);
        } else {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--admin-danger)">❌ Error al cargar leads</td></tr>';
        }
    } catch (error) {
        console.error('Error:', error);
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--admin-danger)">❌ Error de conexión</td></tr>';
    }
}

function renderLeadsTable(leads) {
    const tbody = document.getElementById('leadsTableBody');
    tbody.innerHTML = '';

    // Add bulk actions button if there are leads
    const tableContainer = tbody.closest('.admin-card');
    let bulkActionsDiv = tableContainer.querySelector('.bulk-actions');

    if (!bulkActionsDiv && leads.length > 0) {
        bulkActionsDiv = document.createElement('div');
        bulkActionsDiv.className = 'bulk-actions';
        bulkActionsDiv.style.cssText = 'margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center;';

        const pendingCount = leads.filter(l => !l.report_generated || !l.report_sent_at).length;

        bulkActionsDiv.innerHTML = `
            <div style="color: var(--admin-text-muted); font-size: 0.9em;">
                📊 Total: ${leads.length} leads | ⏳ Pendientes: ${pendingCount}
            </div>
            <button onclick="sendReportsToAll()" class="btn btn-primary" style="padding: 8px 16px;">
                📧 Enviar Reportes a Todos los Pendientes
            </button>
        `;

        tableContainer.querySelector('table').before(bulkActionsDiv);
    } else if (bulkActionsDiv && leads.length === 0) {
        bulkActionsDiv.remove();
    } else if (bulkActionsDiv) {
        // Update counts
        const pendingCount = leads.filter(l => !l.report_generated || !l.report_sent_at).length;
        bulkActionsDiv.querySelector('div').innerHTML = `📊 Total: ${leads.length} leads | ⏳ Pendientes: ${pendingCount}`;
    }

    if (leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">📭 No hay leads registrados</td></tr>';
        return;
    }

    leads.forEach(lead => {
        const date = new Date(lead.created_at).toLocaleString('es-ES', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        const role = lead.role ? `<br><span style="font-size:0.8em; color:var(--admin-text-muted)">${lead.role}</span>` : '';

        let badgeClass = 'badge-info';
        if (lead.interest === 'pilot') badgeClass = 'badge-pilot';
        if (lead.interest === 'demo') badgeClass = 'badge-demo';

        // Report status badge
        let reportStatusBadge = '';
        let buttonText = '📄 Generar Reporte';
        let buttonClass = 'btn btn-success btn-sm';

        if (lead.report_generated) {
            if (lead.report_sent_at) {
                // Report generated and sent
                reportStatusBadge = '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: var(--admin-success); border: 1px solid var(--admin-success); margin-left: 8px;">✅ Enviado</span>';
                buttonText = '🔄 Reenviar Reporte';
                buttonClass = 'btn btn-primary btn-sm';
            } else {
                // Report generated but not sent
                reportStatusBadge = '<span class="badge" style="background: rgba(251, 191, 36, 0.2); color: #f59e0b; border: 1px solid #f59e0b; margin-left: 8px;">📄 Generado</span>';
                buttonText = '📧 Enviar Reporte';
                buttonClass = 'btn btn-primary btn-sm';
            }
        } else {
            // Report not generated yet
            reportStatusBadge = '<span class="badge" style="background: rgba(148, 163, 184, 0.2); color: var(--admin-text-muted); border: 1px solid var(--admin-text-muted); margin-left: 8px;">⏳ Pendiente</span>';
        }

        const row = `
            <tr>
                <td style="color: var(--admin-text-muted); font-size: 0.9em;">${date}</td>
                <td style="font-weight: 600;">${lead.name || 'N/A'}</td>
                <td>${lead.company || 'N/A'} ${role}</td>
                <td><a href="mailto:${lead.email}" style="color: var(--admin-primary);">${lead.email}</a></td>
                <td><span class="badge ${badgeClass}">${(lead.interest || 'info').toUpperCase()}</span>${reportStatusBadge}</td>
                <td>
                    <button onclick="generateReport('${lead.name}', '${lead.company}', ${lead.id})" 
                        class="${buttonClass}">
                        ${buttonText}
                    </button>
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

async function generateReport(clientName, company, leadId) {
    const sendEmail = confirm(`¿Generar reporte para ${clientName}?\n\nSi aceptas, también se intentará enviar por email al cliente.`);

    const btn = event.target;
    btn.disabled = true;
    btn.innerText = '⏳ Generando...';

    try {
        const response = await fetch(`${LEGACY_API}/generate-report`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Admin-Token': authToken
            },
            body: JSON.stringify({
                client_name: clientName,
                industry: 'Energy & Utilities',
                lead_id: leadId,
                send_email: sendEmail
            })
        });

        const data = await response.json();

        if (response.ok) {
            let msg = `✅ ${data.message}\n\nArchivo: ${data.file_path}`;
            if (data.email_status) msg += `\nEstado Email: ${data.email_status}`;
            alert(msg);

            if (data.download_url) {
                window.open(`http://localhost:5001${data.download_url}`, '_blank');
            }
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ Error generando reporte. Verifica que el servidor esté corriendo.');
    } finally {
        btn.disabled = false;
        btn.innerText = '📄 Generar Reporte';
    }
}

// ============================================
// ENVÍO MASIVO DE REPORTES
// ============================================

async function sendReportsToAll() {
    if (!confirm('⚠️ ¿Estás seguro de que deseas generar y enviar reportes a TODOS los leads pendientes?\n\nEsto puede tomar varios minutos dependiendo de la cantidad de leads.')) {
        return;
    }

    const btn = event.target;
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = '⏳ Procesando...';

    try {
        const response = await fetchWithAuth(`${LEGACY_API}/send-all-reports`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (response.ok) {
            alert(`✅ Proceso completado!\n\n` +
                `📧 Enviados: ${result.sent}\n` +
                `⏭️ Omitidos (ya enviados): ${result.skipped}\n` +
                `❌ Errores: ${result.errors}\n` +
                `📊 Total procesados: ${result.total}`);

            // Recargar la tabla de leads para ver los estados actualizados
            loadLeads();
        } else {
            alert(`❌ Error: ${result.error || 'No se pudo completar el envío masivo'}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ Error de conexión al procesar envío masivo.');
    } finally {
        btn.disabled = false;
        btn.innerText = originalText;
    }
}

// ============================================
// USUARIOS
// ============================================

async function loadUsers() {
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="loading"><div class="spinner"></div>Cargando usuarios...</td></tr>';

    try {
        const response = await fetchWithAuth(`${API_BASE}/security/users`);

        if (response.ok) {
            const data = await response.json();
            renderUsersTable(data.users);
        } else {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">⚠️ No disponible (requiere autenticación JWT)</td></tr>';
        }
    } catch (error) {
        console.error('Error:', error);
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">⚠️ Función no disponible</td></tr>';
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('usersTableBody');
    tbody.innerHTML = '';

    if (!users || users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">👥 No hay usuarios registrados</td></tr>';
        return;
    }

    users.forEach(user => {
        const lastLogin = user.last_login
            ? new Date(user.last_login).toLocaleString('es-ES')
            : 'Nunca';

        const statusBadge = user.is_active
            ? '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: var(--admin-success); border: 1px solid var(--admin-success)">ACTIVO</span>'
            : '<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: var(--admin-danger); border: 1px solid var(--admin-danger)">INACTIVO</span>';

        const row = `
            <tr>
                <td>${user.id}</td>
                <td style="font-weight: 600;">${user.username}</td>
                <td>${user.email}</td>
                <td><span class="badge badge-pilot">${user.role.toUpperCase()}</span></td>
                <td>${user.company || 'N/A'}</td>
                <td style="color: var(--admin-text-muted); font-size: 0.9em;">${lastLogin}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// ============================================
// ARCHIVOS
// ============================================

async function loadFiles() {
    const tbody = document.getElementById('filesTableBody');
    tbody.innerHTML = '<tr><td colspan="7" class="loading"><div class="spinner"></div>Cargando archivos...</td></tr>';

    try {
        const response = await fetchWithAuth(`${API_BASE}/security/files`);

        if (response.ok) {
            const data = await response.json();
            renderFilesTable(data.files);
        } else {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">⚠️ No disponible (requiere autenticación JWT)</td></tr>';
        }
    } catch (error) {
        console.error('Error:', error);
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">⚠️ Función no disponible</td></tr>';
    }
}

function renderFilesTable(files) {
    const tbody = document.getElementById('filesTableBody');
    tbody.innerHTML = '';

    if (!files || files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">📁 No hay archivos subidos</td></tr>';
        return;
    }

    files.forEach(file => {
        const date = new Date(file.created_at).toLocaleString('es-ES');
        const size = formatFileSize(file.file_size);

        const row = `
            <tr>
                <td>${file.id}</td>
                <td style="font-weight: 600;">${file.original_filename}</td>
                <td>${size}</td>
                <td><span class="badge badge-info">${file.mime_type || 'N/A'}</span></td>
                <td>Usuario #${file.user_id || 'N/A'}</td>
                <td style="color: var(--admin-text-muted); font-size: 0.9em;">${date}</td>
                <td>
                    <button onclick="downloadFile(${file.id})" class="btn btn-primary btn-sm">
                        ⬇️ Descargar
                    </button>
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

async function downloadFile(fileId) {
    try {
        const response = await fetchWithAuth(`${API_BASE}/security/files/${fileId}/download`);

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `file_${fileId}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            alert('❌ Error al descargar archivo');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('❌ Error de conexión');
    }
}

// ============================================
// LOGS DE SEGURIDAD
// ============================================

async function loadSecurityLogs() {
    const tbody = document.getElementById('securityTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div>Cargando logs...</td></tr>';

    try {
        const response = await fetchWithAuth(`${API_BASE}/security/logs/security?limit=50`);

        if (response.ok) {
            const data = await response.json();
            renderSecurityLogsTable(data.logs);
        } else {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">⚠️ No disponible (requiere autenticación JWT)</td></tr>';
        }
    } catch (error) {
        console.error('Error:', error);
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">⚠️ Función no disponible</td></tr>';
    }
}

function renderSecurityLogsTable(logs) {
    const tbody = document.getElementById('securityTableBody');
    tbody.innerHTML = '';

    if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 30px; color: var(--admin-text-muted)">🔒 No hay eventos de seguridad</td></tr>';
        return;
    }

    logs.forEach(log => {
        const date = new Date(log.created_at).toLocaleString('es-ES');

        const statusBadge = log.success
            ? '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: var(--admin-success); border: 1px solid var(--admin-success)">✓ ÉXITO</span>'
            : '<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: var(--admin-danger); border: 1px solid var(--admin-danger)">✗ FALLO</span>';

        const row = `
            <tr>
                <td style="color: var(--admin-text-muted); font-size: 0.9em;">${date}</td>
                <td>${log.username || `User #${log.user_id}` || 'N/A'}</td>
                <td><span class="badge badge-info">${log.action}</span></td>
                <td style="font-family: monospace; font-size: 0.85em;">${log.ip_address || 'N/A'}</td>
                <td>${statusBadge}</td>
                <td style="color: var(--admin-text-muted); font-size: 0.85em;">${log.details || '-'}</td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

// ============================================
// UTILIDADES
// ============================================

async function fetchWithAuth(url, options = {}) {
    const headers = options.headers || {};

    // Intentar con JWT primero
    if (authToken && !authToken.includes('INTEGRA')) {
        headers['Authorization'] = `Bearer ${authToken}`;
    } else {
        // Fallback a sistema legacy
        headers['X-Admin-Token'] = authToken;
    }

    return fetch(url, { ...options, headers });
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// ============================================
// INICIALIZACIÓN
// ============================================

// Verificar si ya hay sesión activa
window.addEventListener('DOMContentLoaded', () => {
    // === DESBLOQUEO DE EMERGENCIA ACTIVADO ===
    localStorage.removeItem('lockoutUntil');

    // Verificar bloqueo persistente
    /* Bloqueo temporalmente desactivado para recuperación
    const savedLockout = localStorage.getItem('lockoutUntil');
    if (savedLockout) {
        lockoutUntil = parseInt(savedLockout);
        if (checkLockout()) {
            // Deshabilitar formulario
            document.getElementById('adminUsername').disabled = true;
            document.getElementById('adminPassword').disabled = true;
            document.querySelector('.login-btn').disabled = true;
            return;
        }
    }
    */

    const savedToken = sessionStorage.getItem('authToken');
    const savedUser = sessionStorage.getItem('currentUser');
    const loginTime = sessionStorage.getItem('loginTime');

    if (savedToken && savedUser && loginTime) {
        // Verificar si la sesión no ha expirado
        const sessionAge = Date.now() - parseInt(loginTime);
        const maxSessionAge = 8 * 60 * 60 * 1000; // 8 horas máximo

        if (sessionAge < maxSessionAge) {
            authToken = savedToken;
            currentUser = JSON.parse(savedUser);
            unlockDashboard();
            loadAllData();
            startAutoRefresh();
            initSessionProtection(); // IMPORTANTE: Activar protección
        } else {
            // Sesión expirada
            sessionStorage.clear();
            alert('⚠️ Sesión expirada. Por favor, inicia sesión nuevamente.');
        }
    }
});

// Limpiar al cerrar
window.addEventListener('beforeunload', () => {
    if (refreshInterval) clearInterval(refreshInterval);
    if (sessionTimeout) clearTimeout(sessionTimeout);
});

// Prevenir acceso no autorizado
window.addEventListener('load', () => {
    // Si no hay token después de 100ms, asegurar que el contenido esté bloqueado
    setTimeout(() => {
        if (!authToken) {
            const content = document.getElementById('adminContent');
            content.style.filter = 'blur(10px)';
            content.style.pointerEvents = 'none';
            content.style.opacity = '0';
        }
    }, 100);
});

console.log('🔐 Admin Panel Loaded - Integra Mind v2.0 - ACCESO RESTRINGIDO');
