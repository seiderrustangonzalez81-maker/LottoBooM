import ast

archivo = 'usuarios/views.py'

try:
    with open(archivo, 'r', encoding='utf-8') as f:
        ast.parse(f.read())
    print("✅ ¡Todo perfecto! Sintaxis OK.")
except SyntaxError as e:
    print(f"\n❌ ERROR DETECTADO EN LA LÍNEA {e.lineno}: {e.msg}")
    print("🔍 Aquí tienes el código. Los espacios se muestran como '·' (puntos) para que veas la sangría:\n")
    
    with open(archivo, 'r', encoding='utf-8') as f:
        lineas = f.readlines()
        
    # Mostrar 4 líneas antes y 4 después del error
    inicio = max(0, e.lineno - 5)
    fin = min(len(lineas), e.lineno + 4)
    
    for i in range(inicio, fin):
        num = i + 1
        # Reemplazamos espacios por puntos y los Tabs por flechas
        linea_visual = lineas[i].rstrip().replace(' ', '·').replace('\t', '->')
        
        if num == e.lineno:
            print(f"👉 {num:3} | {linea_visual}")
        else:
            print(f"   {num:3} | {linea_visual}")
