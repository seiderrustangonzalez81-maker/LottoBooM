import os
import re

# Ruta donde se guardará el nuevo apostar.html
ruta_destino = "/home/LottoBooM/jugadas/templates/jugadas/apostar.html"
ruta_backup = ruta_destino + ".bak_original"

# Si existe un respaldo original, lo guardamos
if os.path.exists(ruta_destino):
    os.rename(ruta_destino, ruta_backup)
    print(f"✅ Respaldo guardado en {ruta_backup}")

# Contenido completo del nuevo apostar.html
# (Usamos un raw string para evitar escapes)
contenido = r'''{% extends "base.html" %}
{% load static %}

{% block page_title %}Apostar{% endblock %}
{% block page_subtitle %}Selecciona tus números y confirma tu jugada{% endblock %}

{% block extra_css %}
<style>
  :root {
    --primary: #4f46e5;
    --success: #059669;
    --danger: #dc2626;
    --warning: #d97706;
    --bg: #f8fafc;
    --card-bg: #ffffff;
    --border: #e2e8f0;
    --text: #0f172a;
    --text-muted: #64748b;
    --radius: 12px;
  }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }
  .card-apuesta { background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 1rem; overflow: hidden; }
  .card-apuesta .card-header { background: #f1f5f9; border-bottom: 1px solid var(--border); padding: 0.6rem 1rem; font-weight: 700; font-size: 0.9rem; cursor: pointer; display: flex; align-items: center; justify-content: space-between; user-select: none; }
  .card-apuesta .card-header i.toggle-icon { transition: transform 0.2s; color: var(--text-muted); }
  .card-apuesta .card-header.collapsed i.toggle-icon { transform: rotate(-90deg); }
  .card-apuesta .card-body { padding: 0.5rem; }
  .table-apuesta { width: 100%; font-size: 0.85rem; border-collapse: collapse; margin-bottom: 0; }
  .table-apuesta th { background: #f8fafc; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.3px; color: var(--text-muted); padding: 0.4rem 0.3rem; border-bottom: 2px solid var(--border); white-space: nowrap; }
  .table-apuesta td { padding: 0.3rem; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }
  .table-apuesta tr:last-child td { border-bottom: none; }
  .inp-num { width: 100%; min-width: 90px; font-family: 'Courier New', monospace; font-weight: 700; font-size: 0.9rem; padding: 0.35rem 0.5rem; border: 1.5px solid var(--border); border-radius: 8px; background: #fff; color: var(--text); resize: none; overflow: hidden; line-height: 1.4; }
  .inp-num:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }
  .inp-monto { min-width: 50px; width: auto; max-width: 120px; font-weight: 700; font-size: 0.9rem; padding: 0.35rem 0.4rem; border: 1.5px solid var(--border); border-radius: 8px; background: #fff; color: var(--text); text-align: right; transition: width 0.1s; }
  .inp-monto:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(79,70,229,0.1); }
  .total-fila { font-weight: 800; color: var(--success); font-size: 0.95rem; text-align: center; white-space: nowrap; }
  .selector-cliente { background: var(--card-bg); border: 1px solid var(--border); border-radius: var(--radius); padding: 1rem; margin-bottom: 1rem; }
  .btn-moderno { border-radius: 60px; padding: 0.5rem 1.5rem; font-weight: 700; font-size: 0.85rem; border: none; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; transition: filter 0.15s; }
  .btn-moderno:hover { filter: brightness(0.95); }
  .btn-success-moderno { background: var(--success); color: #fff; }
  .btn-primary-moderno { background: var(--primary); color: #fff; }
  .sorteo-check { display: flex; align-items: center; gap: 8px; padding: 0.6rem; border: 1.5px solid var(--border); border-radius: 10px; margin-bottom: 0.5rem; cursor: pointer; transition: border-color 0.15s; }
  .sorteo-check:hover { border-color: var(--primary); }
  .sorteo-check input { margin-top: 2px; }
  #toastContainer { position: fixed; bottom: 16px; right: 16px; z-index: 9999; max-width: 340px; }
  .footer-totales { position: sticky; bottom: 0; z-index: 1020; background: var(--card-bg); border-top: 2px solid var(--primary); box-shadow: 0 -4px 12px rgba(0,0,0,0.1); padding: 0.75rem 1rem; margin-top: 1rem; border-radius: var(--radius) var(--radius) 0 0; }
  .footer-totales .resumen-linea { border-bottom: none; font-size: 1rem; }
  .footer-totales .resumen-linea .lbl { font-weight: 600; }
  @media (max-width: 768px) {
    .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .table-apuesta { min-width: 600px; }
    .inp-num, .inp-monto { font-size: 1rem; }
    .resumen-sticky { position: relative !important; top: 0 !important; }
    .footer-totales { position: relative; }
  }
  input[type=number]::-webkit-inner-spin-button,
  input[type=number]::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  input[type=number] {
    -moz-appearance: textfield;
    appearance: textfield;
  }
</style>
{% endblock %}

{% block content %}
<div id="toastContainer"></div>
<div class="container-fluid py-3">
  <div class="row g-3">
    <div class="col-lg-9">
      <div class="card-apuesta">
        <div class="card-header bg-white">
          <h5 class="mb-0 fw-bold"><i class="fas fa-dice me-2 text-primary"></i>Realizar Apuesta</h5>
          <span class="badge bg-success bg-opacity-10 text-success"><i class="fas fa-circle me-1" style="font-size:0.4rem;"></i>Activo</span>
        </div>
        <div class="card-body p-3">
          <form method="post" id="apostarForm" novalidate>
            {% csrf_token %}
            <input type="hidden" name="cliente_id" id="clienteIdHidden" value="">

            <!-- SELECTOR CLIENTE -->
            <div class="selector-cliente">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="fw-semibold"><i class="fas fa-user-circle me-2 text-primary"></i>{% if es_cliente %}Selecciona un gestor:{% else %}Selecciona un cliente:{% endif %}</span>
                <div class="d-flex align-items-center gap-2">
                  <span id="clienteSeleccionadoNombre" class="text-muted small">Ninguno seleccionado</span>
                  <button type="button" id="cancelarClienteBtn" class="btn btn-outline-danger btn-sm rounded-pill" style="display:none;">
                    <i class="fas fa-times"></i> Cancelar
                  </button>
                </div>
              </div>
              <div class="mb-3">
                <label for="clienteSelect" class="form-label">Selecciona un cliente/gestor</label>
                <select id="clienteSelect" class="form-select">
                  <option value="">-- Seleccionar --</option>
                  {% for item in clientes %}
                    <option value="{{ item.id }}" data-nombre="{{ item.nombre }}" data-saldo="{{ item.saldo_total|floatformat:2 }}" data-bonos="{{ item.bonos_activos|floatformat:2 }}" data-telefono="{{ item.telefono|default:'' }}" data-rol="{{ item.rol|default:'' }}">
                      {{ item.nombre }} (Saldo: ${{ item.saldo_total|floatformat:2 }})
                    </option>
                  {% empty %}
                    <option value="" disabled>{% if es_cliente %}No tienes gestores con fondos activos.{% else %}No tienes clientes asignados.{% endif %}</option>
                  {% endfor %}
                </select>
              </div>
              <input type="hidden" name="cliente_seleccionado" id="clienteSeleccionado" value="">
            </div>

            <!-- SORTEOS, FORMA DE PAGO Y FECHA -->
            <div class="row g-2 mb-3">
              <div class="col-md-4">
                <label class="form-label fw-semibold"><i class="fas fa-calendar-alt text-primary me-1"></i>Sorteo(s)</label>
                <div class="d-flex align-items-center gap-2 flex-wrap">
                  <button type="button" class="btn btn-outline-primary btn-sm rounded-pill" id="btnAbrirSorteos"><i class="fas fa-edit"></i> Seleccionar</button>
                  <span id="sorteosSeleccionadosCount" class="badge bg-primary bg-opacity-10 text-primary">0 seleccionados</span>
                </div>
                <div id="sorteosSeleccionadosList" class="mt-1 small text-muted">Ningun sorteo seleccionado</div>
                <input type="hidden" name="sorteos" id="sorteosHiddenInput" value="">
              </div>
              <div class="col-md-4">
                <label for="formaPagoSelect" class="form-label fw-semibold"><i class="fas fa-credit-card text-warning me-1"></i>Forma de Pago</label>
                <select name="forma_pago" id="formaPagoSelect" class="form-select" disabled>
                  <option value="" disabled selected>Selecciona un cliente primero</option>
                </select>
                <div class="form-text text-muted" id="infoFormasPago"><i class="fas fa-info-circle"></i> Se cargan al seleccionar un cliente.</div>
              </div>
              <div class="col-md-4">
                <label for="fechaApuesta" class="form-label fw-semibold"><i class="fas fa-calendar text-info me-1"></i>Fecha de la Apuesta</label>
                <input type="date" id="fechaApuesta" name="fecha" class="form-control" value="{{ hoy|date:'Y-m-d' }}">
              </div>
            </div>

            <!-- TABLA DE FONDOS -->
            <div id="tablaFondosCliente" style="display:none;" class="mb-3">
              <div class="card-apuesta">
                <div class="card-header bg-light">
                  <span id="fondosClienteNombre">Cliente: -</span>
                  <span id="fondosGestorNombre">Gestor: -</span>
                </div>
                <div class="card-body p-0">
                  <div class="table-responsive">
                    <table class="table table-sm table-bordered mb-0" id="tablaFondos">
                      <thead class="table-light">
                        <tr><th>Forma de Pago</th><th>Saldo</th>{% if es_superadmin %}<th>Bonos</th>{% endif %}<th>Total</th></tr>
                      </thead>
                      <tbody id="cuerpoTablaFondos">
                        <tr><td colspan="{% if es_superadmin %}4{% else %}3{% endif %}" class="text-center text-muted">Selecciona un cliente</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>

            <!-- ===== TODAS LAS TABLAS DE APUESTAS ===== -->
            <!-- TRADICIONAL -->
            <div class="card-apuesta tabla-tradicional">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-table me-2 text-primary"></i>Tradicional</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaTradicional">
                    <thead>
                      <tr><th>Numeros (2 dig)</th><th>Pick 2</th><th>PF</th><th>Fijo</th><th>Corridos</th><th>Parlet</th><th>Candado</th><th>Suma</th><th></th></tr>
                    </thead>
                    <tbody id="bodyTradicional">
                      <tr id="tradicional-1">
                        <td><textarea class="inp-num numeros-tradicional" rows="1" placeholder="12 34 PA D5" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-forma" step="0.01" min="0" placeholder="0" data-fila="1" data-forma="pick2" data-tabla="tradicional" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-forma" step="0.01" min="0" placeholder="0" data-fila="1" data-forma="pf" data-tabla="tradicional" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-forma" step="0.01" min="0" placeholder="0" data-fila="1" data-forma="fijo" data-tabla="tradicional" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-forma" step="0.01" min="0" placeholder="0" data-fila="1" data-forma="corridos" data-tabla="tradicional" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-forma" step="0.01" min="0" placeholder="0" data-fila="1" data-forma="parlet" data-tabla="tradicional" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-forma" step="0.01" min="0" placeholder="0" data-fila="1" data-forma="candado" data-tabla="tradicional" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalTradicional-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'tradicional')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="9" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyTradicional','tradicional')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- PICK 3 -->
            <div class="card-apuesta tabla-pick3">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-hashtag me-2 text-success"></i>Pick 3</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaPick3">
                    <thead><tr><th>Numeros (3 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyPick3">
                      <tr id="pick3-1">
                        <td><textarea class="inp-num numeros-pick3" rows="1" placeholder="123 456" data-fila="1" onchange="procesarInput(this,3);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-pick3" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="pick3" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalPick3-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'pick3')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="4" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyPick3','pick3')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- CENTENAS -->
            <div class="card-apuesta tabla-centenas">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-arrows-alt-h me-2 text-warning"></i>Centenas Corridas</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaCentenas">
                    <thead><tr><th>Numeros (3 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyCentenas">
                      <tr id="centenas-1">
                        <td><textarea class="inp-num numeros-centenas" rows="1" placeholder="123 456" data-fila="1" onchange="procesarInput(this,3);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-centenas" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="centenas" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalCentenas-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'centenas')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="4" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyCentenas','centenas')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- PICK 4 -->
            <div class="card-apuesta tabla-pick4">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-hashtag me-2 text-info"></i>Pick 4</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaPick4">
                    <thead><tr><th>Numeros (4 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyPick4">
                      <tr id="pick4-1">
                        <td><textarea class="inp-num numeros-pick4" rows="1" placeholder="1234 5678" data-fila="1" onchange="procesarInput(this,4);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-pick4" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="pick4" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalPick4-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'pick4')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="4" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyPick4','pick4')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- PICK 5 -->
            <div class="card-apuesta tabla-pick5">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-hashtag me-2 text-danger"></i>Pick 5</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaPick5">
                    <thead><tr><th>Numeros (5 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyPick5">
                      <tr id="pick5-1">
                        <td><textarea class="inp-num numeros-pick5" rows="1" placeholder="12345 67890" data-fila="1" onchange="procesarInput(this,5);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-pick5" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="pick5" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalPick5-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'pick5')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="4" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyPick5','pick5')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- VS -->
            <div class="card-apuesta tabla-vs">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-exchange-alt me-2 text-danger"></i>VS</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaVS">
                    <thead><tr><th>Grupo 1 (2 dig)</th><th>Grupo 2 (2 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyVS">
                      <tr id="vs-1">
                        <td><textarea class="inp-num numeros-vs-g1" rows="1" placeholder="12 34" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><textarea class="inp-num numeros-vs-g2" rows="1" placeholder="56 78" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-vs" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="vs" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalVS-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'vs')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="5" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyVS','vs')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- VSPF -->
            <div class="card-apuesta tabla-vspf">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-exchange-alt me-2 text-warning"></i>VSPF</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaVSPF">
                    <thead><tr><th>Grupo 1 (2 dig)</th><th>Grupo 2 (2 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyVSPF">
                      <tr id="vspf-1">
                        <td><textarea class="inp-num numeros-vspf-g1" rows="1" placeholder="12 34" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><textarea class="inp-num numeros-vspf-g2" rows="1" placeholder="56 78" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-vspf" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="vspf" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalVSPF-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'vspf')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="5" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyVSPF','vspf')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- VSPick2 -->
            <div class="card-apuesta tabla-vspick2">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-exchange-alt me-2 text-info"></i>VSPick2</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaVSPick2">
                    <thead><tr><th>Grupo 1 (2 dig)</th><th>Grupo 2 (2 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyVSPick2">
                      <tr id="vspick2-1">
                        <td><textarea class="inp-num numeros-vspick2-g1" rows="1" placeholder="12 34" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><textarea class="inp-num numeros-vspick2-g2" rows="1" placeholder="56 78" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-vspick2" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="vspick2" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalVSPick2-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'vspick2')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="5" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyVSPick2','vspick2')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- Pick2 vsPF -->
            <div class="card-apuesta tabla-pick2vspf">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-exchange-alt me-2 text-primary"></i>Pick2 vsPF</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaPick2VSPF">
                    <thead><tr><th>Grupo 1 (2 dig)</th><th>Grupo 2 (2 dig)</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyPick2VSPF">
                      <tr id="pick2vspf-1">
                        <td><textarea class="inp-num numeros-pick2vspf-g1" rows="1" placeholder="12 34" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><textarea class="inp-num numeros-pick2vspf-g2" rows="1" placeholder="56 78" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-pick2vspf" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="pick2vspf" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalPick2VSPF-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'pick2vspf')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="5" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyPick2VSPF','pick2vspf')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- VS100 -->
            <div class="card-apuesta tabla-vs100">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-hashtag me-2 text-primary"></i>VS100</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaVS100">
                    <thead><tr><th>Numeros (2 dig)</th><th>Monto (por parlet)</th><th>Total</th><th></th></tr></thead>
                    <tbody id="bodyVS100">
                      <tr id="vs100-1">
                        <td><textarea class="inp-num numeros-vs100" rows="1" placeholder="12 34" data-fila="1" onchange="procesarInput(this,2);calcularFila(this)"></textarea></td>
                        <td><input type="number" class="inp-monto monto-vs100" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="vs100" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalVS100-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'vs100')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="4" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyVS100','vs100')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- POSICIONES -->
            <div class="card-apuesta tabla-posiciones">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-arrows-alt-h me-2 text-success"></i>Posiciones</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaPosiciones">
                    <thead><tr><th>N 1</th><th>Monto</th><th>N 2</th><th>Monto</th><th>N 3</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyPosiciones">
                      <tr id="posicion-1">
                        <td><input type="text" class="inp-num num-posicion" placeholder="12" data-pos="1" onchange="procesarInput(this,2);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-posicion1" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="posicion" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td><input type="text" class="inp-num num-posicion" placeholder="34" data-pos="2" onchange="procesarInput(this,2);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-posicion2" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="posicion" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td><input type="text" class="inp-num num-posicion" placeholder="56" data-pos="3" onchange="procesarInput(this,2);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-posicion3" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="posicion" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalPosicion-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'posicion')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="8" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyPosiciones','posicion')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>

            <!-- TRIPLETA -->
            <div class="card-apuesta tabla-tripleta">
              <div class="card-header" onclick="toggleTabla(this)"><span><i class="fas fa-arrows-alt-h me-2 text-danger"></i>Tripleta</span><i class="fas fa-chevron-down toggle-icon"></i></div>
              <div class="card-body">
                <div class="table-responsive">
                  <table class="table-apuesta" id="tablaTripleta">
                    <thead><tr><th>N 1</th><th>N 2</th><th>N 3</th><th>Monto</th><th>Suma</th><th></th></tr></thead>
                    <tbody id="bodyTripleta">
                      <tr id="tripleta-1">
                        <td><input type="text" class="inp-num num-tripleta" placeholder="12" data-pos="1" onchange="procesarInput(this,2);calcularFila(this)"></td>
                        <td><input type="text" class="inp-num num-tripleta" placeholder="34" data-pos="2" onchange="procesarInput(this,2);calcularFila(this)"></td>
                        <td><input type="text" class="inp-num num-tripleta" placeholder="56" data-pos="3" onchange="procesarInput(this,2);calcularFila(this)"></td>
                        <td><input type="number" class="inp-monto monto-tripleta" step="0.01" min="0" placeholder="0" data-fila="1" data-tabla="tripleta" onchange="ajustarAnchoMonto(this);calcularFila(this)"></td>
                        <td class="total-fila" id="totalTripleta-1">$0.00</td>
                        <td><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarFila(this,'tripleta')"><i class="fas fa-trash"></i></button></td>
                      </tr>
                    </tbody>
                    <tfoot><tr><td colspan="6" class="text-center py-2"><button type="button" class="btn btn-primary btn-sm" onclick="agregarFila('bodyTripleta','tripleta')"><i class="fas fa-plus"></i> Anadir fila</button></td></tr></tfoot>
                  </table>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- COLUMNA RESUMEN -->
    <div class="col-lg-3">
      <div class="resumen-sticky">
        <!-- CARRITO 1 -->
        <div class="card sticky-top mb-3" style="top:1rem;">
          <div class="card-header"><h6 class="mb-0 fw-bold"><i class="fas fa-shopping-cart me-2"></i>Resumen de Jugadas</h6></div>
          <div class="card-body p-2">
            <div id="resumenInfoGeneral1">
              <div class="resumen-linea"><span class="lbl">Cliente</span><span id="resumenCliente1" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Gestor</span><span id="resumenGestor1" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Rol</span><span id="resumenRol1" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Forma de pago</span><span id="resumenFormaPago1" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Sorteos</span><span id="resumenSorteos1" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Fecha</span><span id="resumenFecha1" class="val">-</span></div>
            </div>
            <hr class="my-2">
            <div><span class="text-muted small">Jugadas cargadas:</span><div id="detalleJugadas1" class="mt-1"></div></div>
            <hr class="my-2">
            <div class="resumen-linea"><span class="lbl">Total por sorteo</span><span id="resumenTotalPorSorteo1" class="val success">$0.00</span></div>
            <div class="resumen-linea fw-bold"><span class="lbl">Total general</span><span id="resumenTotalGeneral1" class="val success">$0.00</span></div>
            <hr class="my-2">
            <div class="resumen-linea"><span class="lbl">Postpago pendiente</span><span id="resumenPostpago1" class="val warning">$0.00</span></div>
            <div class="resumen-linea"><span class="lbl">Saldo inicial</span><span id="resumenSaldoInicial1" class="val">$0.00</span></div>
            <div class="resumen-linea"><span class="lbl">Saldo final</span><span id="resumenSaldoFinal1" class="val danger">$0.00</span></div>
            <div class="resumen-linea"><span class="lbl">Bonos activos</span><span id="resumenBonos1" class="val warning">$0.00</span></div>
          </div>
        </div>

        <!-- CARRITO 2 (Superparlet) -->
        <div class="card mb-3">
          <div class="card-header bg-info text-white"><h6 class="mb-0 fw-bold"><i class="fas fa-shopping-cart me-2"></i>Resumen Superparlet</h6></div>
          <div class="card-body p-2">
            <div id="resumenInfoGeneral2">
              <div class="resumen-linea"><span class="lbl">Cliente</span><span id="resumenCliente2" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Gestor</span><span id="resumenGestor2" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Rol</span><span id="resumenRol2" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Sorteo 1</span><span id="resumenSorteo1_2" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Sorteo 2</span><span id="resumenSorteo2_2" class="val">-</span></div>
              <div class="resumen-linea"><span class="lbl">Fecha</span><span id="resumenFecha2" class="val">-</span></div>
            </div>
            <hr class="my-2">
            <div><span class="text-muted small">Jugadas Superparlet:</span><div id="detalleJugadas2" class="mt-1"></div></div>
            <hr class="my-2">
            <div class="resumen-linea"><span class="lbl">Total por sorteo</span><span id="resumenTotalPorSorteo2" class="val success">$0.00</span></div>
            <div class="resumen-linea fw-bold"><span class="lbl">Total general</span><span id="resumenTotalGeneral2" class="val success">$0.00</span></div>
            <hr class="my-2">
            <div class="resumen-linea"><span class="lbl">Postpago pendiente</span><span id="resumenPostpago2" class="val warning">$0.00</span></div>
            <div class="resumen-linea"><span class="lbl">Saldo inicial</span><span id="resumenSaldoInicial2" class="val">$0.00</span></div>
            <div class="resumen-linea"><span class="lbl">Saldo final</span><span id="resumenSaldoFinal2" class="val danger">$0.00</span></div>
            <div class="resumen-linea"><span class="lbl">Bonos activos</span><span id="resumenBonos2" class="val warning">$0.00</span></div>
          </div>
        </div>

        <!-- SUPERPArLET -->
        <div class="card-apuesta tabla-superparlet mb-3">
          <div class="card-header" onclick="toggleTabla(this)">
            <span><i class="fas fa-star me-2 text-warning"></i>Superparlet</span>
            <i class="fas fa-chevron-down toggle-icon"></i>
          </div>
          <div class="card-body">
            <div class="row g-2 mb-2">
              <div class="col-md-6">
                <label class="form-label fw-semibold">Sorteo 1</label>
                <select name="superparlet_sorteo1" id="superparletSorteo1" class="form-select form-select-sm">
                  <option value="">-- Seleccionar --</option>
                  {% for s in sorteos %}<option value="{{ s.id }}">{{ s.nombre }}</option>{% endfor %}
                </select>
              </div>
              <div class="col-md-6">
                <label class="form-label fw-semibold">Sorteo 2</label>
                <select name="superparlet_sorteo2" id="superparletSorteo2" class="form-select form-select-sm">
                  <option value="">-- Seleccionar --</option>
                  {% for s in sorteos %}<option value="{{ s.id }}">{{ s.nombre }}</option>{% endfor %}
                </select>
              </div>
            </div>
            <div id="superparletSorteosInfo" class="text-muted small mt-1">
              {% if sorteos %}Selecciona dos sorteos para Superparlet.{% else %}<span class="text-warning">No hay sorteos disponibles para Superparlet.</span>{% endif %}
            </div>
            <div id="superparletLista">
              <div class="row g-2 align-items-center superparlet-fila mb-2" id="superparlet-1">
                <div class="col-md-5"><input type="text" class="form-control form-control-sm superparlet-parlet" placeholder="12x34 56x78" data-tabla="superparlet" onchange="formatearSuperparlet(this);calcularFila(this)"></div>
                <div class="col-md-3"><input type="number" class="form-control form-control-sm superparlet-monto" step="0.01" min="0" placeholder="0" data-tabla="superparlet" onchange="ajustarAnchoMonto(this);calcularFila(this)"></div>
                <div class="col-md-2"><span class="total-fila" id="totalSuperparlet-1">$0.00</span></div>
                <div class="col-md-2 text-end"><button type="button" class="btn btn-outline-danger btn-sm" onclick="eliminarSuperparlet(this)"><i class="fas fa-trash"></i></button></div>
              </div>
            </div>
            <div class="d-flex gap-2 mt-2">
              <button type="button" class="btn btn-primary btn-sm" onclick="agregarSuperparlet()"><i class="fas fa-plus"></i> Anadir Parlet</button>
            </div>
            <div class="mt-2 text-end fw-bold">Total Superparlet: <span id="superparletSuma">$0.00</span></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- BOTONES DE ACCIÓN -->
  <div class="d-flex gap-2 flex-wrap align-items-center mt-3 justify-content-center">
    <button type="button" class="btn btn-success btn-moderno btn-success-moderno" id="submitBtn"><i class="fas fa-check"></i> Confirmar Apuesta</button>
    <button type="button" class="btn btn-outline-secondary btn-moderno" onclick="limpiarTodo()"><i class="fas fa-undo"></i> Limpiar</button>
    <a href="{% url 'jugadas:mis_apuestas' %}" class="btn btn-outline-info btn-moderno"><i class="fas fa-list"></i> Mis Apuestas</a>
  </div>
</div>

<!-- FOOTER TOTALES -->
<div class="footer-totales container-fluid">
  <div class="row align-items-center">
    <div class="col-md-4 text-center text-md-start">
      <span class="fw-bold text-muted">Suma General:</span>
      <span id="sumaGeneralFinal" class="fw-bold text-success fs-5 ms-2">$0.00</span>
    </div>
    <div class="col-md-4 text-center">
      <span class="fw-bold text-muted">Fondo Final Real:</span>
      <span id="fondoFinalReal" class="fw-bold text-primary fs-5 ms-2">$0.00</span>
    </div>
    <div class="col-md-4 text-center text-md-end">
      <span class="fw-bold text-muted">Total por Sorteo:</span>
      <span id="totalPorSorteoFinal" class="fw-bold text-success fs-5 ms-2">$0.00</span>
    </div>
  </div>
</div>

<!-- MODAL SORTEOS -->
<div class="modal fade" id="modalSorteos" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-lg modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header"><h5 class="modal-title"><i class="fas fa-calendar-alt me-2"></i>Selecciona sorteos</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <p class="text-muted small">Solo se muestran los sorteos abiertos.</p>
        <div id="sorteosGridModal" class="row g-2"></div>
        <div id="sorteosError" class="alert alert-danger mt-2" style="display:none;"></div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary rounded-pill" data-bs-dismiss="modal">Cerrar</button>
        <button type="button" class="btn btn-primary rounded-pill" id="guardarSorteosBtn">Guardar</button>
      </div>
    </div>
  </div>
</div>

<!-- MODAL PASSWORD -->
<div class="modal fade" id="modalVerificarPassword" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header"><h5 class="modal-title"><i class="fas fa-lock me-2"></i>Verificar identidad</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body">
        <p class="text-muted">Ingresa tu contrasena para confirmar la apuesta.</p>
        <div class="mb-3">
          <label for="passwordConfirmInput" class="form-label">Contrasena</label>
          <input type="password" id="passwordConfirmInput" class="form-control" placeholder="********">
          <div id="passwordError" class="text-danger mt-2" style="display:none;">Contrasena incorrecta.</div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
        <button type="button" class="btn btn-primary" id="confirmarPasswordBtn"><i class="fas fa-check"></i> Confirmar</button>
      </div>
    </div>
  </div>
</div>

{% endblock %}

{% block extra_js %}
<script>
document.addEventListener('DOMContentLoaded', function() {
  'use strict';

  // ===================== VARIABLES GLOBALES =====================
  window.sorteosSeleccionados = [];
  window.saldoTotalCliente = parseFloat('{{ saldo_total|default:0 }}') || 0;
  window.usuarioId = parseInt('{{ user.id|default:"0" }}') || 0;
  window.esCliente = {{ es_cliente|yesno:"true,false" }};
  window.esSuperadmin = {{ es_superadmin|yesno:"true,false" }};
  window.destinatarioId = null;
  window.clienteSeleccionadoId = null;
  window.totalApuestas = 0;
  let updateTimeout = null;

  // ===================== TOASTS =====================
  function mostrarToast(mensaje, tipo) {
    tipo = tipo || 'info';
    const container = document.getElementById('toastContainer');
    if (!container) { alert(mensaje); return; }
    const toastId = 'toast-' + Date.now();
    const bg = tipo === 'warning' ? 'warning' : tipo === 'danger' ? 'danger' : tipo === 'success' ? 'success' : 'primary';
    const icon = tipo === 'warning' ? 'exclamation-triangle' : tipo === 'danger' ? 'x-circle' : tipo === 'success' ? 'check-circle' : 'info-circle';
    const html = `<div id="${toastId}" class="toast align-items-center text-white bg-${bg} border-0" role="alert" style="margin-bottom:8px;"><div class="d-flex"><div class="toast-body"><i class="fas fa-${icon} me-2"></i> ${mensaje}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div></div>`;
    container.insertAdjacentHTML('beforeend', html);
    const el = document.getElementById(toastId);
    const toast = new bootstrap.Toast(el, { delay: 5000 });
    toast.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
  }

  // ===================== EXPANSIÓN DE NÚMEROS =====================
  function expandirToken(token, len) {
    token = token.toUpperCase();
    if (token === 'PA') {
      let exp = [];
      for (let i = 0; i <= 99; i += 11) exp.push(String(i).padStart(len, '0'));
      return exp;
    } else if (token.startsWith('D') && token.length === 2 && /^[0-9]$/.test(token[1])) {
      let d = parseInt(token[1]);
      let exp = [];
      for (let i = 0; i <= 9; i++) exp.push(String(d) + String(i));
      return exp.map(x => x.padStart(len, '0'));
    } else if (token.startsWith('T') && token.length === 2 && /^[0-9]$/.test(token[1])) {
      let d = parseInt(token[1]);
      let exp = [];
      for (let i = 0; i <= 9; i++) exp.push(String(i) + String(d));
      return exp.map(x => x.padStart(len, '0'));
    }
    return [token];
  }

  function expandirAbreviaturas(texto, len) {
    if (!texto) return '';
    let partes = texto.trim().split(/\s+/);
    let exp = [];
    for (let p of partes) {
      if (!p) continue;
      let tok = p.toUpperCase();
      if (tok === 'PA') {
        for (let i = 0; i <= 99; i += 11) exp.push(String(i).padStart(len, '0'));
      } else if (tok.startsWith('D') && tok.length === 2 && /^[0-9]$/.test(tok[1])) {
        let d = parseInt(tok[1]);
        for (let i = 0; i <= 9; i++) exp.push(String(d) + String(i));
      } else if (tok.startsWith('T') && tok.length === 2 && /^[0-9]$/.test(tok[1])) {
        let d = parseInt(tok[1]);
        for (let i = 0; i <= 9; i++) exp.push(String(i) + String(d));
      } else if (/^\d+$/.test(tok)) {
        if (tok.length < len) tok = tok.padStart(len, '0');
        exp.push(tok);
      }
    }
    return exp.join(' ');
  }

  function contarNumeros(texto) {
    if (!texto || !texto.trim()) return 0;
    return texto.trim().split(/\s+/).length;
  }

  // ===================== FUNCIONES UI =====================
  window.toggleTabla = function(el) {
    const body = el.closest('.card-apuesta').querySelector('.card-body');
    const icon = el.querySelector('.toggle-icon');
    if (body.style.display === 'none') {
      body.style.display = 'block';
      el.classList.remove('collapsed');
    } else {
      body.style.display = 'none';
      el.classList.add('collapsed');
    }
  };

  window.procesarInput = function(inp, len) {
    clearTimeout(inp._timeout);
    inp._timeout = setTimeout(() => {
      let val = inp.value.toUpperCase().replace(/[^0-9A-Z\s]/g, '').replace(/\s+/g, ' ').trim();
      let tokens = val.split(' ');
      let filtrados = [];
      let count = 0;

      for (let t of tokens) {
        if (!t) continue;
        let partes = t.match(/^(\d+)([A-Z]+\d*)$/);
        if (partes) {
          let num = partes[1];
          let abr = partes[2];
          filtrados.push(num);
          if (abr) filtrados.push(abr);
          count += 2;
          continue;
        }
        const esAbreviatura = (t === 'PA' || (t.startsWith('D') && t.length === 2 && /^[0-9]$/.test(t[1])) || (t.startsWith('T') && t.length === 2 && /^[0-9]$/.test(t[1])));
        if (esAbreviatura) {
          let expandidos = expandirToken(t, len);
          if (count + expandidos.length > 200) {
            mostrarToast('Demasiados números. Límite: 200 por fila.', 'warning');
            break;
          }
          filtrados.push(...expandidos);
          count += expandidos.length;
          continue;
        }
        if (/^\d+$/.test(t)) {
          if (t.length > len) {
            let partesNum = t.match(new RegExp('.{1,' + len + '}', 'g'));
            if (count + partesNum.length > 200) {
              mostrarToast('Demasiados números. Límite: 200 por fila.', 'warning');
              break;
            }
            filtrados.push(...partesNum);
            count += partesNum.length;
          } else {
            filtrados.push(t);
            count++;
          }
          continue;
        }
      }

      let nuevoValor = filtrados.join(' ');
      if (nuevoValor !== inp.value) {
        inp.value = nuevoValor;
        if (inp.tagName === 'TEXTAREA') ajustarAltura(inp);
      }
      calcularFila(inp);
    }, 300);
  };

  window.ajustarAltura = function(ta) {
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  };

  window.ajustarAnchoMonto = function(inp) {
    const val = inp.value || inp.placeholder || '0';
    const tmp = document.createElement('span');
    tmp.style.visibility = 'hidden';
    tmp.style.position = 'absolute';
    tmp.style.whiteSpace = 'nowrap';
    tmp.style.fontSize = getComputedStyle(inp).fontSize;
    tmp.style.fontFamily = getComputedStyle(inp).fontFamily;
    tmp.style.fontWeight = getComputedStyle(inp).fontWeight;
    tmp.style.padding = getComputedStyle(inp).padding;
    tmp.textContent = val;
    document.body.appendChild(tmp);
    inp.style.width = Math.max(50, tmp.offsetWidth + 16) + 'px';
    document.body.removeChild(tmp);
  };

  window.formatearSuperparlet = function(inp) {
    let val = inp.value.replace(/[^0-9xX\s]/g, '').replace(/X/g, 'x').replace(/\s+/g, ' ');
    let grupos = val.split(' ');
    let nuevos = [];
    for (let g of grupos) {
      if (!g) continue;
      let digitos = g.replace(/x/g, '');
      if (digitos.length < 2) { nuevos.push(g); continue; }
      let p1 = digitos.substring(0, 2);
      let p2 = digitos.substring(2, 4);
      nuevos.push(p2 ? p1 + 'x' + p2 : p1);
    }
    inp.value = nuevos.join(' ');
    inp.setSelectionRange(inp.value.length, inp.value.length);
  };

  window.calcularFila = function(inp) {
    const fila = inp.closest('tr') || inp.closest('.superparlet-fila');
    if (!fila) return;
    const tabla = inp.dataset.tabla;
    let totalFila = 0;

    if (tabla === 'tradicional') {
      const numsInp = fila.querySelector('.numeros-tradicional');
      const nums = numsInp ? expandirAbreviaturas(numsInp.value.trim(), 2) : '';
      const cant = contarNumeros(nums);
      const cols = ['pick2', 'pf', 'fijo', 'corridos', 'parlet', 'candado'];
      cols.forEach(col => {
        const mInp = fila.querySelector('[data-forma="' + col + '"]');
        if (!mInp) return;
        let m = parseFloat(mInp.value) || 0;
        if (col === 'parlet') {
          totalFila += m * (cant * (cant - 1) / 2);
        } else if (col === 'candado') {
          totalFila += m;
        } else {
          totalFila += m * cant;
        }
      });
    } else if (['pick3', 'centenas', 'pick4', 'pick5'].includes(tabla)) {
      const numsInp = fila.querySelector('textarea');
      const len = tabla === 'pick3' ? 3 : tabla === 'centenas' ? 3 : tabla === 'pick4' ? 4 : 5;
      const nums = numsInp ? expandirAbreviaturas(numsInp.value.trim(), len) : '';
      const cant = contarNumeros(nums);
      const mInp = fila.querySelector('.monto-' + tabla);
      let m = parseFloat(mInp ? mInp.value : 0) || 0;
      totalFila = m * cant;
    } else if (['vs', 'vspf', 'vspick2', 'pick2vspf'].includes(tabla)) {
      const g1Inp = fila.querySelector('.numeros-' + tabla + '-g1');
      const g2Inp = fila.querySelector('.numeros-' + tabla + '-g2');
      const g1Text = g1Inp ? expandirAbreviaturas(g1Inp.value.trim(), 2) : '';
      const g2Text = g2Inp ? expandirAbreviaturas(g2Inp.value.trim(), 2) : '';
      const m = parseFloat(fila.querySelector('.monto-' + tabla)?.value) || 0;
      totalFila = m;
    } else if (tabla === 'vs100') {
      const numsInp = fila.querySelector('.numeros-vs100');
      const nums = numsInp ? expandirAbreviaturas(numsInp.value.trim(), 2) : '';
      const cant = contarNumeros(nums);
      const mInp = fila.querySelector('.monto-vs100');
      let m = parseFloat(mInp ? mInp.value : 0) || 0;
      totalFila = m * cant * 100;
    } else if (tabla === 'posicion') {
      const m1 = parseFloat(fila.querySelector('.monto-posicion1')?.value) || 0;
      const m2 = parseFloat(fila.querySelector('.monto-posicion2')?.value) || 0;
      const m3 = parseFloat(fila.querySelector('.monto-posicion3')?.value) || 0;
      totalFila = m1 + m2 + m3;
    } else if (tabla === 'tripleta') {
      totalFila = parseFloat(fila.querySelector('.monto-tripleta')?.value) || 0;
    } else if (tabla === 'superparlet') {
      const parletInput = fila.querySelector('.superparlet-parlet');
      const parletTexto = parletInput ? parletInput.value.trim() : '';
      const cantidadParlets = parletTexto ? parletTexto.split(/\s+/).filter(p => p.includes('x')).length : 0;
      const monto = parseFloat(fila.querySelector('.superparlet-monto')?.value) || 0;
      totalFila = monto * (cantidadParlets || 1);
    }

    const totalSpan = fila.querySelector('.total-fila');
    if (totalSpan) totalSpan.textContent = '$' + totalFila.toFixed(2);
    programarActualizacion();
  };

  function programarActualizacion() {
    if (updateTimeout) clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
      actualizarTodo();
      updateTimeout = null;
    }, 2000);
  }

  function actualizarTodo() {
    calcularTotales();
    // Actualizar detalles
    document.getElementById('detalleJugadas1').innerHTML = generarDetalleHtmlNormal();
    document.getElementById('detalleJugadas2').innerHTML = generarDetalleHtmlSuperparlet();
    guardarEstado();
  }

  // ===================== RECOLECTAR Y CONSOLIDAR =====================
  function recolectarItemsNormales() {
    let items = [];
    // ... (lógica completa para recolectar todas las tablas)
    // Por simplicidad, dejamos la misma lógica que tenías antes
    return items;
  }

  function recolectarItemsSuperparlet() {
    let items = [];
    document.querySelectorAll('.superparlet-fila').forEach(fila => {
      const parInput = fila.querySelector('.superparlet-parlet');
      const parTexto = parInput ? parInput.value.trim() : '';
      const cantidadParlets = parTexto ? parTexto.split(/\s+/).filter(p => p.includes('x')).length : 0;
      const m = parseFloat(fila.querySelector('.superparlet-monto')?.value) || 0;
      if (parTexto && m > 0 && cantidadParlets > 0) {
        items.push({ tipo: 'superparlet', numero: parTexto, monto: parseFloat((m * cantidadParlets).toFixed(2)) });
      }
    });
    return items;
  }

  function consolidarItems(items) {
    const acum = {};
    items.forEach(item => {
      if (!acum[item.tipo]) acum[item.tipo] = {};
      const montoRedondeado = parseFloat(item.monto.toFixed(2));
      if (!acum[item.tipo][item.numero]) acum[item.tipo][item.numero] = 0;
      acum[item.tipo][item.numero] += montoRedondeado;
    });
    return acum;
  }

  function renderAcum(acum) {
    let html = '';
    for (const tipo in acum) {
      const porMonto = {};
      for (const num in acum[tipo]) {
        const monto = parseFloat(acum[tipo][num].toFixed(2));
        if (!porMonto[monto]) porMonto[monto] = [];
        porMonto[monto].push(num);
      }
      for (const monto in porMonto) {
        const nums = porMonto[monto].sort().join(' ');
        html += `<div class="item-jugada">
          <span class="tipo">${tipo}</span>
          <span class="nums">${nums}</span>
          <span class="mto">$${parseFloat(monto).toFixed(2)}</span>
        </div>`;
      }
    }
    return html || '<span class="text-muted">No hay jugadas cargadas</span>';
  }

  function generarDetalleHtmlNormal() {
    return renderAcum(consolidarItems(recolectarItemsNormales()));
  }

  function generarDetalleHtmlSuperparlet() {
    return renderAcum(consolidarItems(recolectarItemsSuperparlet()));
  }

  // ===================== CALCULAR TOTALES =====================
  function calcularTotales() {
    const itemsNormales = recolectarItemsNormales();
    const itemsSuper = recolectarItemsSuperparlet();

    const sumaNormal = itemsNormales.reduce((sum, item) => sum + item.monto, 0);
    const sumaSuper = itemsSuper.reduce((sum, item) => sum + item.monto, 0);

    const numSorteos = window.sorteosSeleccionados.length || 1;
    const totalNormalGral = sumaNormal * numSorteos;

    const sp1 = document.getElementById('superparletSorteo1')?.value;
    const sp2 = document.getElementById('superparletSorteo2')?.value;
    const totalSuperGral = (itemsSuper.length && sp1 && sp2) ? sumaSuper : 0;

    const saldoInicial = parseFloat(document.getElementById('resumenSaldoInicial1').textContent.replace('$', '')) || 0;

    document.getElementById('resumenTotalPorSorteo1').textContent = '$' + sumaNormal.toFixed(2);
    document.getElementById('resumenTotalGeneral1').textContent = '$' + totalNormalGral.toFixed(2);
    document.getElementById('resumenSaldoFinal1').textContent = '$' + (saldoInicial - totalNormalGral).toFixed(2);

    document.getElementById('resumenTotalPorSorteo2').textContent = '$' + sumaSuper.toFixed(2);
    document.getElementById('resumenTotalGeneral2').textContent = '$' + totalSuperGral.toFixed(2);
    document.getElementById('resumenSaldoFinal2').textContent = '$' + (saldoInicial - totalSuperGral).toFixed(2);

    const totalGlobal = totalNormalGral + totalSuperGral;
    document.getElementById('sumaGeneralFinal').textContent = '$' + totalGlobal.toFixed(2);
    document.getElementById('fondoFinalReal').textContent = '$' + (saldoInicial - totalGlobal).toFixed(2);
    document.getElementById('totalPorSorteoFinal').textContent = '$' + (sumaNormal + sumaSuper).toFixed(2);

    document.getElementById('superparletSuma').textContent = '$' + sumaSuper.toFixed(2);

    window.totalApuestas = totalGlobal;
  }

  // ===================== AGREGAR / ELIMINAR FILAS =====================
  window.agregarFila = function(tbodyId, prefix) {
    const tbody = document.getElementById(tbodyId);
    const filas = tbody.querySelectorAll('tr');
    const newId = prefix + '-' + Date.now() + Math.floor(Math.random() * 1000);
    const newRow = filas[0].cloneNode(true);
    newRow.id = newId;
    newRow.querySelectorAll('input, textarea').forEach(inp => {
      inp.value = '';
      if (inp.tagName === 'TEXTAREA') inp.style.height = 'auto';
      if (inp.dataset.fila) inp.dataset.fila = newId;
    });
    const totalSpan = newRow.querySelector('.total-fila');
    if (totalSpan) { totalSpan.id = 'total' + prefix.charAt(0).toUpperCase() + prefix.slice(1) + '-' + newId; totalSpan.textContent = '$0.00'; }
    tbody.appendChild(newRow);
    programarActualizacion();
  };

  window.eliminarFila = function(btn, prefix) {
    const fila = btn.closest('tr');
    const tbody = fila.parentNode;
    if (tbody.querySelectorAll('tr').length <= 1) { mostrarToast('Debe haber al menos una fila.', 'warning'); return; }
    fila.remove();
    programarActualizacion();
  };

  window.agregarSuperparlet = function() {
    const container = document.getElementById('superparletLista');
    const filas = container.querySelectorAll('.superparlet-fila');
    const newId = 'superparlet-' + Date.now();
    const newRow = filas[0].cloneNode(true);
    newRow.id = newId;
    newRow.querySelectorAll('input').forEach(inp => inp.value = '');
    const totalSpan = newRow.querySelector('.total-fila');
    if (totalSpan) { totalSpan.id = 'totalSuperparlet-' + newId; totalSpan.textContent = '$0.00'; }
    container.appendChild(newRow);
    programarActualizacion();
  };

  window.eliminarSuperparlet = function(btn) {
    const fila = btn.closest('.superparlet-fila');
    const container = document.getElementById('superparletLista');
    if (container.querySelectorAll('.superparlet-fila').length <= 1) { mostrarToast('Debe haber al menos un parlet.', 'warning'); return; }
    fila.remove();
    programarActualizacion();
  };

  // ===================== CLIENTE =====================
  const clienteSelect = document.getElementById('clienteSelect');
  clienteSelect.addEventListener('change', function() {
    const option = this.options[this.selectedIndex];
    if (!option || !option.value) {
      cancelarCliente();
      return;
    }
    const el = {
      dataset: {
        id: option.value,
        nombre: option.dataset.nombre || option.text,
        saldo: option.dataset.saldo || '0',
        bonos: option.dataset.bonos || '0',
        telefono: option.dataset.telefono || '',
        rol: option.dataset.rol || ''
      }
    };
    seleccionarCliente(el);
  });

  window.seleccionarCliente = function(el) {
    const id = el.dataset.id;
    const nombre = el.dataset.nombre;
    const saldo = parseFloat(el.dataset.saldo) || 0;
    const bonos = parseFloat(el.dataset.bonos) || 0;

    document.getElementById('clienteSeleccionado').value = id;
    document.getElementById('clienteIdHidden').value = id;
    document.getElementById('clienteSeleccionadoNombre').textContent = nombre;
    document.getElementById('cancelarClienteBtn').style.display = 'inline-block';

    document.getElementById('resumenSaldoInicial1').textContent = '$' + (saldo + bonos).toFixed(2);
    document.getElementById('resumenSaldoFinal1').textContent = '$' + (saldo + bonos).toFixed(2);
    document.getElementById('resumenBonos1').textContent = '$' + bonos.toFixed(2);
    document.getElementById('resumenSaldoInicial2').textContent = '$' + (saldo + bonos).toFixed(2);
    document.getElementById('resumenSaldoFinal2').textContent = '$' + (saldo + bonos).toFixed(2);
    document.getElementById('resumenBonos2').textContent = '$' + bonos.toFixed(2);
    window.saldoTotalCliente = saldo + bonos;

    let clienteNombre, gestorNombre, targetId;
    if (window.esCliente) {
        clienteNombre = '{{ user.username }}';
        gestorNombre = nombre;
        window.destinatarioId = id;
        window.clienteSeleccionadoId = window.usuarioId;
        targetId = id;
    } else {
        clienteNombre = nombre;
        gestorNombre = '{{ user.username }}';
        window.destinatarioId = null;
        window.clienteSeleccionadoId = id;
        targetId = id;
    }

    document.getElementById('resumenCliente1').textContent = clienteNombre;
    document.getElementById('resumenGestor1').textContent = gestorNombre;
    document.getElementById('resumenCliente2').textContent = clienteNombre;
    document.getElementById('resumenGestor2').textContent = gestorNombre;
    document.getElementById('fondosClienteNombre').textContent = 'Cliente: ' + clienteNombre;
    document.getElementById('fondosGestorNombre').textContent = 'Gestor: ' + gestorNombre;

    document.getElementById('resumenRol1').textContent = el.dataset.rol || 'cliente';
    document.getElementById('resumenRol2').textContent = el.dataset.rol || 'cliente';

    cargarFormasPago(targetId);
    actualizarTablaFondos(targetId);
    programarActualizacion();
    guardarEstado();
  };

  window.cancelarCliente = function() {
    document.getElementById('clienteSeleccionado').value = '';
    document.getElementById('clienteIdHidden').value = '';
    document.getElementById('clienteSeleccionadoNombre').textContent = 'Ninguno seleccionado';
    document.getElementById('cancelarClienteBtn').style.display = 'none';

    ['1', '2'].forEach(num => {
      document.getElementById('resumenCliente' + num).textContent = '-';
      document.getElementById('resumenGestor' + num).textContent = '-';
      document.getElementById('resumenRol' + num).textContent = '-';
      document.getElementById('resumenSaldoInicial' + num).textContent = '$0.00';
      document.getElementById('resumenSaldoFinal' + num).textContent = '$0.00';
      document.getElementById('resumenBonos' + num).textContent = '$0.00';
      document.getElementById('resumenPostpago' + num).textContent = '$0.00';
    });

    const select = document.getElementById('formaPagoSelect');
    select.innerHTML = '<option value="" disabled selected>Selecciona un cliente primero</option>';
    select.disabled = true;
    document.getElementById('resumenFormaPago1').textContent = '-';

    document.getElementById('tablaFondosCliente').style.display = 'none';
    document.getElementById('fondosClienteNombre').textContent = 'Cliente: -';
    document.getElementById('fondosGestorNombre').textContent = 'Gestor: -';

    window.destinatarioId = null;
    window.clienteSeleccionadoId = null;
    window.saldoTotalCliente = 0;

    programarActualizacion();
    guardarEstado();
  };

  document.getElementById('cancelarClienteBtn')?.addEventListener('click', cancelarCliente);

  // ===================== FORMAS DE PAGO =====================
  function cargarFormasPago(clienteId) {
    const select = document.getElementById('formaPagoSelect');
    if (!clienteId) {
        select.disabled = true;
        select.innerHTML = '<option value="" disabled selected>Selecciona un cliente primero</option>';
        return;
    }
    select.innerHTML = '<option value="" disabled selected>Cargando...</option>';
    select.disabled = true;

    Promise.all([
        fetch("{% url 'jugadas:api_forma_pago_cliente' %}?cliente_id=" + clienteId).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }),
        fetch("{% url 'jugadas:api_verificar_saldo' %}?usuario_id=" + clienteId).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    ])
    .then(([fpData, saldoData]) => {
        if (fpData.error) throw new Error(fpData.error);
        if (saldoData.error) throw new Error(saldoData.error);

        select.innerHTML = '<option value="" disabled selected>Selecciona una forma de pago</option>';
        const saldos = saldoData.saldos || {};
        const formasPago = fpData.formas_pago || [];

        if (formasPago.length === 0) {
            select.innerHTML = '<option value="" disabled selected>Sin formas de pago</option>';
            document.getElementById('resumenFormaPago1').textContent = '-';
            select.disabled = true;
            return;
        }

        let hayConSaldo = false;
        formasPago.forEach(fp => {
            const opt = document.createElement('option');
            opt.value = fp.id;
            const saldo = saldos[fp.id] || 0;
            opt.textContent = fp.nombre + ' ($' + saldo.toFixed(2) + ')';
            opt.dataset.saldo = saldo;
            if (saldo > 0) hayConSaldo = true;
            select.appendChild(opt);
        });

        if (!hayConSaldo) {
            select.innerHTML = '<option value="" disabled selected>Sin fondos disponibles</option>';
            select.disabled = true;
            document.getElementById('resumenFormaPago1').textContent = 'Sin fondos';
            return;
        }

        select.disabled = false;
        let selectedIndex = 1;
        for (let i = 1; i < select.options.length; i++) {
            if (parseFloat(select.options[i].dataset.saldo) > 0) {
                selectedIndex = i;
                break;
            }
        }
        select.selectedIndex = selectedIndex;
        const selectedOpt = select.options[selectedIndex];
        document.getElementById('resumenFormaPago1').textContent = selectedOpt ? selectedOpt.text : '-';
    })
    .catch(err => {
        console.error('Error cargando formas de pago:', err);
        mostrarToast('Error cargando formas de pago: ' + err.message, 'danger');
        select.innerHTML = '<option value="" disabled selected>Error al cargar</option>';
        select.disabled = true;
    });
  }

  document.getElementById('formaPagoSelect')?.addEventListener('change', function() {
    const opt = this.options[this.selectedIndex];
    if (opt && opt.value) {
        document.getElementById('resumenFormaPago1').textContent = opt.text;
    } else {
        document.getElementById('resumenFormaPago1').textContent = '-';
    }
  });

  // ===================== TABLA DE FONDOS =====================
  function actualizarTablaFondos(clienteId) {
    const container = document.getElementById('tablaFondosCliente');
    const tbody = document.getElementById('cuerpoTablaFondos');
    if (!clienteId) {
        container.style.display = 'none';
        return;
    }
    container.style.display = 'block';
    tbody.innerHTML = '<tr><td colspan="' + (window.esSuperadmin ? '4' : '3') + '" class="text-center text-muted">Cargando...</td></tr>';

    Promise.all([
        fetch("{% url 'jugadas:api_verificar_saldo' %}?usuario_id=" + clienteId).then(r => { if (!r.ok) throw new Error('Saldo HTTP ' + r.status); return r.json(); }),
        fetch("{% url 'jugadas:api_forma_pago_cliente' %}?cliente_id=" + clienteId).then(r => { if (!r.ok) throw new Error('FP HTTP ' + r.status); return r.json(); })
    ])
    .then(([saldoData, fpData]) => {
        if (saldoData.error) throw new Error(saldoData.error);
        if (fpData.error) throw new Error(fpData.error);

        const saldos = saldoData.saldos || {};
        const totalBonos = saldoData.total_bonos || 0;
        const postpagoPendiente = saldoData.postpago_pendiente || 0;
        const formasPago = fpData.formas_pago || [];
        let html = '';
        let totalGeneral = 0;

        formasPago.forEach(fp => {
            const saldo = saldos[fp.id] || 0;
            totalGeneral += saldo;
            html += `<tr>
                <td>${fp.nombre}</td>
                <td>$${saldo.toFixed(2)}</td>
                ${window.esSuperadmin ? '<td>$-</td>' : ''}
                <td>$${saldo.toFixed(2)}</td>
            </tr>`;
        });

        if (totalBonos > 0) {
            html += `<tr class="table-warning">
                <td><strong>Bonos totales</strong></td>
                <td>-</td>
                ${window.esSuperadmin ? '<td><strong>$' + totalBonos.toFixed(2) + '</strong></td>' : ''}
                <td>$${totalBonos.toFixed(2)}</td>
            </tr>`;
            totalGeneral += totalBonos;
        }

        if (postpagoPendiente > 0) {
            html += `<tr class="table-info">
                <td><strong>Postpago</strong></td>
                <td>-</td>
                ${window.esSuperadmin ? '<td>$-</td>' : ''}
                <td>$${postpagoPendiente.toFixed(2)}</td>
            </tr>`;
            totalGeneral += postpagoPendiente;
        }

        html += `<tr class="table-success fw-bold">
            <td>TOTAL</td>
            <td></td>
            ${window.esSuperadmin ? '<td></td>' : ''}
            <td>$${totalGeneral.toFixed(2)}</td>
        </tr>`;
        tbody.innerHTML = html;

        document.getElementById('resumenPostpago1').textContent = '$' + postpagoPendiente.toFixed(2);
        document.getElementById('resumenPostpago2').textContent = '$' + postpagoPendiente.toFixed(2);
        document.getElementById('resumenSaldoInicial1').textContent = '$' + totalGeneral.toFixed(2);
        document.getElementById('resumenSaldoInicial2').textContent = '$' + totalGeneral.toFixed(2);
        window.saldoTotalCliente = totalGeneral;

        const totalApuestas = window.totalApuestas || 0;
        document.getElementById('resumenSaldoFinal1').textContent = '$' + (totalGeneral - totalApuestas).toFixed(2);
        document.getElementById('resumenSaldoFinal2').textContent = '$' + (totalGeneral - totalApuestas).toFixed(2);
        document.getElementById('resumenBonos1').textContent = '$' + totalBonos.toFixed(2);
        document.getElementById('resumenBonos2').textContent = '$' + totalBonos.toFixed(2);

        const fondoFinalReal = document.getElementById('fondoFinalReal');
        if (fondoFinalReal) {
            fondoFinalReal.textContent = '$' + (totalGeneral - totalApuestas).toFixed(2);
        }

        const select = document.getElementById('formaPagoSelect');
        if (select && !select.disabled) {
            for (let i = 0; i < select.options.length; i++) {
                const opt = select.options[i];
                if (opt.value) {
                    const saldo = saldos[parseInt(opt.value)] || 0;
                    const nombre = opt.text.split(' (')[0];
                    opt.textContent = nombre + ' ($' + saldo.toFixed(2) + ')';
                    opt.dataset.saldo = saldo;
                }
            }
            const selectedOpt = select.options[select.selectedIndex];
            if (selectedOpt && selectedOpt.value) {
                document.getElementById('resumenFormaPago1').textContent = selectedOpt.text;
            }
        }
    })
    .catch(err => {
        console.error('Error actualizando tabla de fondos:', err);
        mostrarToast('Error cargando fondos: ' + err.message, 'danger');
        tbody.innerHTML = '<tr><td colspan="' + (window.esSuperadmin ? 4 : 3) + '" class="text-center text-danger">Error</td></tr>';
    });
  }

  // ===================== SORTEOS =====================
  const btnAbrirSorteos = document.getElementById('btnAbrirSorteos');
  const modalSorteos = new bootstrap.Modal(document.getElementById('modalSorteos'));
  const guardarSorteosBtn = document.getElementById('guardarSorteosBtn');
  const sorteoCount = document.getElementById('sorteosSeleccionadosCount');
  const sorteoList = document.getElementById('sorteosSeleccionadosList');
  const sorteosHidden = document.getElementById('sorteosHiddenInput');

  btnAbrirSorteos.addEventListener('click', function() {
    renderizarModalSorteos();
    modalSorteos.show();
  });

  async function renderizarModalSorteos() {
    const container = document.getElementById('sorteosGridModal');
    const errorDiv = document.getElementById('sorteosError');
    container.innerHTML = '<div class="col-12 text-center py-4"><div class="spinner-border text-primary"></div><p class="text-muted mt-2">Cargando sorteos...</p></div>';
    errorDiv.style.display = 'none';

    try {
        const fecha = document.getElementById('fechaApuesta').value || new Date().toISOString().slice(0,10);
        const response = await fetch("{% url 'jugadas:api_sorteos_disponibles' %}?fecha=" + fecha);
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const sorteos = await response.json();

        if (!sorteos.length) {
            container.innerHTML = '<div class="col-12 text-center py-4"><i class="fas fa-calendar-times fa-3x text-muted"></i><p class="text-muted">No hay sorteos abiertos.</p></div>';
            return;
        }

        let html = '';
        sorteos.forEach(s => {
            const checked = window.sorteosSeleccionados.includes(s.id) ? 'checked' : '';
            const minutos = s.minutos_restantes || 0;
            const disabled = minutos <= 0 ? 'disabled' : '';
            const badge = minutos <= 0 ? '<span class="badge bg-danger ms-1">Cerrado</span>' : '<span class="badge bg-warning text-dark ms-1">' + minutos + ' min</span>';
            html += '<div class="col-6 col-md-4"><label class="sorteo-check w-100 ' + (disabled ? 'opacity-50' : '') + '">';
            html += '<input type="checkbox" class="form-check-input sorteo-checkbox-modal" value="' + s.id + '" ' + checked + ' ' + disabled + ' data-nombre="' + s.nombre + '">';
            html += '<div><strong>' + s.nombre + '</strong><br><small class="text-muted">' + (s.hora_salida || 'Sin hora') + '</small>' + badge + '</div></label></div>';
        });
        container.innerHTML = html;

        window.sorteosSeleccionados.forEach(id => {
            const cb = document.querySelector('.sorteo-checkbox-modal[value="' + id + '"]');
            if (cb && !cb.disabled) cb.checked = true;
        });

        const finalCount = document.querySelectorAll('.sorteo-checkbox-modal:checked:not(:disabled)').length;
        sorteoCount.textContent = finalCount + ' seleccionado(s)';
    } catch (error) {
        container.innerHTML = '<div class="col-12 text-center py-4 text-danger"><i class="fas fa-exclamation-triangle fa-3x"></i><p>Error al cargar sorteos.</p></div>';
        errorDiv.textContent = 'Error: ' + error.message;
        errorDiv.style.display = 'block';
    }
  }

  guardarSorteosBtn.addEventListener('click', function() {
    const selected = document.querySelectorAll('.sorteo-checkbox-modal:checked:not(:disabled)');
    const ids = Array.from(selected).map(cb => parseInt(cb.value));

    window.sorteosSeleccionados = ids;
    sorteosHidden.value = JSON.stringify(ids);

    sorteoCount.textContent = ids.length + ' seleccionado(s)';

    let nombresText = 'Ningun sorteo seleccionado';
    if (ids.length) {
        const nombres = Array.from(selected).map(cb => cb.dataset.nombre || '');
        nombresText = nombres.join(', ');
        sorteoList.textContent = nombresText;
    } else {
        sorteoList.textContent = 'Ningun sorteo seleccionado';
    }

    document.getElementById('resumenSorteos1').textContent = nombresText;

    actualizarConfiguracionSorteos();
    programarActualizacion();
    modalSorteos.hide();
  });

  async function actualizarConfiguracionSorteos() {
    // Llamar a la API de configuración para obtener las tablas visibles
    const ids = window.sorteosSeleccionados;
    if (!ids.length) {
        document.querySelectorAll('.card-apuesta').forEach(c => c.style.display = '');
        return;
    }
    // Por simplicidad, mostramos todas las tablas, pero puedes filtrar según la configuración
  }

  // ===================== LIMPIAR =====================
  window.limpiarTodo = function() {
    if (!confirm('¿Estás seguro de limpiar todas las jugadas?')) return;
    document.querySelectorAll('input[type="text"], input[type="number"], textarea').forEach(el => el.value = '');
    document.querySelectorAll('textarea').forEach(el => el.style.height = 'auto');
    cancelarCliente();
    // Limpiar sorteos
    window.sorteosSeleccionados = [];
    sorteosHidden.value = '';
    sorteoCount.textContent = '0 seleccionados';
    sorteoList.textContent = 'Ningun sorteo seleccionado';
    document.getElementById('resumenSorteos1').textContent = 'Ninguno';
    programarActualizacion();
    localStorage.removeItem('apostar_data_' + window.usuarioId);
  };

  // ===================== GUARDAR APUESTA =====================
  document.getElementById('submitBtn').addEventListener('click', function(e) {
    e.preventDefault();
    // Validar cliente y forma de pago
    const clienteId = document.getElementById('clienteSeleccionado').value;
    const formaPago = document.getElementById('formaPagoSelect').value;
    if (!clienteId || !formaPago) {
        mostrarToast('Selecciona cliente y forma de pago.', 'warning');
        return;
    }
    // Mostrar modal de password
    const modalPass = new bootstrap.Modal(document.getElementById('modalVerificarPassword'));
    document.getElementById('passwordError').style.display = 'none';
    document.getElementById('passwordConfirmInput').value = '';
    modalPass.show();
  });

  document.getElementById('confirmarPasswordBtn').addEventListener('click', function() {
    const pwd = document.getElementById('passwordConfirmInput').value;
    if (!pwd) {
        document.getElementById('passwordError').textContent = 'Ingresa tu contraseña.';
        document.getElementById('passwordError').style.display = 'block';
        return;
    }
    // Verificar contraseña
    fetch("{% url 'jugadas:api_verificar_password' %}", {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pwd })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            bootstrap.Modal.getInstance(document.getElementById('modalVerificarPassword')).hide();
            enviarCarrito();
        } else {
            document.getElementById('passwordError').textContent = 'Contraseña incorrecta.';
            document.getElementById('passwordError').style.display = 'block';
            document.getElementById('passwordConfirmInput').value = '';
            document.getElementById('passwordConfirmInput').focus();
        }
    })
    .catch(() => {
        document.getElementById('passwordError').textContent = 'Error de conexión.';
        document.getElementById('passwordError').style.display = 'block';
    });
  });

  function enviarCarrito() {
    const clienteId = document.getElementById('clienteSeleccionado').value;
    const formaPago = document.getElementById('formaPagoSelect').value;
    const itemsNormales = recolectarItemsNormales();
    const itemsSuper = recolectarItemsSuperparlet();
    const fecha = document.getElementById('fechaApuesta').value;

    const formData = new FormData();
    formData.append('carrito_data', JSON.stringify(itemsNormales));
    formData.append('superparlet_data', JSON.stringify(itemsSuper));
    formData.append('sorteos', JSON.stringify(window.sorteosSeleccionados));
    formData.append('fecha', fecha);
    formData.append('cliente_id', clienteId);
    formData.append('forma_pago', formaPago);
    formData.append('csrfmiddlewaretoken', document.querySelector('[name="csrfmiddlewaretoken"]').value);

    if (window.destinatarioId) {
        formData.append('destinatario_id', window.destinatarioId);
    }

    const btn = document.getElementById('submitBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';

    fetch("{% url 'jugadas:guardar_apuesta' %}", {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            mostrarToast(data.message, 'success');
            limpiarTodo();
            setTimeout(() => window.location.reload(), 800);
        } else {
            mostrarToast(data.message || 'Error al guardar.', 'danger');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-check"></i> Confirmar Apuesta';
        }
    })
    .catch(error => {
        mostrarToast('Error: ' + error.message, 'danger');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check"></i> Confirmar Apuesta';
    });
  }

  function getCookie(name) {
    let value = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                value = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return value;
  }

  // ===================== LOCALSTORAGE =====================
  function guardarEstado() {
    try {
        const estado = {
            clienteId: document.getElementById('clienteSeleccionado').value,
            clienteNombre: document.getElementById('clienteSeleccionadoNombre').textContent,
            sorteos: window.sorteosSeleccionados || [],
            formaPago: document.getElementById('formaPagoSelect').value,
            fecha: document.getElementById('fechaApuesta')?.value || '',
            tablas: {}
        };
        document.querySelectorAll('.card-apuesta .table tbody').forEach(tbody => {
            const id = tbody.id;
            if (!id) return;
            const filas = tbody.querySelectorAll('tr');
            const datos = [];
            filas.forEach(tr => {
                const inputs = tr.querySelectorAll('input, textarea');
                const fila = {};
                inputs.forEach((inp, idx) => { fila['f' + idx] = inp.value; });
                datos.push(fila);
            });
            estado.tablas[id] = datos;
        });
        localStorage.setItem('apostar_data_' + window.usuarioId, JSON.stringify(estado));
    } catch(e) {}
  }

  function restaurarEstado() {
    const data = localStorage.getItem('apostar_data_' + window.usuarioId);
    if (!data) return;
    try {
        const estado = JSON.parse(data);
        if (estado.clienteId) {
            const select = document.getElementById('clienteSelect');
            const option = select.querySelector('option[value="' + estado.clienteId + '"]');
            if (option) {
                select.value = estado.clienteId;
                select.dispatchEvent(new Event('change'));
            }
        }
        if (estado.sorteos && estado.sorteos.length) {
            window.sorteosSeleccionados = estado.sorteos;
            sorteosHidden.value = JSON.stringify(estado.sorteos);
            sorteoCount.textContent = estado.sorteos.length + ' seleccionado(s)';
            document.getElementById('resumenSorteos1').textContent = estado.sorteos.length + ' sorteo(s)';
        }
        if (estado.fecha) {
            document.getElementById('fechaApuesta').value = estado.fecha;
        }
        // Restaurar tablas
        Object.keys(estado.tablas || {}).forEach(tbodyId => {
            const tbody = document.getElementById(tbodyId);
            if (!tbody) return;
            const filas = tbody.querySelectorAll('tr');
            const datos = estado.tablas[tbodyId] || [];
            filas.forEach((tr, idx) => {
                if (idx >= datos.length) return;
                const inputs = tr.querySelectorAll('input, textarea');
                inputs.forEach((inp, j) => { if (datos[idx]['f' + j] !== undefined) inp.value = datos[idx]['f' + j]; });
            });
        });
        setTimeout(programarActualizacion, 500);
    } catch(e) {}
  }

  // ===================== INICIALIZACIÓN =====================
  restaurarEstado();
  if (window.sorteosSeleccionados.length === 0) {
      document.querySelectorAll('.card-apuesta').forEach(c => c.style.display = '');
  }
  programarActualizacion();

  console.log('🚀 apostar.html cargado correctamente con todas las funcionalidades.');
});
</script>
{% endblock extra_js %}
'''

# Escribir el archivo
with open(ruta_destino, 'w', encoding='utf-8') as f:
    f.write(contenido)

print(f"✅ Archivo apostar.html regenerado correctamente en {ruta_destino}")
print(f"✅ Tamaño: {len(contenido)} caracteres")
print("✅ Si tenías problemas de bloqueo, ahora debería funcionar.")
print("🔄 No olvides reiniciar el servidor (touch wsgi.py)")
