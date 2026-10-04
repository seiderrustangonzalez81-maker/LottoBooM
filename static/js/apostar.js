// =============================================
// FUNCIONES PARA APOSTAR
// =============================================

// Variables globales para almacenar selecciones
window.sorteosSeleccionados = [];
window.usuariosSeleccionados = [];
window.formaPagoSeleccionada = null;

// Cambiar fecha
function cambiarFecha(fecha) {
    // Actualizar la fecha en la interfaz
    const fechaDisplay = document.querySelector('.fecha-display');
    if (fechaDisplay) {
        const date = new Date(fecha + 'T00:00:00');
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        fechaDisplay.textContent = date.toLocaleDateString('es-ES', options);
    }
    // Recargar datos si es necesario
    if (document.getElementById('modalSorteos')?.classList.contains('show')) {
        cargarSorteosDisponibles();
    }
}

// Actualizar hora en tiempo real
function actualizarHora() {
    const ahora = new Date();
    const hora = ahora.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const horaDisplay = document.getElementById('horaDinamica');
    if (horaDisplay) {
        horaDisplay.innerHTML = `<i class="fas fa-clock me-1"></i> ${hora}`;
    }
}

// Iniciar reloj
setInterval(actualizarHora, 1000);
actualizarHora();

// =============================================
// FUNCIONES PARA LAS TABLAS DE JUGADAS
// =============================================

function mostrarTabla(tipo) {
    // Ocultar todas las tablas
    const tabs = ['tablaTradicionales', 'tablaSuperparlet', 'tablaCombinada', 'tablaTriplePosicion', 'tablaTripleta'];
    tabs.forEach(id => {
        const elem = document.getElementById(id);
        if (elem) elem.style.display = 'none';
    });

    // Mostrar la tabla seleccionada
    const tablaMap = {
        'tradicionales': 'tablaTradicionales',
        'superparlet': 'tablaSuperparlet',
        'combinada': 'tablaCombinada',
        'tripleposicion': 'tablaTriplePosicion',
        'tripleta': 'tablaTripleta'
    };
    const tabla = document.getElementById(tablaMap[tipo]);
    if (tabla) tabla.style.display = 'block';

    // Actualizar pestañas activas
    document.querySelectorAll('.selection-bar .btn-header').forEach(btn => {
        btn.classList.remove('active-tab');
    });
    const btnMap = {
        'tradicionales': 'btnTradicionales',
        'superparlet': 'btnSuperparlet',
        'combinada': 'btnCombinada',
        'tripleposicion': 'btnTriplePosicion',
        'tripleta': 'btnTripleta'
    };
    const btnActivo = document.getElementById(btnMap[tipo]);
    if (btnActivo) btnActivo.classList.add('active-tab');
}

// =============================================
// FUNCIONES PARA AÑADIR JUGADAS
// =============================================

function añadirJugadaTradicional() {
    // Implementar lógica para añadir jugada tradicional
    console.log('Añadir jugada tradicional');
    // Aquí va tu lógica específica
}

function añadirJugadaSuperparlet() {
    console.log('Añadir jugada SuperParlet');
}

function añadirJugadaCombinada() {
    console.log('Añadir jugada Combinada');
}

function añadirJugadaTriplePosicion() {
    console.log('Añadir jugada Triple Posición');
}

function añadirJugadaTripleta() {
    console.log('Añadir jugada Tripleta');
}

// Funciones para agregar filas dinámicas
function agregarFilaSuperparlet() {
    // Implementar lógica para agregar fila en SuperParlet
    console.log('Agregar fila SuperParlet');
}

function agregarFilaCombinada() {
    console.log('Agregar fila Combinada');
}

function añadirFilaSuperparlet(btn) {
    console.log('Añadir fila SuperParlet desde botón');
}

function añadirFilaCombinada(btn) {
    console.log('Añadir fila Combinada desde botón');
}

// =============================================
// FUNCIONES PARA EL SALDO
// =============================================

function cargarSaldo() {
    const saldoBody = document.getElementById('saldoBody');
    if (!saldoBody) return;

    fetch('/usuarios/api/saldo/')
        .then(response => {
            if (!response.ok) throw new Error('Error al cargar saldo');
            return response.json();
        })
        .then(data => {
            saldoBody.innerHTML = `
                <div class="saldo-monto">${data.saldo || 0.00}</div>
                <div class="saldo-moneda">CUP</div>
            `;
        })
        .catch(error => {
            console.error('Error:', error);
            saldoBody.innerHTML = `
                <div class="text-center py-3 text-danger small">
                    Error al cargar saldo
                    <button class="btn btn-sm btn-outline-danger d-block mx-auto mt-2"
                            onclick="cargarSaldo()">Reintentar</button>
                </div>
            `;
        });
}

// Cargar saldo al iniciar
document.addEventListener('DOMContentLoaded', function() {
    cargarSaldo();

    // Si hay un botón para recargar saldo
    document.getElementById('btnRecargarSaldo')?.addEventListener('click', cargarSaldo);
});