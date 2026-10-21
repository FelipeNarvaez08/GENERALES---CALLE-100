# Caso inicial de pruebas: EDIFICIO TRASTEVERE PH

**Documentos:** `Cotizacion_Cop_v1(2).pdf` y `Pol_Cop_101001320(1).pdf`.

Este resultado es una prueba de regresión del extractor y las reglas, no una aprobación técnica del negocio. Los valores detectados por OCR se deben cotejar contra la imagen original.

## Campos identificados

| Campo | Cotización / slip | Póliza emitida | Resultado |
|---|---|---|---|
| N.º de cotización | 17543237 | — | Identificado en el slip |
| N.º de póliza | — | 33-22-101001320 | Identificado en la póliza |
| Tomador / asegurado | EDIFICIO TRASTEVERE PH | EDIFICIO TRASTEVERE | Coincide al normalizar el sufijo PH |
| NIT | 830,020,130 | 830.020.130-6 | Alerta: confirmar que el dígito de verificación corresponde al mismo NIT |
| Vigencia | Anual desde fecha a convenir | 10/10/2026–10/10/2027 | Alerta: comparar contra la instrucción aprobada de emisión |
| Suma asegurada total | $4.883.576.546 | OCR leyó $5.403.576.546 | Alerta OCR; la suma de bienes comunes, muebles y enseres, maquinaria y equipo electrónico indicada en el slip es $4.883.576.546. Revisar carátula y sumas por artículo antes de clasificar como diferencia real |
| Prima anual con IVA del slip | $8.641.553 | Total a pagar OCR: $8.664.013 | Alerta: diferencia de $22.460; revisar valores impresos, IVA y liquidación |
| Terremoto | 3% del valor asegurable de cada artículo afectado por el siniestro, mínimo 3 SMMLV | OCR: 3% del valor asegurable de cada artículo afectado, mínimo 3 SMMLV | Coinciden en el texto extraído; validar la redacción en el documento original |
| Huelga / AMIT | 10% de la pérdida, mínimo 1 SMMLV | OCR detectó 20% de la pérdida en un renglón | Alerta OCR de alta prioridad: confirmar porcentaje en la póliza original |
| Incendio / amparo básico | Incendio/rayo sin deducible; demás eventos 10% de la pérdida, mínimo 1 SMMLV | La póliza muestra un deducible ligado al amparo básico | Revisar la cláusula para confirmar cómo aplica la excepción de incendio/rayo |

## Qué prueba este caso

- Normalización del sufijo PH y del formato del NIT.
- Alerta de vigencia cuando la cotización deja la fecha “a convenir”.
- Extracción complementaria OCR de la carátula y cuadros de amparos/deducibles.
- Control específico de terremoto que separa porcentaje, base de cálculo y mínimo en SMMLV.
- Alertas de discrepancia económica y de porcentaje de deducible extraído por OCR.
- Hallazgos no verificables cuando no existe evidencia legible suficiente, para evitar afirmar una coincidencia que el sistema no puede demostrar.

## Limitaciones observadas

El OCR de la carátula no lee de forma fiable todos los importes y parte del cuadro de deducibles. En el resultado Excel quedan alertas/no verificables para inspección visual. Antes de declarar el módulo listo para producción, se debe calibrar con más pólizas de Copropiedades de distintas versiones, validar cada deducible por amparo y aprobar una matriz de reglas con el equipo técnico.
