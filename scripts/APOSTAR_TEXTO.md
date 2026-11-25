# Procesar texto en Apostar

El texto se revisa línea por línea. **Si una línea contiene un token desconocido, número con longitud incorrecta, monto inválido o sintaxis no admitida, no se habilita Procesar y no se aplica ninguna fila.** No se recortan ni se omiten tokens de una línea válida a medias.

## Sintaxis aceptada

| Destino | Ejemplo |
|---|---|
| Tradicional (Fijo) | \`12 34 56 con 5\` |
| Tradicional (Fijo + Corridos) | \`12 34 con 5 y 2\` |
| Tradicional (Corridos) | \`12 34 corridos 2\` |
| Pick2 | \`pick2 12 34 con 5\` o \`12 34 pick2 con 5\` |
| PF | \`pf 12 34 con 5\` o \`12 34 pf con 5\` |
| Parlet | \`12 34 parlet 2\` |
| Candado (requiere Parlet) | `12 34 56 parlet 2 candado 6` (3 pares × $2) |
| Pick3 | \`pick3 123 456 con 5\` o \`123 456 pick3 con 5\` |
| Centenas Corridas | \`centenas corridas 123 456 con 5\` |
| Pick4 | \`pick4 1234 5678 con 5\` |
| Pick5 | \`pick5 12345 67890 con 5\` |
| VS | \`12 34 vs 56 78 con 5\` |
| VS PF | \`12 34 vspf 56 78 con 5\` |
| VS Pick2 | \`12 34 vspick2 56 78 con 5\` |
| P2 vs PF | \`12 34 pick2vspf 56 78 con 5\` |
| VS100 | \`vs100 12 34 con 5\` |
| Posiciones | \`pos 2 12 34 con 5\` |
| Tripleta | \`tripleta 12 34 56 con 5\` |
| Solo Parlet | \`solo parlet 12 34 56 con 5\` |

Los grupos VS pueden contener cantidades distintas de números: se multiplican las combinaciones de ambos grupos. Todos sus números, sin embargo, deben tener dos dígitos y ambos grupos deben estar presentes. Candado requiere que Parlet esté habilitado en la misma tabla; su importe es un espejo de Parlet por número de combinaciones y no se suma por separado. Si no coincide, el semáforo bloquea Procesar.

## Abreviaturas y continuaciones

- \`T7\` o \`T 7\`: números que terminan en 7; \`D3\` o \`D 3\`: números que empiezan en 3. Una letra T/D aislada sin dígito es un error.
- \`PA\` / \`PAREJAS\`: 00, 11, 22, …, 99.
- \`12V\`: 12 y 21.
- Pares explícitos: \`12x34 con 5\`, \`12x34 56x78 con 5\`; también se puede dejar el par sin monto y luego escribir \`cada parlet 2\`. La instrucción solo completa los pares pendientes, no modifica pares con monto propio.
- Monto en línea siguiente: \`12 34\` seguido por \`5f 10c\`.
- Encabezados entre corchetes y líneas de metadata \`Tarjeta\`, \`Tarieta\` o \`Saldo\` se ignoran.

Montos deben ser positivos, finitos y tener como máximo dos decimales. Pick3, Pick4, Pick5, VS, VS100, Posiciones, Tripleta, Solo Parlet y Centenas Corridas aceptan una instrucción de monto por línea. Pick3 no admite que se pierda uno de varios montos.

## Aplicación segura

1. Pega el texto; se muestran errores de línea/token en vivo.
2. Selecciona sorteo(s) y espera a que terminen de cargar todas las pestañas/formas destino.
3. Activa **Procesar** (no Replica). El botón pasa a verde solo si texto y destinos están válidos.
4. Si existen filas previas, confirma el reemplazo. El mapeo de todas las tablas y sorteos se prepara antes de modificar cualquiera.
