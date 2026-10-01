// ==========================================
// Protección de Rutas (HU20 & HU21)
// Redirige a login.html si no existe helpstream_token en localStorage
// ==========================================
(function protegerRuta() {
    const token = localStorage.getItem('helpstream_token');
    const path = window.location.pathname;
    const esLogin = path.endsWith('login.html') || path.endsWith('/login');

    if (!token && !esLogin) {
        window.location.replace('login.html');
        return;
    }

    // Bloqueo estricto para usuarios regulares (rol_id 1) en páginas protegidas
    const rolId = localStorage.getItem('helpstream_rol_id');
    if (token && rolId === '1' && !esLogin) {
        localStorage.clear();
        window.location.replace('login.html');
        return;
    }

    // HU20: Restricción estricta en frontend para dashboard_gerencial.html
    if (token && path.endsWith('dashboard_gerencial.html')) {
        const rol = localStorage.getItem('helpstream_user_role');
        if (rol && rol !== 'Jefe de TI' && rolId && rolId !== '3') {
            alert('Acceso denegado exclusivo para Jefatura. Redirigiendo a la mesa de ayuda...');
            window.location.replace('index.html');
        }
    }
})();

// URL base de producción en Render o local si se ejecuta en localhost
const API_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? (window.location.origin)
    : 'https://helpstream-api.onrender.com';

// Endpoints centralizados de la API
const ENDPOINTS = {
    LOGIN_LOCAL: `${API_URL}/api/auth/login/local`, // HU21: Endpoint de inicio de sesión local con JWT
    REGISTRO: `${API_URL}/api/auth/registro`,       // Endpoint de registro con asignación de rol
    ROLES: `${API_URL}/api/auth/roles`,             // Lista de roles del sistema
    USUARIOS: `${API_URL}/api/auth/usuarios`,       // Lista y gestión de usuarios
    TICKETS: `${API_URL}/tickets/`,
    VIDEOS: `${API_URL}/videos/`,
    REPORTES_DASHBOARD: `${API_URL}/api/reportes/dashboard`, // HU20: Reportes y dashboard gerencial
    REPORTES_KPIS: `${API_URL}/api/reportes/kpis`,
    REPORTES_TICKETS: `${API_URL}/api/reportes/tickets`,
    DASHBOARD_GERENCIAL: `${API_URL}/api/dashboard/gerencial`,
    REPORTES_EXCEL: `${API_URL}/api/reportes/exportar/excel`, // HU15.3: Exportación nativa a Excel
    ANALYTICS_DASHBOARD: `${API_URL}/api/analytics/dashboard` // HU15: HelpStream Analytics
};

let modalInstance = null;
let allTickets = []; // Global state for client-side filtering

// ==========================================
// HU18: Tiempos SLA según Criticidad (en horas equivalentes a 1, 3 y 7 días)
// Alta: 24h, Media: 72h, Baja: 168h
// ==========================================
const SLA_TIEMPOS_HORAS = {
    'Alta': 24,
    'Alto': 24,
    'Crítico': 24,
    'Critico': 24,
    'Media': 72,
    'Medio': 72,
    'Baja': 168,
    'Bajo': 168
};

let slaIntervalId = null;

// ==========================================
// HU21 & HU20: Flujo de Autenticación / Inicio de Sesión
// Endpoint: /api/auth/login/local
// ==========================================
async function iniciarSesion(correo, password) {
    try {
        const formData = new URLSearchParams();
        formData.append('username', correo);
        formData.append('password', password);

        const response = await fetch(ENDPOINTS.LOGIN_LOCAL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Correo o contraseña incorrectos');
        }

        const data = await response.json();

        // 1. Extraer y verificar inmediatamente el rol_id del usuario
        let userRolId = (data.rol_id !== undefined && data.rol_id !== null) ? Number(data.rol_id) : null;
        let tokenPayload = null;
        if (data.access_token) {
            try {
                tokenPayload = JSON.parse(atob(data.access_token.split('.')[1]));
                if (userRolId === null && tokenPayload && tokenPayload.rol_id !== undefined && tokenPayload.rol_id !== null) {
                    userRolId = Number(tokenPayload.rol_id);
                }
            } catch (err) {
                console.warn('No se pudo decodificar payload JWT:', err);
            }
        }

        // =========================================================================
        // Bloqueo de Acceso a Usuarios Regulares (rol_id === 1)
        // El portal web es exclusivo para el equipo de TI. Bloquear inmediatamente,
        // no guardar el token en localStorage y detener cualquier redirección.
        // =========================================================================
        if (userRolId === 1) {
            throw new Error('Acceso denegado: El portal web es exclusivo para el equipo de TI. Por favor, utilice la aplicación móvil.');
        }

        // 2. Guardar credenciales y datos de sesión de personal TI en localStorage
        if (data.access_token) {
            localStorage.setItem('helpstream_token', data.access_token);
            localStorage.setItem('helpstream_token_type', data.token_type || 'bearer');

            // Determinar rol
            let userRole = data.rol || data.rol_nombre;
            if (!userRole && tokenPayload && tokenPayload.rol) {
                userRole = tokenPayload.rol;
            }
            if (!userRole) {
                if (userRolId === 3) userRole = 'Jefe de TI';
                else if (userRolId === 2) userRole = 'Analista TI';
                else userRole = 'Soporte TI';
            }
            localStorage.setItem('helpstream_user_role', userRole);
            if (userRolId !== null) localStorage.setItem('helpstream_rol_id', String(userRolId));
            localStorage.setItem('helpstream_user_email', correo);

            // Determinar nombre completo y guardarlo en localStorage
            let nombreCompleto = data.nombre_completo || data.nombre;
            if (!nombreCompleto && (data.nombres || data.apellidos)) {
                nombreCompleto = `${data.nombres || ''} ${data.apellidos || ''}`.trim();
            }
            if (!nombreCompleto && tokenPayload) {
                if (tokenPayload.nombre_completo || tokenPayload.nombre) {
                    nombreCompleto = tokenPayload.nombre_completo || tokenPayload.nombre;
                } else if (tokenPayload.nombres || tokenPayload.apellidos) {
                    nombreCompleto = `${tokenPayload.nombres || ''} ${tokenPayload.apellidos || ''}`.trim();
                }
            }

            // Fallback: si no viene en el token o respuesta, consultar al backend por correo
            if (!nombreCompleto) {
                try {
                    const userRes = await fetch(`${ENDPOINTS.USUARIOS}/buscar?correo=${encodeURIComponent(correo)}`);
                    if (userRes.ok) {
                        const userObj = await userRes.json();
                        nombreCompleto = `${userObj.nombres || ''} ${userObj.apellidos || ''}`.trim();
                    }
                } catch (err) {
                    console.warn('No se pudo consultar detalle de usuario por correo:', err);
                }
            }

            // Fallback final derivado del correo o rol
            if (!nombreCompleto) {
                const namePart = correo.split('@')[0].replace(/[._-]/g, ' ');
                nombreCompleto = namePart.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') || userRole;
            }

            localStorage.setItem('helpstream_user_name', nombreCompleto);
            localStorage.setItem('helpstream_user_fullname', nombreCompleto);
        }
        return data;
    } catch (error) {
        console.error('Error en autenticación HU21:', error);
        throw error;
    }
}

// Cerrar sesión y limpiar credenciales
function cerrarSesion() {
    localStorage.removeItem('helpstream_token');
    localStorage.removeItem('helpstream_token_type');
    localStorage.removeItem('helpstream_user_role');
    localStorage.removeItem('helpstream_rol_id');
    localStorage.removeItem('helpstream_user_email');
    localStorage.removeItem('helpstream_user_name');
    localStorage.removeItem('helpstream_user_fullname');
    window.location.replace('login.html');
}

// ==========================================
// Datos Dinámicos en el Navbar / Top Header
// ==========================================
function calcularIniciales(nombreCompleto) {
    if (!nombreCompleto || typeof nombreCompleto !== 'string') return 'TI';
    const partes = nombreCompleto.trim().split(/\s+/).filter(Boolean);
    if (partes.length === 0) return 'TI';
    if (partes.length === 1) {
        return partes[0].slice(0, 2).toUpperCase();
    }
    // Primera letra del primer nombre y primera letra del primer apellido
    return (partes[0][0] + partes[1][0]).toUpperCase();
}

function actualizarDatosNavbar() {
    const token = localStorage.getItem('helpstream_token');
    const path = window.location.pathname;
    const esLogin = path.endsWith('login.html') || path.endsWith('/login');
    if (!token || esLogin) return;

    let nombre = localStorage.getItem('helpstream_user_name') || localStorage.getItem('helpstream_user_fullname');
    let rol = localStorage.getItem('helpstream_user_role');
    const rolId = localStorage.getItem('helpstream_rol_id');
    const email = localStorage.getItem('helpstream_user_email');

    if (!rol) {
        if (rolId === '3') rol = 'Jefe de TI';
        else if (rolId === '2') rol = 'Analista TI';
        else rol = 'Soporte TI';
    }

    if (!nombre && email) {
        const usernamePart = email.split('@')[0].replace(/[._-]/g, ' ');
        nombre = usernamePart.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    }
    if (!nombre) {
        nombre = (rol === 'Jefe de TI' || rolId === '3') ? 'Jefe de TI' : 'Analista TI';
    }

    const iniciales = calcularIniciales(nombre);

    // Actualizar nombre completo en Navbar
    const nameEls = document.querySelectorAll('#navbar-user-name, .navbar-user-name, #headerAdminNombre');
    nameEls.forEach(el => {
        el.textContent = nombre;
    });

    // Actualizar rol en Navbar
    const roleEls = document.querySelectorAll('#navbar-user-role, .navbar-user-role, #headerAdminRol');
    roleEls.forEach(el => {
        el.textContent = rol;
    });

    // Actualizar iniciales en avatar circular
    const initialEls = document.querySelectorAll('#navbar-user-initials, .navbar-user-initials, #headerAdminAvatar');
    initialEls.forEach(el => {
        el.textContent = iniciales;
    });
}
window.actualizarDatosNavbar = actualizarDatosNavbar;
window.calcularIniciales = calcularIniciales;

// Ejecutar automáticamente al cargar cualquier página protegida
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', actualizarDatosNavbar);
} else {
    actualizarDatosNavbar();
}

// Conectar evento submit del formulario de login.html
function inicializarLogin(loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const correoInput = document.getElementById('loginCorreo');
        const passwordInput = document.getElementById('loginPassword');
        const alertBox = document.getElementById('loginAlert');
        const btnSubmit = document.getElementById('btnLogin');

        const correo = correoInput ? correoInput.value.trim() : '';
        const password = passwordInput ? passwordInput.value : '';

        if (!correo || !password) {
            if (alertBox) {
                alertBox.textContent = 'Por favor ingresa tu correo y contraseña.';
                alertBox.classList.remove('d-none');
            }
            return;
        }

        if (alertBox) {
            alertBox.classList.add('d-none');
            alertBox.textContent = '';
        }

        // Estado visual del botón durante la autenticación
        const originalBtnContent = btnSubmit ? btnSubmit.innerHTML : 'Ingresar';
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Ingresando...';
        }

        try {
            const data = await iniciarSesion(correo, password);
            if (data && data.access_token) {
                // Doble validación preventiva por si rol_id es 1
                const rolId = data.rol_id !== undefined ? Number(data.rol_id) : Number(localStorage.getItem('helpstream_rol_id'));
                if (rolId === 1) {
                    cerrarSesion();
                    if (alertBox) {
                        alertBox.textContent = 'Acceso denegado: El portal web es exclusivo para el equipo de TI. Por favor, utilice la aplicación móvil.';
                        alertBox.classList.remove('d-none');
                    }
                    return;
                }

                // =========================================================================
                // HU20: Bifurcación en el Login según el Rol de Usuario
                // Si es "Jefe de TI", ejecuta window.location.replace('dashboard_gerencial.html')
                // Si es analista o soporte técnico, mantén window.location.replace('index.html')
                // =========================================================================
                let userRole = localStorage.getItem('helpstream_user_role') || data.rol || data.rol_nombre;
                if (!userRole && (data.rol_id === 3 || rolId === 3)) {
                    userRole = 'Jefe de TI';
                }

                if (userRole === 'Jefe de TI' || data.rol_id === 3 || rolId === 3) {
                    window.location.replace('dashboard_gerencial.html');
                } else {
                    window.location.replace('index.html');
                }
            } else {
                throw new Error('No se recibió el token de autenticación del servidor.');
            }
        } catch (error) {
            if (alertBox) {
                alertBox.textContent = error.message || 'Error al iniciar sesión. Verifica tus credenciales.';
                alertBox.classList.remove('d-none');
            } else {
                alert(error.message || 'Error al iniciar sesión.');
            }
        } finally {
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = originalBtnContent;
            }
        }
    });
}


// ==========================================
// HU11: Creación Rápida de Tickets (con Sede y Piso)
// ==========================================
function inicializarFormNuevoTicket() {
    const formNuevoTicket = document.getElementById('formNuevoTicket');
    if (!formNuevoTicket) return;

    const sedeSelect = document.getElementById('nuevoTicketSede');
    const pisoSelect = document.getElementById('nuevoTicketPiso');

    // Event listener dinámico: Piso solo se habilita si la sede es "San Isidro"
    if (sedeSelect && pisoSelect) {
        sedeSelect.addEventListener('change', () => {
            if (sedeSelect.value === 'San Isidro') {
                pisoSelect.disabled = false;
            } else {
                pisoSelect.disabled = true;
                pisoSelect.value = '';
            }
        });
    }

    formNuevoTicket.addEventListener('submit', async (e) => {
        e.preventDefault();

        const correoInput = document.getElementById('nuevoTicketCorreo');
        const descripcionInput = document.getElementById('nuevoTicketDescripcion');
        const criticidadInput = document.getElementById('nuevoTicketCriticidad');
        const alertBox = document.getElementById('nuevoTicketAlert');
        const btnSubmit = document.getElementById('btnRegistrarTicket');

        const correo = correoInput ? correoInput.value.trim() : '';
        const sede = sedeSelect ? sedeSelect.value : '';
        const piso = (pisoSelect && !pisoSelect.disabled) ? pisoSelect.value : '';
        const criticidad = criticidadInput ? criticidadInput.value : 'Media';
        const descripcion = descripcionInput ? descripcionInput.value.trim() : '';

        if (!correo) {
            if (alertBox) {
                alertBox.textContent = 'Por favor ingrese el correo del solicitante.';
                alertBox.classList.remove('d-none');
            }
            return;
        }

        if (!sede) {
            if (alertBox) {
                alertBox.textContent = 'Por favor seleccione la sede del incidente.';
                alertBox.classList.remove('d-none');
            }
            return;
        }

        if (sede === 'San Isidro' && !piso) {
            if (alertBox) {
                alertBox.textContent = 'Por favor seleccione el piso para la sede San Isidro.';
                alertBox.classList.remove('d-none');
            }
            return;
        }

        if (!descripcion) {
            if (alertBox) {
                alertBox.textContent = 'Por favor ingrese la descripción del incidente.';
                alertBox.classList.remove('d-none');
            }
            return;
        }

        if (alertBox) {
            alertBox.classList.add('d-none');
            alertBox.textContent = '';
        }

        // Estado visual del botón durante la creación
        const originalBtnContent = btnSubmit ? btnSubmit.innerHTML : 'Registrar Ticket';
        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Registrando...';
        }

        try {
            const token = localStorage.getItem('helpstream_token');
            const response = await fetch(ENDPOINTS.TICKETS, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + token
                },
                body: JSON.stringify({
                    correo: correo,
                    sede: sede,
                    piso: piso,
                    descripcion: descripcion,
                    criticidad: criticidad
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Error al registrar el ticket.');
            }

            // Éxito: cerrar modal, limpiar formulario y notificar
            const modalEl = document.getElementById('modalNuevoTicket');
            if (modalEl) {
                const bsModal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                bsModal.hide();
            }

            formNuevoTicket.reset();
            if (pisoSelect) {
                pisoSelect.disabled = true;
                pisoSelect.value = '';
            }

            // Mostrar alerta temporal de éxito
            mostrarAlertaExito('¡Ticket registrado exitosamente!');

            // Recargar tickets y KPIs
            cargarTickets();

        } catch (error) {
            if (alertBox) {
                alertBox.textContent = error.message || 'Error al conectar con el servidor.';
                alertBox.classList.remove('d-none');
            } else {
                alert(error.message || 'Error al registrar el ticket.');
            }
        } finally {
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = originalBtnContent;
            }
        }
    });
}

function mostrarAlertaExito(mensaje) {
    const alertEl = document.getElementById('dashboardAlert');
    const msgEl = document.getElementById('dashboardAlertMsg');
    if (alertEl && msgEl) {
        msgEl.textContent = mensaje;
        alertEl.classList.remove('d-none');
        setTimeout(() => {
            alertEl.classList.add('d-none');
        }, 5000);
    } else {
        alert(mensaje);
    }
}

// ==========================================
// MÓDULO DE GESTIÓN DE USUARIOS
// ==========================================
function inicializarModuloUsuarios() {
    // 1. Formulario Registrar Usuario (registrar_usuario.html)
    const formRegistro = document.getElementById('formRegistroUsuario');
    if (formRegistro) {
        formRegistro.addEventListener('submit', async (e) => {
            e.preventDefault();
            const alertBox = document.getElementById('regUserAlert');
            const btnSubmit = document.getElementById('btnSubmitRegistro');

            const nombre = document.getElementById('regNombre').value.trim();
            const correo = document.getElementById('regCorreo').value.trim();
            const password = document.getElementById('regPassword').value;
            const rol_id = parseInt(document.getElementById('regRol').value, 10);
            const telefonoInput = document.getElementById('telefono') || document.getElementById('regTelefono');
            const anexoInput = document.getElementById('anexo') || document.getElementById('regAnexo');
            const telefono = telefonoInput ? telefonoInput.value.trim() : null;
            const anexo = anexoInput ? anexoInput.value.trim() : null;

            if (alertBox) {
                alertBox.classList.add('d-none');
            }
            if (btnSubmit) {
                btnSubmit.disabled = true;
                btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Registrando...';
            }

            try {
                const response = await fetch(ENDPOINTS.REGISTRO, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ nombre, correo, password, rol_id, telefono, anexo })
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || 'Error al registrar el usuario.');
                }

                if (alertBox) {
                    alertBox.className = 'alert alert-success py-2 px-3 small';
                    alertBox.textContent = `¡Usuario "${nombre}" registrado con éxito!`;
                    alertBox.classList.remove('d-none');
                }
                formRegistro.reset();
            } catch (err) {
                if (alertBox) {
                    alertBox.className = 'alert alert-danger py-2 px-3 small';
                    alertBox.textContent = err.message;
                    alertBox.classList.remove('d-none');
                }
            } finally {
                if (btnSubmit) {
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = '<i class="bi bi-person-check-fill me-2"></i> Registrar Usuario';
                }
            }
        });
    }

    // 2. Búsqueda y Edición de Usuario (editar_usuario.html)
    const btnBuscar = document.getElementById('btnBuscarUsuario');
    const inputBuscar = document.getElementById('inputBuscarCorreo');
    const formEditar = document.getElementById('formEditarUsuario');
    const contenedorFormEditar = document.getElementById('contenedorFormEditar');
    const alertEdit = document.getElementById('editUserAlert');

    async function buscarUsuario() {
        const correo = inputBuscar ? inputBuscar.value.trim() : '';
        if (!correo) return;

        if (alertEdit) alertEdit.classList.add('d-none');

        try {
            const response = await fetch(`${ENDPOINTS.USUARIOS}/buscar?correo=${encodeURIComponent(correo)}`);
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || 'Usuario no encontrado.');
            }

            const usuario = await response.json();

            // Cargar datos en el formulario
            document.getElementById('editUserId').value = usuario.id;
            document.getElementById('editNombre').value = usuario.nombres || '';
            document.getElementById('editCorreo').value = usuario.correo || '';
            const editTelefono = document.getElementById('telefono') || document.getElementById('editTelefono');
            if (editTelefono) editTelefono.value = usuario.telefono || '';
            const editAnexo = document.getElementById('anexo') || document.getElementById('editAnexo');
            if (editAnexo) editAnexo.value = usuario.anexo || '';
            document.getElementById('editRol').value = usuario.rol_id;
            document.getElementById('editActivo').checked = usuario.activo;

            if (contenedorFormEditar) {
                contenedorFormEditar.classList.remove('d-none');
            }
        } catch (err) {
            if (contenedorFormEditar) {
                contenedorFormEditar.classList.add('d-none');
            }
            if (alertEdit) {
                alertEdit.className = 'alert alert-danger py-2 px-3 small';
                alertEdit.textContent = err.message;
                alertEdit.classList.remove('d-none');
            }
        }
    }

    if (btnBuscar) {
        btnBuscar.addEventListener('click', buscarUsuario);
    }
    if (inputBuscar) {
        inputBuscar.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                buscarUsuario();
            }
        });
    }

    if (formEditar) {
        formEditar.addEventListener('submit', async (e) => {
            e.preventDefault();
            const userId = document.getElementById('editUserId').value;
            const nombres = document.getElementById('editNombre').value.trim();
            const correo = document.getElementById('editCorreo').value.trim();
            const rol_id = parseInt(document.getElementById('editRol').value, 10);
            const activo = document.getElementById('editActivo').checked;
            const editTelefono = document.getElementById('telefono') || document.getElementById('editTelefono');
            const editAnexo = document.getElementById('anexo') || document.getElementById('editAnexo');
            const telefono = editTelefono ? editTelefono.value.trim() : null;
            const anexo = editAnexo ? editAnexo.value.trim() : null;
            const btnGuardar = document.getElementById('btnGuardarEdicion');

            if (btnGuardar) {
                btnGuardar.disabled = true;
                btnGuardar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Guardando...';
            }

            try {
                const response = await fetch(`${ENDPOINTS.USUARIOS}/${userId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ nombres, correo, rol_id, activo, telefono, anexo })
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || 'Error al guardar cambios.');
                }

                if (alertEdit) {
                    alertEdit.className = 'alert alert-success py-2 px-3 small';
                    alertEdit.textContent = '¡Datos de usuario actualizados correctamente!';
                    alertEdit.classList.remove('d-none');
                }
            } catch (err) {
                if (alertEdit) {
                    alertEdit.className = 'alert alert-danger py-2 px-3 small';
                    alertEdit.textContent = err.message;
                    alertEdit.classList.remove('d-none');
                }
            } finally {
                if (btnGuardar) {
                    btnGuardar.disabled = false;
                    btnGuardar.innerHTML = '<i class="bi bi-save me-1"></i> Guardar Cambios';
                }
            }
        });
    }

    // 3. Directorio de Usuarios (directorio_usuarios.html)
    const tablaDirectorio = document.getElementById('tablaDirectorioBody');
    if (tablaDirectorio) {
        cargarDirectorioUsuarios();
    }
}

async function cargarDirectorioUsuarios() {
    const tbody = document.getElementById('tablaDirectorioBody');
    if (!tbody) return;

    try {
        const response = await fetch(ENDPOINTS.USUARIOS);
        if (!response.ok) throw new Error('Error al cargar la lista de usuarios.');
        const usuarios = await response.json();

        const rolesMap = {
            1: 'Usuario Planta',
            2: 'Analista TI',
            3: 'Jefe TI'
        };

        tbody.innerHTML = '';
        if (usuarios.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">No hay usuarios registrados.</td></tr>';
            return;
        }

        usuarios.forEach(u => {
            const tr = document.createElement('tr');
            const rolNombre = rolesMap[u.rol_id] || `Rol ${u.rol_id}`;
            const estadoBadge = u.activo 
                ? '<span class="badge bg-success">Activo</span>' 
                : '<span class="badge bg-secondary">Inactivo</span>';

            tr.innerHTML = `
                <td class="fw-bold text-muted">#${u.id}</td>
                <td class="fw-semibold">${u.nombres || '-'}</td>
                <td>${u.correo}</td>
                <td>${u.telefono || '<span class="text-muted small">-</span>'}</td>
                <td>${u.anexo ? `<span class="badge bg-light text-dark border">${u.anexo}</span>` : '<span class="text-muted small">-</span>'}</td>
                <td><span class="badge bg-primary bg-opacity-10 text-primary border border-primary border-opacity-25 px-2 py-1">${rolNombre}</span></td>
                <td>${estadoBadge}</td>
                <td>
                    <a href="editar_usuario.html?correo=${encodeURIComponent(u.correo)}" class="btn btn-sm btn-outline-primary rounded-pill px-3">
                        <i class="bi bi-pencil-square"></i> Editar
                    </a>
                    <button class="btn btn-sm btn-outline-danger rounded-pill px-3 ms-2" onclick="eliminarUsuario(${u.id})">
                        <i class="bi bi-trash"></i> Eliminar
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger py-4">Error al cargar usuarios desde el servidor.</td></tr>';
    }
}

async function eliminarUsuario(id) {
    const confirmacion = confirm('¿Está seguro que desea eliminar este usuario?');
    if (!confirmacion) {
        return;
    }

    try {
        const token = localStorage.getItem('helpstream_token');
        const headers = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_URL}/api/usuarios/${id}`, {
            method: 'DELETE',
            headers: headers
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            const errorMsg = data.detail || 'Error al eliminar el usuario.';
            alert(errorMsg);
            return;
        }

        alert(data.mensaje || 'Usuario eliminado exitosamente.');
        cargarDirectorioUsuarios();
    } catch (err) {
        console.error('Error al eliminar usuario:', err);
        alert(err.message || 'Error de conexión con el servidor al intentar eliminar el usuario.');
    }
}
window.eliminarUsuario = eliminarUsuario;

document.addEventListener("DOMContentLoaded", () => {
    // Si estamos en login.html
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        inicializarLogin(loginForm);
        return;
    }

    // Actualización dinámica de datos de usuario en el Navbar
    actualizarDatosNavbar();

    // Inicialización del Menú Lateral en todas las páginas
    inicializarSidebar();

    // Inicialización del Dashboard (index.html)
    const modalEl = document.getElementById('gestionarModal');
    if (modalEl) {
        modalInstance = new bootstrap.Modal(modalEl);
    }
    const ticketsTable = document.getElementById('ticketsTable');
    if (ticketsTable) {
        cargarTickets();
    }

    // Inicializar modal de nuevo ticket si está presente
    inicializarFormNuevoTicket();

    // Inicializar módulo de usuarios si corresponde
    inicializarModuloUsuarios();

    // Inicializar Dashboard Gerencial & Reportes si la vista está presente (HU20)
    if (document.getElementById('view-gerencial') || document.getElementById('tablaReportesGerencial')) {
        inicializarDashboardGerencial();
    }

    // Pre-llenar búsqueda si viene parámetro correo en la URL
    const urlParams = new URLSearchParams(window.location.search);
    const correoParam = urlParams.get('correo');
    const inputBuscar = document.getElementById('inputBuscarCorreo');
    const btnBuscar = document.getElementById('btnBuscarUsuario');
    if (correoParam && inputBuscar && btnBuscar) {
        inputBuscar.value = correoParam;
        btnBuscar.click();
    }
});

// Control del Menú Lateral (Sidebar Colapsable)
function toggleSidebar(forceState) {
    const body = document.body;
    if (typeof forceState === 'boolean') {
        if (forceState) {
            body.classList.add('sidebar-open');
        } else {
            body.classList.remove('sidebar-open');
        }
    } else {
        body.classList.toggle('sidebar-open');
    }
}

function inicializarSidebar() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleSidebar();
        });
    }

    const sidebarCloseBtn = document.getElementById('sidebarCloseBtn');
    if (sidebarCloseBtn) {
        sidebarCloseBtn.addEventListener('click', () => {
            toggleSidebar(false);
        });
    }

    const backdrop = document.getElementById('sidebarBackdrop');
    if (backdrop) {
        backdrop.addEventListener('click', () => {
            toggleSidebar(false);
        });
    }

    // Cerrar con Escape si está abierto
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && document.body.classList.contains('sidebar-open')) {
            toggleSidebar(false);
        }
    });

    // Si el usuario es Jefe de TI y está navegando en páginas operativas, agregar acceso al Dashboard Gerencial
    const userRole = localStorage.getItem('helpstream_user_role');
    const rolId = localStorage.getItem('helpstream_rol_id');
    const esJefe = (userRole === 'Jefe de TI' || rolId === '3');
    if (esJefe && !window.location.pathname.endsWith('dashboard_gerencial.html')) {
        const navContainer = document.querySelector('#sidebar .mt-4');
        const navDashboard = document.getElementById('nav-dashboard');
        if (navContainer && !document.getElementById('nav-acceso-gerencial')) {
            const enlaceGerencial = document.createElement('a');
            enlaceGerencial.href = 'dashboard_gerencial.html';
            enlaceGerencial.id = 'nav-acceso-gerencial';
            enlaceGerencial.className = 'nav-link text-decoration-none fw-semibold';
            enlaceGerencial.style.color = '#ff9248';
            enlaceGerencial.innerHTML = '<i class="bi bi-speedometer2 text-warning"></i> Dashboard Gerencial';
            if (navDashboard) {
                navContainer.insertBefore(enlaceGerencial, navDashboard);
            } else {
                navContainer.prepend(enlaceGerencial);
            }
        }
    }
}

// View Navigation
function switchView(viewName) {
    document.getElementById('view-dashboard').style.display = 'none';
    document.getElementById('view-knowledge-base').style.display = 'none';
    
    document.getElementById('nav-dashboard').classList.remove('active');
    document.getElementById('nav-kb').classList.remove('active');

    if (viewName === 'dashboard') {
        document.getElementById('view-dashboard').style.display = 'block';
        document.getElementById('nav-dashboard').classList.add('active');
        // Opcional: Recargar tickets al volver al dashboard
        // cargarTickets(); 
    } else if (viewName === 'knowledge-base') {
        document.getElementById('view-knowledge-base').style.display = 'block';
        document.getElementById('nav-kb').classList.add('active');
    }

    // En pantallas pequeñas, cerramos el menú tras seleccionar una opción
    if (window.innerWidth < 992 && document.body.classList.contains('sidebar-open')) {
        toggleSidebar(false);
    }
}

// Fetch Tickets
async function cargarTickets() {
    try {
        const response = await fetch(`${API_URL}/tickets/?skip=0&limit=100`);
        if (!response.ok) throw new Error("Error al cargar los tickets");
        
        allTickets = await response.json();
        
        // Inicializar vistas
        calcularMetricas(allTickets);
        aplicarFiltros(); // Esto llamará a renderTickets() con los filtros actuales (por defecto: Todos)
        
    } catch (error) {
        console.error(error);
        alert("Ocurrió un error al cargar los datos del servidor.");
        document.getElementById('ticketsBody').innerHTML = '<tr><td colspan="12" class="text-center text-danger">Error al cargar datos</td></tr>';
    }
}

// Calcular KPIs
function calcularMetricas(tickets) {
    let abiertos = 0;
    let resueltos = 0;
    let nuevosHoy = 0;
    
    const hoy = new Date();
    // Obtener fecha de hoy en formato YYYY-MM-DD en hora de Lima
    const formatoHoy = hoy.toLocaleDateString('en-CA', { timeZone: 'America/Lima' });

    tickets.forEach(t => {
        // Abiertos vs Resueltos
        if (t.estado === 'Resuelto') {
            resueltos++;
        } else {
            abiertos++;
        }
        
        // Tickets de Hoy en hora de Lima
        if (t.fecha_creacion) {
            try {
                const dt = new Date(t.fecha_creacion);
                const fechaTicket = !isNaN(dt.getTime())
                    ? dt.toLocaleDateString('en-CA', { timeZone: 'America/Lima' })
                    : t.fecha_creacion.split('T')[0];
                if (fechaTicket === formatoHoy) {
                    nuevosHoy++;
                }
            } catch (e) {
                const fechaTicket = t.fecha_creacion.split('T')[0];
                if (fechaTicket === formatoHoy) {
                    nuevosHoy++;
                }
            }
        }
    });

    document.getElementById('kpi-abiertos').textContent = abiertos;
    document.getElementById('kpi-resueltos').textContent = resueltos;
    document.getElementById('kpi-hoy').textContent = nuevosHoy;
}

// Lógica de Filtros Avanzados
function aplicarFiltros() {
    const searchText = document.getElementById('filter-search').value.toLowerCase().trim();
    const criticidadFilter = document.getElementById('filter-criticidad').value;
    const estadoFilter = document.getElementById('filter-estado').value;
    const evidenciaFilter = document.getElementById('filter-evidencia').value;

    const filteredTickets = allTickets.filter(ticket => {
        // 1. Filtro por Texto (ID o Descripción)
        let matchesSearch = true;
        if (searchText) {
            matchesSearch = ticket.id.toString().includes(searchText) || 
                            ticket.descripcion.toLowerCase().includes(searchText);
        }

        // 2. Filtro por Criticidad
        let matchesCriticidad = true;
        if (criticidadFilter !== 'Todos') {
            const crit = ticket.criticidad || 'Medio';
            matchesCriticidad = crit === criticidadFilter;
        }

        // 3. Filtro por Estado
        let matchesEstado = true;
        if (estadoFilter !== 'Todos') {
            matchesEstado = ticket.estado === estadoFilter;
        }

        // 4. Filtro por Evidencia
        let matchesEvidencia = true;
        if (evidenciaFilter === 'Con Evidencia') {
            matchesEvidencia = ticket.evidencia_url !== null && ticket.evidencia_url !== undefined;
        } else if (evidenciaFilter === 'Sin Evidencia') {
            matchesEvidencia = ticket.evidencia_url === null || ticket.evidencia_url === undefined;
        }

        return matchesSearch && matchesCriticidad && matchesEstado && matchesEvidencia;
    });

    renderTickets(filteredTickets);
}

// Renderizar Tabla
function renderTickets(tickets) {
    const tbody = document.getElementById('ticketsBody');
    if (!tbody) return;

    // Destruir instancias previas de popovers para evitar elementos huérfanos
    const oldPopovers = tbody.querySelectorAll('[data-bs-toggle="popover"]');
    oldPopovers.forEach(el => {
        const pop = bootstrap.Popover.getInstance(el);
        if (pop) pop.dispose();
    });

    tbody.innerHTML = '';

    if (tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center text-muted py-4">No se encontraron tickets con los filtros actuales.</td></tr>';
        return;
    }

    tickets.forEach(ticket => {
        // Formatear Fecha en Zona Horaria America/Lima (UTC-5)
        let fechaFormatted = '-';
        if (ticket.fecha_creacion) {
            try {
                const d = new Date(ticket.fecha_creacion);
                if (!isNaN(d.getTime())) {
                    const dia = d.toLocaleDateString('es-PE', { timeZone: 'America/Lima', day: '2-digit' });
                    const mes = d.toLocaleDateString('es-PE', { timeZone: 'America/Lima', month: '2-digit' });
                    const hora = d.toLocaleTimeString('es-PE', { timeZone: 'America/Lima', hour: '2-digit', minute: '2-digit', hour12: false });
                    fechaFormatted = `${dia}/${mes} ${hora}`;
                }
            } catch (e) {
                fechaFormatted = String(ticket.fecha_creacion);
            }
        }

        // Badge Estado
        const estadoBadge = obtenerBadgeEstado(ticket.estado);
        
        // Badge Criticidad
        const criticidad = ticket.criticidad || "Medio";
        let criticidadBadge = "bg-secondary";
        if (criticidad === "Crítico" || criticidad === "Alto") {
            criticidadBadge = "bg-danger";
        } else if (criticidad === "Medio" || criticidad === "Bajo") {
            criticidadBadge = "bg-warning text-dark";
        }

        // HU18: Columna SLA y atributos data para el temporizador en tiempo real
        let slaHtml = '';
        const estadoNorm = (ticket.estado || '').trim();
        if (estadoNorm === 'Resuelto' || estadoNorm === 'Cerrado') {
            slaHtml = `<span class="sla-timer text-muted fw-semibold" data-fecha="${ticket.fecha_creacion || ''}" data-criticidad="${criticidad}" data-estado="${ticket.estado}">Detenido</span>`;
        } else {
            slaHtml = `<span class="sla-timer fw-semibold" data-fecha="${ticket.fecha_creacion || ''}" data-criticidad="${criticidad}" data-estado="${ticket.estado}">-</span>`;
        }

        // Evidencia
        let evidenciaHref = '#';
        if (ticket.evidencia_url) {
            evidenciaHref = ticket.evidencia_url.startsWith('http')
                ? ticket.evidencia_url
                : `${API_URL}${ticket.evidencia_url.startsWith('/') ? '' : '/'}${ticket.evidencia_url}`;
        }
        const evidenciaHtml = ticket.evidencia_url 
            ? `<a href="${evidenciaHref}" target="_blank" class="btn btn-sm btn-outline-info rounded-pill px-3"><i class="bi bi-paperclip"></i> Ver</a>`
            : `<span class="text-muted small"><i class="bi bi-dash"></i> Sin adjunto</span>`;

        // HU17: Información del Creador y Popover Interactivo de Bootstrap
        const creador = ticket.creador || ticket.usuario || {};
        const nombreCompleto = creador.nombre || (creador.nombres ? `${creador.nombres} ${creador.apellidos || ''}`.trim() : null) || (ticket.correo_solicitante ? ticket.correo_solicitante.split('@')[0] : `Usuario #${ticket.usuario_id}`);
        const correoContacto = creador.correo || ticket.correo_solicitante || 'No registrado';
        const telefonoContacto = creador.telefono || 'No registrado';
        const anexoContacto = creador.anexo || 'No registrado';

        const popoverContent = `
            <div class='p-1'>
                <div class='mb-1 text-nowrap'><strong><i class='bi bi-envelope-fill text-primary me-1'></i> Correo:</strong> ${correoContacto}</div>
                <div class='mb-1 text-nowrap'><strong><i class='bi bi-telephone-fill text-success me-1'></i> Teléfono:</strong> ${telefonoContacto}</div>
                <div class='text-nowrap'><strong><i class='bi bi-telephone-forward-fill text-info me-1'></i> Anexo:</strong> ${anexoContacto}</div>
            </div>
        `.trim().replace(/"/g, '&quot;');

        const usuarioHtml = `
            <button type="button" 
               class="btn btn-link p-0 text-decoration-none fw-semibold text-primary d-inline-flex align-items-center" 
               data-bs-toggle="popover" 
               data-bs-html="true" 
               title="Datos de Contacto" 
               data-bs-content="${popoverContent}">
                <i class="bi bi-person-circle me-1 text-secondary"></i><span>${nombreCompleto}</span>
            </button>
        `;

        const tr = document.createElement('tr');

        tr.innerHTML = `
            <td class="fw-bold text-muted">#${ticket.id}</td>
            <td>${usuarioHtml}</td>
            <td class="small text-muted">${fechaFormatted}</td>
            <td style="max-width: 250px;" class="text-truncate" title="${ticket.descripcion}">${ticket.descripcion}</td>
            <td><span class="badge bg-light text-dark border">${ticket.sede || '-'}</span></td>
            <td><span class="badge bg-light text-dark border">${ticket.piso || '-'}</span></td>
            <td><span class="badge ${estadoBadge}">${ticket.estado}</span></td>
            <td><span class="badge ${criticidadBadge}">${criticidad}</span></td>
            <td>${slaHtml}</td>
            <td>${evidenciaHtml}</td>
            <td style="max-width: 200px;" class="text-truncate" title="${ticket.comentario_tecnico || ''}">${ticket.comentario_tecnico || '-'}</td>
            <td>
                <button class="btn btn-sm btn-primary badge-custom" onclick="abrirModalGestion(${ticket.id}, '${ticket.estado}', '${ticket.comentario_tecnico ? ticket.comentario_tecnico.replace(/'/g, "\\'") : ''}')">
                    <i class="bi bi-pencil-square"></i> Gestionar
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Crucial (HU17): Inicializar popovers de Bootstrap inmediatamente tras inyectar las filas en el DOM
    const popoverTriggerList = tbody.querySelectorAll('[data-bs-toggle="popover"]');
    popoverTriggerList.forEach(popoverTriggerEl => {
        new bootstrap.Popover(popoverTriggerEl, {
            trigger: 'hover focus',
            container: 'body'
        });
    });

    // Crucial (HU18): Inicializar temporizadores SLA de cuenta regresiva inmediatamente tras inyectar las filas en el DOM
    iniciarTemporizadoresSLA();
}

// ==========================================
// HU18: Motor de Cuenta Regresiva SLA en Tiempo Real
// ==========================================
function actualizarTemporizadoresSLA() {
    const timers = document.querySelectorAll('.sla-timer');
    const ahora = new Date();

    timers.forEach(timer => {
        const estado = (timer.getAttribute('data-estado') || '').trim();
        if (estado === 'Resuelto' || estado === 'Cerrado') {
            timer.textContent = 'Detenido';
            timer.className = 'sla-timer text-muted fw-semibold';
            timer.style.color = '';
            return;
        }

        const fechaCreacionStr = timer.getAttribute('data-fecha');
        if (!fechaCreacionStr) {
            timer.textContent = '-';
            timer.className = 'sla-timer text-muted small';
            timer.style.color = '';
            return;
        }

        const criticidad = timer.getAttribute('data-criticidad') || 'Medio';
        const horasSLA = SLA_TIEMPOS_HORAS[criticidad] || 72; // Alta: 24, Media: 72, Baja: 168

        const fechaCreacion = new Date(fechaCreacionStr);
        if (isNaN(fechaCreacion.getTime())) {
            timer.textContent = '-';
            timer.style.color = '';
            return;
        }

        const tiempoTotalMs = horasSLA * 3600000;
        const fechaLimite = new Date(fechaCreacion.getTime() + tiempoTotalMs);
        const diferenciaMs = fechaLimite.getTime() - ahora.getTime();
        const tiempoTranscurridoMs = ahora.getTime() - fechaCreacion.getTime();
        const porcentajeTranscurrido = (tiempoTranscurridoMs / tiempoTotalMs) * 100;

        if (diferenciaMs <= 0 || porcentajeTranscurrido >= 100) {
            // Si el tiempo venció o superó el 100%: Rojo (danger)
            timer.innerHTML = '<strong>Vencido</strong>';
            timer.className = 'sla-timer badge bg-danger text-white shadow-sm';
            timer.style.color = '';
            return;
        }

        timer.style.color = '';
        const totalMinutos = Math.floor(diferenciaMs / 60000);
        const totalHoras = Math.floor(totalMinutos / 60);
        const dias = Math.floor(totalHoras / 24);
        const horasRestantes = totalHoras % 24;
        const minutosRestantes = totalMinutos % 60;

        let textoTiempo = '';
        if (dias > 0) {
            textoTiempo = `${dias}d ${horasRestantes}h`;
        } else if (totalHoras > 0) {
            textoTiempo = `${totalHoras}h ${minutosRestantes}m`;
        } else {
            textoTiempo = `${minutosRestantes}m`;
        }

        // HU18: Nueva regla matemática de tercios:
        // Verde (success): Si ha transcurrido menos de un tercio (< 33.3%) del tiempo total.
        // Amarillo (warning): Si ha transcurrido entre un tercio y dos tercios (>= 33.3% y < 66.6%) del tiempo total.
        // Rojo (danger): Si ha transcurrido más de dos tercios (>= 66.6%) del tiempo total, o si ya está vencido.
        if (porcentajeTranscurrido < (100 / 3)) {
            // < 33.3% transcurrido -> Verde (success)
            timer.textContent = textoTiempo;
            timer.className = 'sla-timer badge bg-success bg-opacity-10 text-success border border-success border-opacity-25';
        } else if (porcentajeTranscurrido < (200 / 3)) {
            // >= 33.3% y < 66.6% transcurrido -> Amarillo (warning)
            timer.textContent = textoTiempo;
            timer.className = 'sla-timer badge bg-warning bg-opacity-10 text-warning border border-warning border-opacity-25 text-dark';
        } else {
            // >= 66.6% transcurrido -> Rojo (danger)
            timer.textContent = textoTiempo;
            timer.className = 'sla-timer badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-25 fw-bold';
        }
    });
}

function iniciarTemporizadoresSLA() {
    if (slaIntervalId) {
        clearInterval(slaIntervalId);
    }
    // Ejecutar inmediatamente al inyectar filas
    actualizarTemporizadoresSLA();
    // Ejecutar cada 60000 ms (1 minuto)
    slaIntervalId = setInterval(actualizarTemporizadoresSLA, 60000);
}

function obtenerBadgeEstado(estado) {
    switch (estado) {
        case 'Abierto': return 'bg-secondary';
        case 'En Progreso': return 'bg-warning text-dark';
        case 'Resuelto': return 'bg-success';
        default: return 'bg-secondary';
    }
}

// Lógica del Modal
function abrirModalGestion(id, estadoActual, comentarioActual) {
    document.getElementById('modalTicketId').value = id;
    document.getElementById('modalTicketIdTitle').textContent = id;
    document.getElementById('modalEstado').value = estadoActual;
    document.getElementById('modalComentario').value = comentarioActual;

    const alerta = document.getElementById('modalAlert');
    alerta.classList.add('d-none');
    alerta.textContent = '';

    modalInstance.show();
}

async function guardarGestion() {
    const id = document.getElementById('modalTicketId').value;
    const estado = document.getElementById('modalEstado').value;
    const comentario = document.getElementById('modalComentario').value.trim();
    const alerta = document.getElementById('modalAlert');

    alerta.classList.add('d-none');

    if (estado === 'Resuelto') {
        if (!comentario || comentario.length < 10) {
            alerta.textContent = 'Si el estado es Resuelto, el comentario técnico debe tener al menos 10 caracteres.';
            alerta.classList.remove('d-none');
            return;
        }
    }

    const body = { estado: estado };
    if (comentario !== "") {
        body.comentario_tecnico = comentario;
    }

    try {
        const response = await fetch(`${API_URL}/tickets/${id}/estado`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            let errorMsg = 'Error al actualizar el ticket.';
            if (response.status === 400) {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorMsg;
            }
            alerta.textContent = errorMsg;
            alerta.classList.remove('d-none');
            return;
        }

        modalInstance.hide();
        cargarTickets(); // Recargar la tabla y KPIs globalmente
    } catch (error) {
        console.error(error);
        alerta.textContent = 'Error de conexión con el servidor.';
        alerta.classList.remove('d-none');
    }
}

// Carga de Video Tutorial
const formCargarVideoEl = document.getElementById('formCargarVideo');
if (formCargarVideoEl) {
    formCargarVideoEl.addEventListener('submit', async function (event) {
        event.preventDefault(); 

        const datosVideo = new FormData();
        datosVideo.append('titulo', document.getElementById('inputTituloVideo').value.trim());
        datosVideo.append('descripcion', document.getElementById('inputDescripcionVideo').value.trim());
        datosVideo.append('tags', document.getElementById('inputTagsVideo').value.trim());
        datosVideo.append('video_file', document.getElementById('inputUrlVideo').files[0]);

        try {
            const respuesta = await fetch(`${API_URL}/videos/`, {
                method: 'POST',
                body: datosVideo
            });

            if (respuesta.ok) {
                const videoGuardado = await respuesta.json();
                alert(`¡Éxito! El video "${videoGuardado.titulo}" fue guardado correctamente en la Base de Conocimiento.`);
                formCargarVideoEl.reset();
                
                // Volver al dashboard y limpiar vista (Opcional)
                switchView('dashboard');
            } else {
                const errorData = await respuesta.json();
                console.error('Error del servidor:', errorData);
                alert('Hubo un error al intentar guardar el video. Revisa la consola para más detalles.');
            }
        } catch (error) {
            console.error('Error de red:', error);
            alert('No se pudo conectar con el servidor de HelpStream. Verifica que el backend esté ejecutándose.');
        }
    });
}

// ==========================================
// HU20: Lógica del Dashboard Gerencial & Reportes Ejecutivos
// Vista exclusiva para Jefatura de TI (Protegida con 403 en API)
// ==========================================
let allGerencialTickets = [];
let modalAuditoriaInstance = null;

async function inicializarDashboardGerencial() {
    const modalEl = document.getElementById('modalAuditoriaTicket');
    if (modalEl && typeof bootstrap !== 'undefined') {
        modalAuditoriaInstance = new bootstrap.Modal(modalEl);
    }

    // Actualizar nombre, rol e iniciales dinámicamente en cabecera
    actualizarDatosNavbar();

    // Configurar listeners de filtros
    const inputBuscar = document.getElementById('filtroBuscarTexto');
    const selectSede = document.getElementById('filtroSede');
    const selectCrit = document.getElementById('filtroCriticidad');
    const selectEstado = document.getElementById('filtroEstado');
    const btnRecargar = document.getElementById('btnRecargarDashboard');
    const btnExportar = document.getElementById('btnExportarCSV');
    const btnExportarExcel = document.getElementById('btnExportarExcel');

    if (inputBuscar) inputBuscar.addEventListener('input', filtrarReportesGerenciales);
    if (selectSede) selectSede.addEventListener('change', filtrarReportesGerenciales);
    if (selectCrit) selectCrit.addEventListener('change', filtrarReportesGerenciales);
    if (selectEstado) selectEstado.addEventListener('change', filtrarReportesGerenciales);

    if (btnRecargar) {
        btnRecargar.addEventListener('click', () => {
            btnRecargar.disabled = true;
            btnRecargar.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Actualizando...';
            cargarReportesGerenciales().finally(() => {
                btnRecargar.disabled = false;
                btnRecargar.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i> Actualizar Métricas';
            });
        });
    }

    if (btnExportar) {
        btnExportar.addEventListener('click', exportarReportesCSV);
    }

    if (btnExportarExcel) {
        btnExportarExcel.addEventListener('click', exportarReportesExcel);
    }

    // Configuración de controles del Módulo HelpStream Analytics (HU15)
    const btnFiltrarAnalytics = document.getElementById('btnAplicarFiltrosAnalytics');
    const selectAnioAnalytics = document.getElementById('analyticsSelectAnio');
    const btnResetAnalytics = document.getElementById('btnResetFiltrosAnalytics');

    if (btnFiltrarAnalytics) {
        btnFiltrarAnalytics.addEventListener('click', cargarAnalyticsDashboard);
    }

    if (selectAnioAnalytics) {
        selectAnioAnalytics.addEventListener('change', cargarAnalyticsDashboard);
    }

    if (btnResetAnalytics) {
        btnResetAnalytics.addEventListener('click', () => {
            const fi = document.getElementById('analyticsFechaInicio');
            const ff = document.getElementById('analyticsFechaFin');
            if (fi) fi.value = '';
            if (ff) ff.value = '';
            if (selectAnioAnalytics) selectAnioAnalytics.value = '';
            cargarAnalyticsDashboard();
        });
    }

    // Si la URL solicita Analytics (#view-analytics o #analytics), cambiar de vista
    if (window.location.hash === '#view-analytics' || window.location.hash === '#analytics') {
        cambiarVistaGerencial('analytics');
    }

    await cargarReportesGerenciales();
}

async function cargarReportesGerenciales() {
    const alertBox = document.getElementById('gerencialAlert');
    const alertMsg = document.getElementById('gerencialAlertMsg');
    const token = localStorage.getItem('helpstream_token');

    try {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(ENDPOINTS.REPORTES_DASHBOARD, { headers });

        if (response.status === 403) {
            const errData = await response.json().catch(() => ({}));
            const mensaje = errData.detail || 'Acceso denegado exclusivo para Jefatura';
            if (alertBox && alertMsg) {
                alertMsg.textContent = `${mensaje}. Redirigiendo a su portal operativo...`;
                alertBox.className = 'alert alert-danger mb-4 py-2 px-3 small';
                alertBox.classList.remove('d-none');
            }
            alert(mensaje);
            window.location.replace('index.html');
            return;
        }

        if (!response.ok) {
            throw new Error(`Error en servidor (${response.status})`);
        }

        const data = await response.json();
        allGerencialTickets = data.tickets || [];

        // 1. Actualizar KPIs Principales
        const kpis = data.kpis || {};
        const slaPct = kpis.cumplimiento_sla_porcentaje !== undefined ? kpis.cumplimiento_sla_porcentaje : 100;
        
        const elSla = document.getElementById('kpiSlaPorcentaje');
        if (elSla) elSla.textContent = `${slaPct}%`;
        
        const elSlaBar = document.getElementById('kpiSlaProgressBar');
        if (elSlaBar) {
            elSlaBar.style.width = `${slaPct}%`;
            elSlaBar.setAttribute('aria-valuenow', slaPct);
        }

        const elSlaSub = document.getElementById('kpiSlaSubtext');
        if (elSlaSub) {
            elSlaSub.textContent = `${kpis.tickets_dentro_sla || 0} dentro de tiempo (${kpis.tickets_vencidos_sla || 0} vencidos)`;
        }

        const elTotal = document.getElementById('kpiTotalTickets');
        if (elTotal) elTotal.textContent = kpis.total_tickets || 0;

        const elAbiertos = document.getElementById('kpiAbiertos');
        if (elAbiertos) elAbiertos.textContent = `${kpis.abiertos || 0} Abiertos`;
        const elEnProg = document.getElementById('kpiEnProgreso');
        if (elEnProg) elEnProg.textContent = `${kpis.en_progreso || 0} En Progreso`;
        const elResueltos = document.getElementById('kpiResueltos');
        if (elResueltos) elResueltos.textContent = `${kpis.resueltos || 0} Resueltos`;

        const elCriticos = document.getElementById('kpiCriticosPendientes');
        if (elCriticos) elCriticos.textContent = kpis.criticos_pendientes || 0;

        const elAutoatencion = document.getElementById('kpiAutoatencion');
        if (elAutoatencion) elAutoatencion.textContent = kpis.autoatencion_resueltos || 0;

        // 2. Tasa de resolución
        const tasaRes = kpis.tasa_resolucion_porcentaje || 0;
        const elTasaRes = document.getElementById('kpiTasaResolucion');
        if (elTasaRes) elTasaRes.textContent = `${tasaRes}%`;
        const elTasaBar = document.getElementById('barTasaResolucion');
        if (elTasaBar) elTasaBar.style.width = `${tasaRes}%`;

        const elResumenR = document.getElementById('resumenResueltos');
        if (elResumenR) elResumenR.textContent = kpis.resueltos || 0;
        const elResumenP = document.getElementById('resumenEnProgreso');
        if (elResumenP) elResumenP.textContent = kpis.en_progreso || 0;
        const elResumenA = document.getElementById('resumenAbiertos');
        if (elResumenA) elResumenA.textContent = kpis.abiertos || 0;

        // 3. Distribución por Criticidad
        const total = kpis.total_tickets || 1;
        const distCrit = (data.distribucion && data.distribucion.por_criticidad) ? data.distribucion.por_criticidad : {};
        const cAlta = distCrit.Alta || 0;
        const cMedia = distCrit.Media || 0;
        const cBaja = distCrit.Baja || 0;

        const pctAlta = Math.round((cAlta / total) * 100);
        const pctMedia = Math.round((cMedia / total) * 100);
        const pctBaja = Math.round((cBaja / total) * 100);

        const elCritAlta = document.getElementById('distCritAlta');
        if (elCritAlta) elCritAlta.textContent = `${cAlta} (${pctAlta}%)`;
        const elCritAltaBar = document.getElementById('distCritAltaBar');
        if (elCritAltaBar) elCritAltaBar.style.width = `${pctAlta}%`;

        const elCritMedia = document.getElementById('distCritMedia');
        if (elCritMedia) elCritMedia.textContent = `${cMedia} (${pctMedia}%)`;
        const elCritMediaBar = document.getElementById('distCritMediaBar');
        if (elCritMediaBar) elCritMediaBar.style.width = `${pctMedia}%`;

        const elCritBaja = document.getElementById('distCritBaja');
        if (elCritBaja) elCritBaja.textContent = `${cBaja} (${pctBaja}%)`;
        const elCritBajaBar = document.getElementById('distCritBajaBar');
        if (elCritBajaBar) elCritBajaBar.style.width = `${pctBaja}%`;

        // 4. Distribución por Sedes y poblar select
        const distSedes = (data.distribucion && data.distribucion.por_sede) ? data.distribucion.por_sede : {};
        const listaSedesEl = document.getElementById('listaDistribucionSedes');
        const selectSede = document.getElementById('filtroSede');

        if (listaSedesEl) {
            listaSedesEl.innerHTML = '';
            const sedesKeys = Object.keys(distSedes);
            if (sedesKeys.length === 0) {
                listaSedesEl.innerHTML = '<span class="text-muted small">No hay sedes registradas.</span>';
            } else {
                sedesKeys.forEach(sedeNombre => {
                    const cnt = distSedes[sedeNombre];
                    const item = document.createElement('div');
                    item.className = 'd-flex justify-content-between align-items-center p-2 rounded bg-light border';
                    item.innerHTML = `
                        <span class="fw-semibold text-truncate" style="max-width: 75%;"><i class="bi bi-geo-alt text-danger me-1"></i> ${sedeNombre}</span>
                        <span class="badge bg-secondary">${cnt} tickets</span>
                    `;
                    listaSedesEl.appendChild(item);
                });
            }
        }

        if (selectSede) {
            const currentVal = selectSede.value;
            selectSede.innerHTML = '<option value="">Todas las Sedes</option>';
            Object.keys(distSedes).forEach(sedeNombre => {
                if (sedeNombre && sedeNombre !== 'Sin Sede Asignada') {
                    const opt = document.createElement('option');
                    opt.value = sedeNombre;
                    opt.textContent = sedeNombre;
                    selectSede.appendChild(opt);
                }
            });
            selectSede.value = currentVal;
        }

        // 5. Renderizar Tabla de Reportes
        filtrarReportesGerenciales();

        if (alertBox) alertBox.classList.add('d-none');
    } catch (error) {
        console.error('Error al cargar reportes gerenciales:', error);
        if (alertBox && alertMsg) {
            alertMsg.textContent = 'Error al cargar los datos del dashboard gerencial desde la API.';
            alertBox.className = 'alert alert-danger mb-4 py-2 px-3 small';
            alertBox.classList.remove('d-none');
        }
    }
}

function filtrarReportesGerenciales() {
    const txtBuscar = (document.getElementById('filtroBuscarTexto') ? document.getElementById('filtroBuscarTexto').value : '').toLowerCase().trim();
    const sede = document.getElementById('filtroSede') ? document.getElementById('filtroSede').value : '';
    const criticidad = document.getElementById('filtroCriticidad') ? document.getElementById('filtroCriticidad').value : '';
    const estado = document.getElementById('filtroEstado') ? document.getElementById('filtroEstado').value : '';

    const filtrados = allGerencialTickets.filter(t => {
        if (sede && (t.sede || '').toLowerCase() !== sede.toLowerCase()) return false;
        if (criticidad && (t.criticidad || '').toLowerCase() !== criticidad.toLowerCase()) return false;
        if (estado && (t.estado || '').toLowerCase() !== estado.toLowerCase()) return false;

        if (txtBuscar) {
            const idMatch = String(t.id).includes(txtBuscar);
            const descMatch = (t.descripcion || '').toLowerCase().includes(txtBuscar);
            const solicitanteMatch = (t.solicitante || '').toLowerCase().includes(txtBuscar);
            const correoMatch = (t.correo_solicitante || '').toLowerCase().includes(txtBuscar);
            const sedeMatch = (t.sede || '').toLowerCase().includes(txtBuscar);
            if (!idMatch && !descMatch && !solicitanteMatch && !correoMatch && !sedeMatch) return false;
        }

        return true;
    });

    const badgeTotal = document.getElementById('totalFiltradosBadge');
    if (badgeTotal) badgeTotal.textContent = `Mostrando ${filtrados.length} de ${allGerencialTickets.length} tickets`;

    renderizarTablaReportes(filtrados);
}

function renderizarTablaReportes(tickets) {
    const tbody = document.getElementById('tablaReportesBody');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-4 text-muted">No se encontraron tickets con los filtros seleccionados.</td></tr>';
        return;
    }

    tickets.forEach(t => {
        const tr = document.createElement('tr');

        // Estado SLA Badge (Regla de Tercios HU18)
        let badgeSlaHtml = '';
        if (t.estado === 'Resuelto' || t.estado_sla === 'Cumplido') {
            badgeSlaHtml = '<span class="badge-sla-cumplido"><i class="bi bi-check-circle-fill me-1"></i> Cumplido</span>';
        } else if (t.estado_sla === 'Vencido' || (t.horas_restantes !== undefined && t.horas_restantes <= 0)) {
            badgeSlaHtml = '<span class="badge-sla-vencido"><i class="bi bi-x-circle-fill me-1"></i> Vencido</span>';
        } else if (t.color_sla === 'danger' || t.estado_sla === 'En Riesgo') {
            badgeSlaHtml = `<span class="badge-sla-vencido"><i class="bi bi-exclamation-octagon-fill me-1"></i> En Riesgo (${t.horas_restantes}h)</span>`;
        } else if (t.color_sla === 'warning' || t.estado_sla === 'En Atención') {
            badgeSlaHtml = `<span class="badge-sla-advertencia"><i class="bi bi-exclamation-triangle-fill me-1"></i> En Atención (${t.horas_restantes}h)</span>`;
        } else {
            badgeSlaHtml = `<span class="badge-sla-normal"><i class="bi bi-clock-fill me-1"></i> ${t.horas_restantes}h restantes</span>`;
        }

        // Criticidad Badge
        let critBadge = '<span class="badge bg-warning bg-opacity-10 text-warning border border-warning border-opacity-25">Media</span>';
        if (t.criticidad === 'Alta') {
            critBadge = '<span class="badge bg-danger bg-opacity-10 text-danger border border-danger border-opacity-25 fw-bold">Alta</span>';
        } else if (t.criticidad === 'Baja') {
            critBadge = '<span class="badge bg-info bg-opacity-10 text-info border border-info border-opacity-25">Baja</span>';
        }

        // Estado Ticket Badge
        let estadoBadge = '<span class="badge bg-secondary">Abierto</span>';
        if (t.estado === 'En Progreso') {
            estadoBadge = '<span class="badge bg-warning text-dark">En Progreso</span>';
        } else if (t.estado === 'Resuelto') {
            estadoBadge = '<span class="badge bg-success">Resuelto</span>';
        }

        // Fecha creación formateada en Hora de Lima
        let fechaStr = '-';
        if (t.fecha_creacion) {
            try {
                const f = new Date(t.fecha_creacion);
                if (!isNaN(f.getTime())) {
                    fechaStr = f.toLocaleDateString('es-PE', {
                        timeZone: 'America/Lima',
                        day: '2-digit',
                        month: '2-digit',
                        year: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    });
                } else {
                    fechaStr = t.fecha_creacion;
                }
            } catch (e) {
                fechaStr = t.fecha_creacion;
            }
        }

        // Ubicación
        const ubicacionStr = t.piso && t.piso !== '-' ? `${t.sede} (${t.piso})` : t.sede;

        tr.innerHTML = `
            <td class="fw-bold" style="color: var(--admin-anthracite);">#${t.id}</td>
            <td>
                <div class="fw-semibold">${t.solicitante || 'Usuario'}</div>
                <small class="text-muted">${t.correo_solicitante || '-'}</small>
                ${(t.telefono || t.anexo) ? `<div><span class="badge bg-light text-dark border small" style="font-size: 0.68rem;"><i class="bi bi-telephone me-1"></i>${t.telefono || '-'} (Anexo: ${t.anexo || '-'})</span></div>` : ''}
            </td>
            <td>
                <span class="small fw-semibold text-secondary"><i class="bi bi-geo-alt me-1"></i>${ubicacionStr}</span>
            </td>
            <td>${critBadge}</td>
            <td>${estadoBadge}</td>
            <td>${badgeSlaHtml}</td>
            <td class="small text-muted">${fechaStr}</td>
            <td class="text-center">
                <button class="btn btn-sm btn-outline-burnt-orange rounded-pill px-3" onclick="abrirModalAuditoria(${t.id})">
                    <i class="bi bi-search"></i> Auditar
                </button>
            </td>
        `;

        tbody.appendChild(tr);
    });
}

function abrirModalAuditoria(ticketId) {
    const t = allGerencialTickets.find(item => item.id === ticketId);
    if (!t) return;

    const elId = document.getElementById('auditTicketId');
    if (elId) elId.textContent = t.id;

    const elSol = document.getElementById('auditSolicitante');
    if (elSol) elSol.textContent = t.solicitante || 'Usuario Solicitante';

    const elCorreo = document.getElementById('auditCorreo');
    if (elCorreo) elCorreo.textContent = t.correo_solicitante || '-';

    const elBadges = document.getElementById('auditContactoBadges');
    if (elBadges) {
        elBadges.innerHTML = `
            <span class="badge bg-light text-dark border me-1"><i class="bi bi-telephone-fill text-muted me-1"></i>${t.telefono || 'Sin teléfono'}</span>
            <span class="badge bg-light text-dark border"><i class="bi bi-building text-muted me-1"></i>Anexo: ${t.anexo || '-'}</span>
        `;
    }

    const elUbi = document.getElementById('auditUbicacion');
    if (elUbi) elUbi.textContent = t.sede || 'No especificada';

    const elPiso = document.getElementById('auditPiso');
    if (elPiso) elPiso.textContent = t.piso ? `Área/Piso: ${t.piso}` : 'Piso: No aplica / No especificado';

    const elCrit = document.getElementById('auditCriticidad');
    if (elCrit) elCrit.innerHTML = `<span class="badge bg-dark">${t.criticidad} (Límite: ${t.sla_limite_horas}h)</span>`;

    const elEst = document.getElementById('auditEstado');
    if (elEst) elEst.innerHTML = `<span class="badge bg-primary">${t.estado}</span>`;

    const elSla = document.getElementById('auditSla');
    if (elSla) {
        if (t.estado === 'Resuelto' || t.estado_sla === 'Cumplido') {
            elSla.innerHTML = '<span class="badge-sla-cumplido"><i class="bi bi-check-circle-fill me-1"></i> Cumplido en tiempo</span>';
        } else if (t.estado_sla === 'Vencido' || (t.horas_restantes !== undefined && t.horas_restantes <= 0)) {
            elSla.innerHTML = '<span class="badge-sla-vencido"><i class="bi bi-x-circle-fill me-1"></i> Vencido fuera de SLA</span>';
        } else if (t.color_sla === 'danger' || t.estado_sla === 'En Riesgo') {
            elSla.innerHTML = `<span class="badge-sla-vencido"><i class="bi bi-exclamation-octagon-fill me-1"></i> En Riesgo (${t.horas_restantes}h restantes)</span>`;
        } else if (t.color_sla === 'warning' || t.estado_sla === 'En Atención') {
            elSla.innerHTML = `<span class="badge-sla-advertencia"><i class="bi bi-exclamation-triangle-fill me-1"></i> En Atención (${t.horas_restantes}h restantes)</span>`;
        } else {
            elSla.innerHTML = `<span class="badge-sla-normal"><i class="bi bi-clock-fill me-1"></i> ${t.horas_restantes} horas restantes</span>`;
        }
    }

    const elDesc = document.getElementById('auditDescripcion');
    if (elDesc) elDesc.textContent = t.descripcion || 'Sin descripción detallada.';

    const elCom = document.getElementById('auditComentarios');
    if (elCom) {
        if (t.es_autoatencion) {
            elCom.innerHTML = `<span class="badge bg-info text-dark mb-1"><i class="bi bi-play-circle-fill me-1"></i> Resuelto con Microaprendizaje</span><p class="mb-0">El usuario resolvió el incidente utilizando los videos tutoriales de la Base de Conocimiento.</p>`;
        } else {
            elCom.textContent = t.comentario_tecnico || 'Sin comentarios técnicos registrados por el analista aún.';
        }
    }

    if (modalAuditoriaInstance) {
        modalAuditoriaInstance.show();
    }
}

function exportarReportesCSV() {
    if (!allGerencialTickets || allGerencialTickets.length === 0) {
        alert('No hay datos disponibles para exportar.');
        return;
    }

    const encabezados = ['ID', 'Solicitante', 'Correo', 'Telefono', 'Anexo', 'Sede', 'Piso', 'Criticidad', 'Estado', 'Estado_SLA', 'Horas_Restantes', 'Fecha_Creacion', 'Descripcion'];
    const filas = allGerencialTickets.map(t => [
        t.id,
        `"${(t.solicitante || '').replace(/"/g, '""')}"`,
        `"${(t.correo_solicitante || '').replace(/"/g, '""')}"`,
        `"${(t.telefono || '').replace(/"/g, '""')}"`,
        `"${(t.anexo || '').replace(/"/g, '""')}"`,
        `"${(t.sede || '').replace(/"/g, '""')}"`,
        `"${(t.piso || '').replace(/"/g, '""')}"`,
        t.criticidad,
        t.estado,
        t.estado_sla,
        t.horas_restantes,
        t.fecha_creacion,
        `"${(t.descripcion || '').replace(/"/g, '""')}"`
    ]);

    const csvContent = '\uFEFF' + [encabezados.join(','), ...filas.map(f => f.join(','))].join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `HelpStream_Reporte_Ejecutivo_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// ==========================================
// HU15.3: Exportación Nativa a Excel (.xlsx)
// Consume el endpoint protegido /api/reportes/exportar/excel enviando el token JWT en las cabeceras
// ==========================================
async function exportarReportesExcel() {
    const token = localStorage.getItem('helpstream_token');
    if (!token) {
        alert('Sesión no válida o expirada. Por favor inicie sesión nuevamente.');
        window.location.replace('login.html');
        return;
    }

    const btnExcel = document.getElementById('btnExportarExcel');
    const originalContent = btnExcel ? btnExcel.innerHTML : '<i class="bi bi-file-earmark-excel-fill me-1"></i> Exportar Excel';

    if (btnExcel) {
        btnExcel.disabled = true;
        btnExcel.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Descargando...';
    }

    try {
        let urlEndpoint = (typeof ENDPOINTS !== 'undefined' && ENDPOINTS.REPORTES_EXCEL)
            ? ENDPOINTS.REPORTES_EXCEL
            : `${API_URL}/api/reportes/exportar/excel`;

        // HU15.3: Enviar parámetros de fecha actuales si están definidos en los controles
        const fi = document.getElementById('analyticsFechaInicio')?.value;
        const ff = document.getElementById('analyticsFechaFin')?.value;
        const params = new URLSearchParams();
        if (fi) params.append('fecha_inicio', fi);
        if (ff) params.append('fecha_fin', ff);
        if (params.toString()) {
            urlEndpoint += (urlEndpoint.includes('?') ? '&' : '?') + params.toString();
        }

        const response = await fetch(urlEndpoint, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            if (response.status === 401) {
                alert('Sesión expirada o no autorizada. Redirigiendo a inicio de sesión...');
                window.location.replace('login.html');
                return;
            } else if (response.status === 403) {
                alert('Acceso denegado exclusivo para Jefatura de TI.');
                return;
            } else {
                throw new Error(`Error en el servidor al generar el Excel (código ${response.status})`);
            }
        }

        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.setAttribute('download', 'reporte_incidencias.xlsx');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(downloadUrl);
    } catch (error) {
        console.error('Error al exportar a Excel:', error);
        alert('Ocurrió un error al descargar el archivo Excel. Por favor verifique la conexión o intente nuevamente.');
    } finally {
        if (btnExcel) {
            btnExcel.disabled = false;
            btnExcel.innerHTML = originalContent;
        }
    }
}

// ==========================================
// HU15: Lógica del Módulo HelpStream Analytics
// Métricas Dinámicas, Chart.js, Heatmap y Resumen Mensual
// ==========================================

let chartSoporteVsAutoatencionInstance = null;
let chartTopIncidentesInstance = null;

function cambiarVistaGerencial(vista) {
    const viewGerencial = document.getElementById('view-gerencial');
    const viewAnalytics = document.getElementById('view-analytics');
    const navGerencial = document.getElementById('nav-gerencial');
    const navAnalytics = document.getElementById('nav-analytics');

    if (vista === 'analytics') {
        if (viewGerencial) viewGerencial.classList.add('d-none');
        if (viewAnalytics) viewAnalytics.classList.remove('d-none');
        if (navGerencial) navGerencial.classList.remove('active');
        if (navAnalytics) navAnalytics.classList.add('active');
        window.location.hash = '#view-analytics';
        cargarAnalyticsDashboard();
    } else {
        if (viewAnalytics) viewAnalytics.classList.add('d-none');
        if (viewGerencial) viewGerencial.classList.remove('d-none');
        if (navAnalytics) navAnalytics.classList.remove('active');
        if (navGerencial) navGerencial.classList.add('active');
        window.location.hash = '';
    }

    if (window.innerWidth < 992 && document.body.classList.contains('sidebar-open')) {
        toggleSidebar(false);
    }
}

async function cargarAnalyticsDashboard() {
    const token = localStorage.getItem('helpstream_token');
    if (!token) return;

    const alertBox = document.getElementById('analyticsAlert');
    const alertMsg = document.getElementById('analyticsAlertMsg');
    const btnFiltrar = document.getElementById('btnAplicarFiltrosAnalytics');

    const inputInicio = document.getElementById('analyticsFechaInicio');
    const inputFin = document.getElementById('analyticsFechaFin');
    const selectAnio = document.getElementById('analyticsSelectAnio');

    const fechaInicio = inputInicio ? inputInicio.value : '';
    const fechaFin = inputFin ? inputFin.value : '';
    const anio = selectAnio ? selectAnio.value : '';

    if (btnFiltrar) {
        btnFiltrar.disabled = true;
        btnFiltrar.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Actualizando...';
    }

    try {
        const params = new URLSearchParams();
        if (fechaInicio) params.append('fecha_inicio', fechaInicio);
        if (fechaFin) params.append('fecha_fin', fechaFin);
        if (anio) params.append('anio', anio);

        let url = `${ENDPOINTS.ANALYTICS_DASHBOARD || (API_URL + '/api/analytics/dashboard')}`;
        if (params.toString()) {
            url += `?${params.toString()}`;
        }

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            if (response.status === 403) {
                if (alertBox && alertMsg) {
                    alertBox.className = 'alert alert-danger mb-4 py-2 px-3 small';
                    alertMsg.textContent = 'Acceso denegado exclusivo para Jefatura de TI (403 Forbidden).';
                    alertBox.classList.remove('d-none');
                }
                return;
            }
            throw new Error(`Error en servidor: ${response.status}`);
        }

        const data = await response.json();

        // 1. Poblar select de años dinámicamente si no tiene opciones aún
        if (selectAnio && selectAnio.options.length <= 1 && data.anios_disponibles) {
            data.anios_disponibles.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a;
                opt.textContent = a;
                selectAnio.appendChild(opt);
            });
            if (data.filtros_aplicados && data.filtros_aplicados.anio && !selectAnio.value) {
                selectAnio.value = data.filtros_aplicados.anio;
            }
        }

        // 2. Actualizar tarjetas de KPIs
        const kpis = data.kpis || {};
        const elHoras = document.getElementById('kpiHorasAhorradas');
        const elSubHoras = document.getElementById('kpiSubtextHoras');
        const elMttr = document.getElementById('kpiMttr');
        const elFcr = document.getElementById('kpiFcr');
        const elReabiertos = document.getElementById('kpiReabiertos');
        const elSubReabiertos = document.getElementById('kpiSubtextReabiertos');

        if (elHoras) elHoras.textContent = `${kpis.horas_ahorradas ?? 0} hrs`;
        if (elSubHoras) elSubHoras.textContent = `Autoatención HU15.1 (${kpis.tickets_autoatencion ?? 0} tickets)`;
        if (elMttr) elMttr.textContent = `${kpis.mttr_horas ?? 0} hrs`;
        if (elFcr) elFcr.textContent = `${kpis.fcr_porcentaje ?? 0}%`;
        if (elReabiertos) elReabiertos.textContent = `${kpis.ratio_reabiertos_porcentaje ?? 0}%`;
        if (elSubReabiertos) elSubReabiertos.textContent = `${kpis.tickets_reabiertos ?? 0} tickets con reapertura`;

        // 3. Renderizar Gráficos con Chart.js
        if (data.graficos) {
            renderChartSoporteVsAutoatencion(data.graficos.soporte_vs_autoatencion);
            renderChartTopIncidentes(data.graficos.top_incidentes_recurrentes);
            renderMapaCalor(data.graficos.mapa_calor);
        }

        // 4. Renderizar Resumen Mensual
        if (data.resumen_mensual) {
            renderResumenMensual(data.resumen_mensual, data.filtros_aplicados?.anio);
        }

        if (alertBox) alertBox.classList.add('d-none');
    } catch (err) {
        console.error('Error al cargar HelpStream Analytics:', err);
        if (alertBox && alertMsg) {
            alertBox.className = 'alert alert-danger mb-4 py-2 px-3 small';
            alertMsg.textContent = 'No se pudieron sincronizar las métricas dinámicas de Analytics.';
            alertBox.classList.remove('d-none');
        }
    } finally {
        if (btnFiltrar) {
            btnFiltrar.disabled = false;
            btnFiltrar.innerHTML = '<i class="bi bi-funnel-fill me-1"></i> Aplicar Filtros';
        }
    }
}

function renderChartSoporteVsAutoatencion(serieData) {
    const canvas = document.getElementById('chartSoporteVsAutoatencion');
    if (!canvas || typeof Chart === 'undefined') return;

    if (chartSoporteVsAutoatencionInstance) {
        chartSoporteVsAutoatencionInstance.destroy();
        chartSoporteVsAutoatencionInstance = null;
    }

    const labels = serieData ? serieData.labels : [];
    const soporte = serieData ? serieData.soporte_tecnico : [];
    const autoatencion = serieData ? serieData.autoatencion : [];

    chartSoporteVsAutoatencionInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Soporte Técnico',
                    data: soporte,
                    backgroundColor: '#d35400',
                    borderColor: '#b84500',
                    borderWidth: 1,
                    borderRadius: 6
                },
                {
                    label: 'Autoatención (HU15.1/2)',
                    data: autoatencion,
                    backgroundColor: '#107c41',
                    borderColor: '#0b5a2f',
                    borderWidth: 1,
                    borderRadius: 6
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 14,
                        font: { family: 'Inter', weight: 600 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} incidencias`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false }
                },
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 },
                    grid: { color: 'rgba(0,0,0,0.05)' }
                }
            }
        }
    });
}

function renderChartTopIncidentes(topData) {
    const canvas = document.getElementById('chartTopIncidentes');
    if (!canvas || typeof Chart === 'undefined') return;

    if (chartTopIncidentesInstance) {
        chartTopIncidentesInstance.destroy();
        chartTopIncidentesInstance = null;
    }

    const items = topData || [];
    const labels = items.map(i => i.categoria);
    const dataVals = items.map(i => i.total);

    const colors = [
        '#d35400',
        '#22272e',
        '#107c41',
        '#e67e22',
        '#57606a'
    ];

    chartTopIncidentesInstance = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: dataVals,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: { size: 11, family: 'Inter' }
                    }
                }
            },
            cutout: '62%'
        }
    });
}

function renderMapaCalor(mapaData) {
    const headerRow = document.getElementById('heatmapHeaderRow');
    const tbody = document.getElementById('heatmapBody');
    if (!headerRow || !tbody || !mapaData) return;

    headerRow.innerHTML = '<th style="min-width: 110px;">Día</th>';
    mapaData.rangos.forEach(rango => {
        const th = document.createElement('th');
        th.textContent = rango;
        headerRow.appendChild(th);
    });

    tbody.innerHTML = '';
    const maxVal = mapaData.max_valor || 1;

    mapaData.datos.forEach(item => {
        const tr = document.createElement('tr');
        const tdDia = document.createElement('td');
        tdDia.className = 'fw-bold text-start ps-3';
        tdDia.style.color = 'var(--admin-anthracite)';
        tdDia.textContent = item.dia;
        tr.appendChild(tdDia);

        item.valores.forEach((val, idx) => {
            const td = document.createElement('td');
            const rangoNombre = mapaData.rangos[idx];
            td.className = 'heatmap-cell';

            if (val > 0) {
                const ratio = Math.min(1, val / maxVal);
                const bgAlpha = (0.15 + (ratio * 0.85)).toFixed(2);
                td.style.backgroundColor = `rgba(211, 84, 0, ${bgAlpha})`;
                td.style.color = ratio > 0.45 ? '#ffffff' : 'var(--admin-anthracite)';
                td.textContent = val;
            } else {
                td.style.backgroundColor = '#fbfcfd';
                td.style.color = '#94a3b8';
                td.textContent = '0';
            }

            td.setAttribute('title', `${item.dia} (${rangoNombre}): ${val} tickets`);
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });
}

function renderResumenMensual(resumenData, anio) {
    const tbody = document.getElementById('resumenMensualBody');
    const badgeAnio = document.getElementById('badgeAnioResumen');
    if (badgeAnio && anio) {
        badgeAnio.textContent = `Año ${anio}`;
    }
    if (!tbody || !resumenData) return;

    tbody.innerHTML = '';
    if (resumenData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No hay datos mensuales registrados para el año seleccionado.</td></tr>';
        return;
    }

    resumenData.forEach(m => {
        const tr = document.createElement('tr');

        let slaBadgeClass = 'badge bg-success';
        if (m.cumplimiento_sla_porcentaje < 75) {
            slaBadgeClass = 'badge bg-danger';
        } else if (m.cumplimiento_sla_porcentaje < 90) {
            slaBadgeClass = 'badge bg-warning text-dark';
        }

        tr.innerHTML = `
            <td class="fw-semibold">${m.mes}</td>
            <td class="text-center text-muted">${m.anio}</td>
            <td class="text-center fw-bold">${m.total_atenciones}</td>
            <td class="text-center text-success fw-bold">${m.incidentes_resueltos}</td>
            <td class="text-center">
                <span class="${slaBadgeClass} px-2 py-1">${m.cumplimiento_sla_porcentaje}%</span>
            </td>
            <td class="text-center text-burnt-orange fw-bold">${m.horas_ahorradas} hrs</td>
        `;
        tbody.appendChild(tr);
    });
}

