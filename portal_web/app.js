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

document.addEventListener("DOMContentLoaded", () => {
    // Si estamos en login.html
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        inicializarLogin(loginForm);
        return;
    }

    // Inicialización del Dashboard (index.html)
    const modalEl = document.getElementById('gestionarModal');
    if (modalEl) {
        modalInstance = new bootstrap.Modal(modalEl);
    }
    cargarTickets();
    inicializarSidebar();
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
        document.getElementById('ticketsBody').innerHTML = '<tr><td colspan="9" class="text-center text-danger">Error al cargar datos</td></tr>';
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
    tbody.innerHTML = '';

    if (tickets.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">No se encontraron tickets con los filtros actuales.</td></tr>';
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

        const tr = document.createElement('tr');

        tr.innerHTML = `
            <td class="fw-bold text-muted">#${ticket.id}</td>
            <td>${ticket.usuario_id}</td>
            <td class="small text-muted">${fechaFormatted}</td>
            <td style="max-width: 250px;" class="text-truncate" title="${ticket.descripcion}">${ticket.descripcion}</td>
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
