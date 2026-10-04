// =============================================
// MODAL SORTEOS - Cargar sorteos disponibles
// =============================================
function cargarSorteosDisponibles() {
    const container = document.getElementById('sorteosContainer');
    if (!container) return;

    // Mostrar loading
    container.innerHTML = `
        <div class="col-12 text-center py-5 text-muted">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
            <p class="mt-2">Cargando sorteos disponibles...</p>
        </div>
    `;

    fetch('/sorteos/api/disponibles/')
        .then(response => {
            if (!response.ok) throw new Error('Error al cargar sorteos');
            return response.json();
        })
        .then(data => {
            if (data.length === 0) {
                container.innerHTML = `
                    <div class="col-12 text-center py-5 text-muted">
                        <i class="fas fa-calendar-times fa-3x"></i>
                        <p class="mt-2">No hay sorteos disponibles para apostar</p>
                        <small class="text-muted">Los sorteos cierran 10 minutos antes de su salida</small>
                    </div>
                `;
                return;
            }

            container.innerHTML = '';
            data.forEach(sorteo => {
                const col = document.createElement('div');
                col.className = 'col-md-6 col-xl-4';

                // Calcular tiempo restante en minutos
                const minutosRestantes = Math.floor(sorteo.tiempo_restante / 60);

                col.innerHTML = `
                    <label class="modal-card sorteos-modal d-block h-100" style="cursor:pointer;border:2px solid #dee2e6;border-radius:10px;padding:12px;transition:all 0.2s;">
                        <input class="form-check-input check-sorteo"
                               type="checkbox"
                               value="${sorteo.id}"
                               data-nombre="${sorteo.nombre}"
                               data-hora="${sorteo.hora_salida}">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <strong class="d-block">${sorteo.nombre}</strong>
                                <small class="text-muted">
                                    <i class="fas fa-clock"></i> ${sorteo.hora_salida}
                                </small>
                            </div>
                            <span class="badge bg-success rounded-pill">
                                ${minutosRestantes} min
                            </span>
                        </div>
                        <small class="text-muted d-block mt-1">
                            <i class="fas fa-hourglass-half"></i> Cierra en ${minutosRestantes} minutos
                        </small>
                    </label>
                `;
                container.appendChild(col);

                // Estilo hover dinámico
                col.querySelector('.modal-card').addEventListener('mouseenter', function() {
                    this.style.borderColor = '#0d6efd';
                    this.style.backgroundColor = '#f8f9fa';
                });
                col.querySelector('.modal-card').addEventListener('mouseleave', function() {
                    this.style.borderColor = '#dee2e6';
                    this.style.backgroundColor = 'transparent';
                });
            });

            // Actualizar contador en el botón de aceptar
            actualizarContadorSorteos();
        })
        .catch(error => {
            console.error('Error:', error);
            container.innerHTML = `
                <div class="col-12 text-center py-5 text-danger">
                    <i class="fas fa-exclamation-triangle fa-3x"></i>
                    <p class="mt-2">Error al cargar sorteos</p>
                    <button class="btn btn-sm btn-outline-primary" onclick="cargarSorteosDisponibles()">
                        Reintentar
                    </button>
                </div>
            `;
        });
}

// Contar sorteos seleccionados
function actualizarContadorSorteos() {
    const checkboxes = document.querySelectorAll('.check-sorteo:checked');
    const btnAceptar = document.getElementById('btnAceptarSorteos');
    if (btnAceptar) {
        const count = checkboxes.length;
        btnAceptar.textContent = count > 0 ? `Aceptar (${count})` : 'Aceptar';
    }
}

// Seleccionar todos los sorteos
function seleccionarTodosSorteos(seleccionar) {
    const checkboxes = document.querySelectorAll('.check-sorteo');
    checkboxes.forEach(cb => cb.checked = seleccionar);
    actualizarContadorSorteos();
}

// Guardar sorteos seleccionados
function guardarSorteosSeleccionados() {
    const checkboxes = document.querySelectorAll('.check-sorteo:checked');
    const seleccionados = Array.from(checkboxes).map(cb => ({
        id: parseInt(cb.value),
        nombre: cb.dataset.nombre,
        hora: cb.dataset.hora
    }));

    // Actualizar el campo "Enviada a: Sorteos"
    const envSorteos = document.getElementById('envSorteos');
    if (envSorteos) {
        if (seleccionados.length === 0) {
            envSorteos.textContent = '-';
            envSorteos.className = 'enviada-valor';
        } else {
            envSorteos.textContent = seleccionados.map(s => s.nombre).join(', ');
            envSorteos.className = 'enviada-valor activo';
        }
    }

    // Guardar en variable global para usarlo en la apuesta
    window.sorteosSeleccionados = seleccionados;
}

// =============================================
// MODAL CON QUIÉN - Cargar usuarios
// =============================================
function cargarUsuariosFondo(busqueda = '') {
    const container = document.getElementById('usuariosFondoContainer');
    if (!container) return;

    // Mostrar loading
    container.innerHTML = `
        <div class="text-center py-3 text-muted small">
            <div class="spinner-border text-purple" role="status">
                <span class="visually-hidden">Cargando...</span>
            </div>
        </div>
    `;

    // Esta URL debería ser tu API de usuarios (ajústala según tu proyecto)
    fetch(`/usuarios/api/usuarios/?busqueda=${encodeURIComponent(busqueda)}`)
        .then(response => {
            if (!response.ok) throw new Error('Error al cargar usuarios');
            return response.json();
        })
        .then(data => {
            if (data.length === 0) {
                container.innerHTML = `
                    <div class="text-center py-3 text-muted small">
                        <i class="fas fa-user-slash"></i> No se encontraron usuarios
                    </div>
                `;
                return;
            }

            container.innerHTML = '';
            data.forEach(usuario => {
                const label = document.createElement('label');
                label.className = 'modal-card purple d-block';
                label.style.cssText = 'cursor:pointer;border:2px solid #dee2e6;border-radius:10px;padding:10px 12px;transition:all 0.2s;';
                label.innerHTML = `
                    <input class="form-check-input check-usuario" type="checkbox"
                           value="${usuario.id}" data-nombre="${usuario.username}">
                    <strong>${usuario.username}</strong>
                    ${usuario.email ? `<small class="text-muted d-block">${usuario.email}</small>` : ''}
                `;
                container.appendChild(label);

                // Estilo hover
                label.addEventListener('mouseenter', function() {
                    this.style.borderColor = '#6f42c1';
                    this.style.backgroundColor = '#f8f9fa';
                });
                label.addEventListener('mouseleave', function() {
                    this.style.borderColor = '#dee2e6';
                    this.style.backgroundColor = 'transparent';
                });
            });

            actualizarContadorUsuarios();
        })
        .catch(error => {
            console.error('Error:', error);
            container.innerHTML = `
                <div class="text-center py-3 text-danger small">
                    <i class="fas fa-exclamation-triangle"></i> Error al cargar usuarios
                    <button class="btn btn-sm btn-outline-danger d-block mx-auto mt-2"
                            onclick="cargarUsuariosFondo()">Reintentar</button>
                </div>
            `;
        });
}

// Contar usuarios seleccionados
function actualizarContadorUsuarios() {
    const checkboxes = document.querySelectorAll('.check-usuario:checked');
    const btnAceptar = document.getElementById('btnAceptarConQuien');
    if (btnAceptar) {
        const count = checkboxes.length;
        btnAceptar.textContent = count > 0 ? `Aceptar (${count})` : 'Aceptar';
    }
}

// Guardar usuarios seleccionados
function guardarConQuien() {
    const checkboxes = document.querySelectorAll('.check-usuario:checked');
    const seleccionados = Array.from(checkboxes).map(cb => ({
        id: parseInt(cb.value),
        nombre: cb.dataset.nombre
    }));

    const envDestinatarios = document.getElementById('envDestinatarios');
    if (envDestinatarios) {
        if (seleccionados.length === 0) {
            envDestinatarios.textContent = '-';
            envDestinatarios.className = 'enviada-valor';
        } else {
            envDestinatarios.textContent = seleccionados.map(u => u.nombre).join(', ');
            envDestinatarios.className = 'enviada-valor activo';
        }
    }

    window.usuariosSeleccionados = seleccionados;
}

// Búsqueda en tiempo real
document.addEventListener('DOMContentLoaded', function() {
    const buscarInput = document.getElementById('buscarConQuien');
    if (buscarInput) {
        let timeoutId;
        buscarInput.addEventListener('input', function() {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                cargarUsuariosFondo(this.value);
            }, 300);
        });
    }
});

// =============================================
// MODAL FORMAS DE PAGO
// =============================================
function cargarFormasPago() {
    const container = document.getElementById('formasPagoContainer');
    if (!container) return;

    // Aquí deberías cargar desde una API o usar las que están en el HTML
    // Por ahora usamos las que vienen del contexto de Django
    const formasPago = window.formasPagoData || [
        { id: 1, nombre: 'Efectivo' },
        { id: 2, nombre: 'Transferencia' },
        { id: 3, nombre: 'Tarjeta' }
    ];

    container.innerHTML = '';
    formasPago.forEach((pago, index) => {
        const label = document.createElement('label');
        label.className = 'modal-card orange d-block';
        label.style.cssText = 'cursor:pointer;border:2px solid #dee2e6;border-radius:10px;padding:12px;transition:all 0.2s;';
        label.innerHTML = `
            <input class="form-check-input check-pago" type="radio"
                   name="forma_pago_radio" value="${pago.nombre}"
                   data-nombre="${pago.nombre}" ${index === 0 ? 'checked' : ''}>
            <strong>${pago.nombre}</strong>
        `;
        container.appendChild(label);

        // Estilo hover
        label.addEventListener('mouseenter', function() {
            this.style.borderColor = '#fd7e14';
            this.style.backgroundColor = '#fff8f0';
        });
        label.addEventListener('mouseleave', function() {
            this.style.borderColor = '#dee2e6';
            this.style.backgroundColor = 'transparent';
        });
    });

    // Marcar el primero como seleccionado visualmente
    const firstRadio = container.querySelector('.check-pago');
    if (firstRadio && firstRadio.checked) {
        firstRadio.closest('.modal-card').style.borderColor = '#fd7e14';
    }

    // Evento para resaltar el seleccionado
    container.querySelectorAll('.check-pago').forEach(radio => {
        radio.addEventListener('change', function() {
            container.querySelectorAll('.modal-card').forEach(card => {
                card.style.borderColor = '#dee2e6';
                card.style.backgroundColor = 'transparent';
            });
            if (this.checked) {
                this.closest('.modal-card').style.borderColor = '#fd7e14';
                this.closest('.modal-card').style.backgroundColor = '#fff8f0';
            }
        });
    });
}

// Guardar forma de pago seleccionada
function guardarFormaPago() {
    const selected = document.querySelector('.check-pago:checked');
    if (selected) {
        const nombre = selected.dataset.nombre;
        const envPago = document.getElementById('envPago');
        if (envPago) {
            envPago.textContent = nombre;
            envPago.className = 'enviada-valor activo';
        }
        window.formaPagoSeleccionada = nombre;
    }
}

// =============================================
// INICIALIZACIÓN DE MODALES
// =============================================
document.addEventListener('DOMContentLoaded', function() {
    // --- Modal Sorteos ---
    const modalSorteos = document.getElementById('modalSorteos');
    if (modalSorteos) {
        modalSorteos.addEventListener('show.bs.modal', function() {
            cargarSorteosDisponibles();
        });

        // Botones de selección
        document.getElementById('btnSelTodosSorteos')?.addEventListener('click', function() {
            seleccionarTodosSorteos(true);
        });
        document.getElementById('btnSelNingunoSorteos')?.addEventListener('click', function() {
            seleccionarTodosSorteos(false);
        });

        // Evento para contar selecciones
        document.addEventListener('change', function(e) {
            if (e.target.classList.contains('check-sorteo')) {
                actualizarContadorSorteos();
            }
        });

        // Botón aceptar
        document.getElementById('btnAceptarSorteos')?.addEventListener('click', function() {
            guardarSorteosSeleccionados();
        });

        // Cambio de fecha
        document.getElementById('modalFechaSelector')?.addEventListener('change', function() {
            // Aquí puedes recargar los sorteos para la fecha seleccionada
            cargarSorteosDisponibles();
        });
    }

    // --- Modal Con Quién ---
    const modalConQuien = document.getElementById('modalConQuien');
    if (modalConQuien) {
        modalConQuien.addEventListener('show.bs.modal', function() {
            cargarUsuariosFondo();
        });

        // Evento para contar selecciones
        document.addEventListener('change', function(e) {
            if (e.target.classList.contains('check-usuario')) {
                actualizarContadorUsuarios();
            }
        });

        // Botón aceptar
        document.getElementById('btnAceptarConQuien')?.addEventListener('click', function() {
            guardarConQuien();
        });
    }

    // --- Modal Formas de Pago ---
    const modalPago = document.getElementById('modalFormasPago');
    if (modalPago) {
        modalPago.addEventListener('show.bs.modal', function() {
            cargarFormasPago();
        });

        document.getElementById('btnAceptarPago')?.addEventListener('click', function() {
            guardarFormaPago();
        });
    }
});