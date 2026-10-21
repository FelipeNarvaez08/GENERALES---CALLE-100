# Auditoría técnica de pólizas — módulo Copropiedades

Aplicación Streamlit para auditar lotes de 1 a 20 negocios comparando slip/cotización contra póliza emitida. Incluye OCR complementario de tablas escaneadas, reglas determinísticas, IA semántica opcional con Ollama, revisión humana y Excel descargable.

> **Estado:** versión piloto avanzada para pruebas técnicas. No es un dictamen automático ni debe usarse en producción sin calibración con los clausulados vigentes, revisión de seguridad y aprobación del área técnica/jurídica. La OCR puede confundir caracteres; siempre se conserva evidencia para confirmación humana.

## Qué controla

- Identidad: tomador, asegurado, beneficiario y NIT, con alerta cuando la cotización omite el dígito de verificación.
- Ubicación: ciudad y dirección con comparación conservadora.
- Vigencia: alerta cuando el slip deja la fecha “a convenir”; comparación de fechas explícitas cuando existen.
- Valores económicos: suma asegurada total, prima, IVA y total a pagar cuando son extraíbles.
- Amparos: controles de presencia textual para RC extracontractual, rotura de maquinaria, equipo electrónico, sustracción con violencia, vidrios y asistencia.
- Deducibles: inventario de fragmentos extraídos y control dedicado de terremoto. El control especial intenta comparar **porcentaje**, **base de cálculo** (por ejemplo, valor asegurable de cada artículo afectado por el siniestro vs. valor de la pérdida) y **mínimo en SMMLV**.
- Evidencia: fragmentos de texto/OCR para que el analista valide la cláusula en el PDF original.
- Revisión humana: Pendiente, Confirmado, Falso positivo, Corregido o No aplica, más comentarios.
- Excel: pestañas Hallazgos, Resumen y Campos extraídos.

## Ejecutar en Mac / Windows / Linux

Recomendado Python 3.11.

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS/Linux
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Tesseract OCR debe estar instalado en el sistema para OCR fuera de Docker. En macOS con Homebrew:

```bash
brew install tesseract tesseract-lang
```

Si `spa` no aparece en `tesseract --list-langs`, instala los datos de español o ejecuta OCR con los idiomas disponibles. El OCR se puede desactivar en el panel lateral, pero las tablas escaneadas pueden quedar sin lectura.

## Cómo agregar Ollama

1. Instala Ollama en la máquina que ejecutará el modelo: https://ollama.com/download
2. En Terminal, descarga un modelo. Para comenzar, prueba:

```bash
ollama pull qwen2.5:7b
ollama list
```

3. Confirma que la API responde localmente:

```bash
curl http://localhost:11434/api/tags
```

4. Ejecuta Streamlit en esa máquina. En la barra lateral activa “Ejecutar revisión semántica con Ollama”, modelo `qwen2.5:7b` y URL `http://localhost:11434`.
5. Si Streamlit está dentro de Docker y Ollama está instalado en el host, usa `http://host.docker.internal:11434` (en Docker Desktop) o la IP privada del servidor donde corre Ollama. La URL `localhost` dentro del contenedor apunta al contenedor, no al host.
6. Si Streamlit está alojado en la nube, instalar Ollama en tu Mac no hace que la app de nube pueda acceder automáticamente a él. Debes alojar Ollama en el mismo servidor/red privada, o usar una API cloud autorizada. No expongas el puerto 11434 directamente a internet.

La IA produce propuestas de hallazgos; no es fuente de verdad, no reemplaza reglas y no aprueba pólizas. Revisa siempre el texto de evidencia y el PDF original.

## Acceso desde varios computadores

### Prueba en una red local

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Los equipos autorizados abren `http://IP-PRIVADA-DEL-SERVIDOR:8501`. El firewall debe permitir el puerto solo en la red de confianza. Esto no implementa autenticación.

### Servidor propio / Docker

En un servidor Linux aprobado por la compañía, instala Docker y Docker Compose, copia el proyecto (sin documentos reales de clientes si no son necesarios) y ejecuta:

```bash
docker compose up -d --build
```

Para producción, publica la aplicación detrás de un proxy HTTPS y autenticación corporativa/SSO o VPN; añade autorización por usuario, base de datos persistente, auditoría de acciones, backups, límites de carga, antivirus y política de retención/borrado. El Docker Compose de ejemplo es para despliegue controlado, no una configuración de seguridad completa.

### ¿Streamlit Community Cloud?

Es práctico para demostraciones con datos sintéticos. **No lo recomiendo para pólizas reales de la compañía**: la documentación/condiciones de Streamlit Community Cloud limitan el procesamiento de información sensible y datos identificables. Revisa términos y aprobación interna antes de subir documentos. En cualquier plataforma, no publiques los PDF de muestra ni documentos de clientes en un repositorio público.

## Arquitectura

- `app.py`: UI, lotes, asociación de pares, tablero, revisión humana y descarga.
- `audit_core/extract.py`: extracción nativa + OCR y campos básicos con metadatos de páginas.
- `audit_core/rules.py`: utilidades numéricas/fechas y despacho por producto.
- `audit_core/rules_copropiedades.py`: controles de Copropiedades, deducibles y terremoto.
- `audit_core/ai_review.py`: comparación semántica opcional con Ollama.
- `audit_core/reporting.py`: libro Excel.
- `tests/`: pruebas de regresión y reglas.
- `muestras/`: PDFs del caso Trastevere, solo para pruebas autorizadas.

## Pruebas

```bash
pytest -q
```

## Límites conocidos que deben cerrarse antes de producción

- La segmentación automática de todos los deducibles en múltiples formatos no puede considerarse infalible. El módulo extrae inventarios de texto y hace una comparación especial de terremoto; se debe calibrar con más ejemplos de cada formato de emisión y anexos.
- El OCR puede confundir `3%`/`8%`, signos de porcentaje, tildes, puntos de miles y números. El hallazgo debe revisarse contra la página original.
- El control de amparos es de presencia textual; no interpreta por completo condiciones generales, exclusiones, garantías, sublímites, cláusulas particulares ni precedencias contractuales.
- No hay login, roles, base de datos persistente, auditoría de accesos ni almacenamiento multiusuario en esta versión. Las validaciones humanas se mantienen en la sesión y se conservan al descargar el Excel.
- El proyecto incluye PDFs reales de prueba. Antes de compartirlo, elimina `muestras/*.pdf` y el Excel de resultados si no tienes autorización expresa para distribuirlos.

## Publicación en un dominio con HTTPS y acceso restringido (Docker + Caddy)

Esta es la opción recomendada para que varios computadores entren a la misma URL. Usa un servidor/VM autorizado por la compañía con Docker, un dominio propio apuntando a la IP pública y puertos 80/443 permitidos. La aplicación no publica directamente el puerto 8501; Caddy agrega HTTPS y contraseña básica.

1. Copia el proyecto al servidor y elimina los PDF de `muestras/` si no necesitas distribuir el caso.
2. Copia `.env.example` a `.env`; configura `APP_DOMAIN` con tu dominio real y un usuario de acceso.
3. Genera el hash de contraseña con Docker:

```bash
docker run --rm caddy:2 caddy hash-password --plaintext 'TU_CLAVE_LARGA_Y_UNICA'
```

Pega el resultado en `BASIC_AUTH_HASH` de `.env`. No compartas ni subas `.env` a GitHub.

4. Asegura que el DNS `A` del dominio apunte a la IP del servidor. Luego inicia:

```bash
docker compose --profile web up -d --build
```

5. Caddy obtendrá/renovará el certificado TLS automáticamente cuando el dominio y los puertos estén bien configurados. Los usuarios entran por `https://tu-dominio` y usan las credenciales que configuraste.

La autenticación básica es un primer control, no sustituye SSO corporativo, roles por usuario ni auditoría de acceso. Para producción de una aseguradora, sustituir por la autenticación aprobada por TI y restringir el acceso por VPN o políticas de red.

### Habilitar Ollama dentro de Docker

Para añadir un modelo en el mismo servidor (CPU puede ser lento; el modelo requiere almacenamiento y memoria), inicia el perfil `ai` además del perfil web:

```bash
docker compose --profile web --profile ai up -d --build
docker compose exec ollama ollama pull qwen2.5:7b
```

En la app, activa Ollama y deja la URL `http://ollama:11434`. El modelo se descarga una sola vez y queda en el volumen `ollama_data`. El puerto de Ollama no se publica directamente a internet. En un servidor sin RAM suficiente, deja IA desactivada o utiliza una infraestructura de modelos aprobada.
