from pathlib import Path

p = Path("/home/LottoBooM/jugadas/templates/jugadas/apostar.html")
src = p.read_text(encoding="utf-8")

if "input.monto.monto-sin-numeros" in src:
    print("SKIP: CSS ya está")
    raise SystemExit(0)

css = """
  /* BLOQUEO_PARLET_CANDADO_V1 */
  input.monto.monto-sin-numeros{
    background: #f3f4f6 !important;
    color: #9ca3af !important;
    border-color: #e5e7eb !important;
    cursor: not-allowed !important;
    opacity: 0.7;
  }
  input.monto.monto-sin-numeros::placeholder{
    color: #d1d5db;
    font-weight: 700;
  }
"""

idx = src.find("</style>")
if idx == -1:
    print("ERROR: no encontré </style>")
    raise SystemExit(1)

src = src[:idx] + css + src[idx:]
p.write_text(src, encoding="utf-8")
print("OK: CSS insertado")
print("input.monto.monto-sin-numeros:", src.count("input.monto.monto-sin-numeros"))
