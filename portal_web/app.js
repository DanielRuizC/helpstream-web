// ==========================================
// Protección de Rutas (HU21)
// Redirige a login.html si no existe helpstream_token en localStorage
// ==========================================
(function protegerRuta() {
    const token = localStorage.getItem('helpstream_token');
    const path = window.location.pathname;
    const esLogin = path.endsWith('login.html') || path.endsWith('/login');

    if (!token && !esLogin) {
        window.location.replace('login.html');
    }
})();

// URL base de producción en Render
const API_URL = 'https://helpstream-api.onrender.com';

// Endpoints centralizados de la API
const ENDPOINTS = {
    LOGIN_LOCAL: `${API_URL}/api/auth/login/local`, // HU21: Endpoint de inicio de sesión local con JWT
    REGISTRO: `${API_URL}/api/auth/registro`,       // Endpoint de registro con asignación de rol
    ROLES: `${API_URL}/api/auth/roles`,             // Lista de roles del sistema
    USUARIOS: `${API_URL}/api/auth/usuarios`,       // Lista y gestión de usuarios
    TICKETS: `${API_URL}/tickets/`,
    VIDEOS: `${API_URL}/videos/`
};

let modalInstance = null;
let allTickets = []; // Global state for client-side filtering

// ==========================================
// HU21: Flujo de Autenticación / Inicio de Sesión
// Endpoint: https://helpstream-api.onrender.com/api/auth/login/local
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
        if (data.access_token) {
            localStorage.setItem('helpstream_token', data.access_token);
            localStorage.setItem('helpstream_token_type', data.token_type || 'bearer');
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
    window.location.replace('login.html');
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
                // Redirigir a index.html tras inicio de sesión exitoso
                window.location.href = 'index.html';
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
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger py-4">Error al cargar usuarios desde el servidor.</td></tr>';
    }
}

document.addEventListener("DOMContentLoaded", () => {
    // Si estamos en login.html
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        inicializarLogin(loginForm);
        return;
    }

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
        document.getElementById('ticketsBody').innerHTML = '<tr><td colspan="11" class="text-center text-danger">Error al cargar datos</td></tr>';
    }
}

// Calcular KPIs
function calcularMetricas(tickets) {
    let abiertos = 0;
    let resueltos = 0;
    let nuevosHoy = 0;
    
    const hoy = new Date();
    const formatoHoy = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`;

    tickets.forEach(t => {
        // Abiertos vs Resueltos
        if (t.estado === 'Resuelto') {
            resueltos++;
        } else {
            abiertos++;
        }
        
        // Tickets de Hoy
        if (t.fecha_creacion) {
            // Asume formato "YYYY-MM-DDTHH:MM:SS"
            const fechaTicket = t.fecha_creacion.split('T')[0];
            if (fechaTicket === formatoHoy) {
                nuevosHoy++;
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
        tbody.innerHTML = '<tr><td colspan="11" class="text-center text-muted py-4">No se encontraron tickets con los filtros actuales.</td></tr>';
        return;
    }

    tickets.forEach(ticket => {
        // Formatear Fecha
        let fechaFormatted = '-';
        if (ticket.fecha_creacion) {
            const d = new Date(ticket.fecha_creacion);
            fechaFormatted = `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
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
document.getElementById('formCargarVideo').addEventListener('submit', async function (event) {
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
            document.getElementById('formCargarVideo').reset();
            
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
