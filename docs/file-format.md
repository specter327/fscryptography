# Formato de archivos y metadatos

## Alcance

Este formato representa el contenido de un archivo cifrado por fscryptography. No representa `MasterKey` ni el formato textual de nombres cifrados.

- El contenido se procesa mediante Tink Streaming AEAD con el keyset independiente de contenido almacenado en `MasterKey`.
- Los nombres se transforman por separado mediante el codec AEAD de nombres (`~1` + Base64URL).
- El cifrado de un directorio transforma exclusivamente su nombre; no crea un archivo de contenido ni recorre sus hijos.
- El archivo cifrado debe ser autocontenido respecto de la información necesaria para interpretar su formato y recuperar el nombre cuando este permanece visible.
- No se utilizan sidecars, bases de datos ni configuración externa.

El formato no oculta el tamaño aproximado del contenido, el número de segmentos, la existencia del recurso ni la jerarquía del filesystem.

## Decisión de diseño: envoltura mínima sobre Streaming AEAD

Se adopta una cabecera propia pequeña, seguida directamente por el flujo ciphertext producido por Tink Streaming AEAD. La envoltura solo identifica el formato y transporta los metadatos estrictamente necesarios para restaurar el nombre visible. No implementa cifrado, segmentación, nonce, tags ni framing criptográfico propios.

La cabecera completa se proporciona como associated data (AAD) al crear el flujo Streaming AEAD. Por tanto, todos sus bytes quedan autenticados por el backend. El path, el nombre actual y la ruta padre no forman parte del AAD: mover o renombrar el recurso no debe invalidar el contenido.

## Formato binario propuesto v1.0

Todos los enteros multibyte son unsigned big-endian. No existe padding entre campos.

### Cabecera fija

La parte fija ocupa exactamente 16 bytes:

| Offset | Tamaño | Campo | Valor / semántica |
|---:|---:|---|---|
| 0 | 8 | Magic | Bytes ASCII `FSCRFIL\0` |
| 8 | 1 | Major version | `0x01` |
| 9 | 1 | Minor version | `0x00` |
| 10 | 2 | Flags | Máscara de bits definida abajo |
| 12 | 4 | Header length | Longitud total de cabecera, incluidos los metadatos |

La cabecera se interpreta antes de inicializar el descifrador. Se rechaza cualquier magic incorrecto, versión no soportada, flag desconocido, longitud fuera de límites o cabecera truncada.

### Flags

| Bit | Nombre | Semántica |
|---:|---|---|
| 0 | `ORIGINAL_EXTENSION_PRESENT` | La cabecera incluye la extensión original visible como metadato UTF-8 |
| 1 | `ENCRYPTED_NAME` | El nombre completo del archivo se transformó mediante el codec de nombres |
| 2–15 | Reservados | Deben ser cero en v1 |

Combinaciones válidas:

- Nombre visible: bit 1 apagado. La cabecera incluye siempre el metadato de extensión original, si el nombre de origen tenía una extensión conforme a la política de extensión finalmente aprobada.
- Nombre cifrado: bit 1 encendido y bit 0 apagado. La extensión forma parte del nombre cifrado y no se duplica en claro dentro de la cabecera.
- No se admiten metadatos de extensión junto con `ENCRYPTED_NAME`.

### Metadato de extensión original

Cuando `ORIGINAL_EXTENSION_PRESENT` está activo, los bytes desde el offset 16 hasta `header_length - 1` son exactamente la extensión original codificada en UTF-8 estricto. Se conserva la secuencia UTF-8 sin normalización Unicode. La extensión incluye el punto inicial cuando la política de extensión la reconoce como tal.

Cuando el flag está apagado, `header_length` debe ser exactamente 16. Cuando está activo, `header_length` debe ser mayor que 16 y no superar 1.036 bytes (16 bytes fijos + máximo conservador de 1.020 bytes UTF-8, correspondiente a 255 unidades UTF-16 de un componente Win32). El límite efectivo del filesystem y la longitud real del componente prevalecen; la implementación debe consultar y validar ambos cuando sea posible.

No se permiten campos adicionales, extensiones desconocidas, bytes sobrantes dentro de la cabecera ni UTF-8 inválido. La extensión se trata como metadato no confiable hasta que el flujo Streaming AEAD haya autenticado correctamente la cabecera.

### Flujo de contenido

Inmediatamente después de la cabecera comienza el flujo ciphertext de Tink Streaming AEAD. No se antepone ni se añade un segundo framing de segmentos.

- Plantilla/keyset: `AES256_GCM_HKDF_1MB`.
- Primitiva: `StreamingAead`.
- AAD: bytes exactos de la cabecera completa.
- Segmentación, nonces, tags, autenticación de segmentos y marcador de finalización: responsabilidad exclusiva de Tink.
- No se almacena una longitud plaintext propia; el final del archivo delimita el flujo y Tink debe validar el segmento final.
- No se intenta interpretar el ciphertext con otro backend, plantilla, versión o clave.

El descifrado debe consumir el flujo hasta EOF y completar la validación final del backend. Un archivo truncado, alterado, reordenado o incompleto no se considera válido. El plaintext producido durante el procesamiento se escribe únicamente en un temporal privado; nunca se publica como archivo definitivo antes de que la autenticación final haya concluido.

## Reglas de interpretación

1. Leer y validar la cabecera fija y sus límites antes de reservar memoria de tamaño variable.
2. Leer exactamente los metadatos indicados por `header_length`.
3. Rechazar magic, versiones, flags, combinaciones o codificaciones no admitidas.
4. Abrir Streaming AEAD con el keyset de contenido y la cabecera exacta como AAD.
5. Descifrar secuencialmente hasta EOF y exigir que Tink valide el cierre completo del flujo.
6. Solo después de autenticar el flujo, usar los metadatos de extensión para preparar el nombre de destino.
7. Publicar el archivo descifrado únicamente después de validar tanto contenido como nombre y de confirmar que el destino puede publicarse sin sobrescritura.

No se devuelve contenido parcial como resultado válido. No se intenta recuperación por heurística, fallback ni downgrade.

## Relación con el nombre del recurso

### Nombre visible

Cuando el nombre no se cifra, el nombre base permanece visible durante el cifrado y la extensión de salida puede cambiar conforme a la política de `new_extension`. La extensión original se conserva en la cabecera autenticada para restaurarla durante el descifrado.

La cabecera no almacena el nombre base: este permanece visible y no debe cambiar como parte de la transformación de extensión.

### Nombre cifrado

Cuando se cifra el nombre, se cifra el componente completo, incluida la extensión original, con el codec de nombres v1 (`~1` + Base64URL sin padding). El flag `ENCRYPTED_NAME` indica esta modalidad. No se almacena la extensión en claro en la cabecera.

La operación de descifrado autentica primero el contenido y valida el nombre cifrado con el keyset de nombres antes de publicar el resultado. La restauración del nombre y la publicación del contenido deben coordinarse según [Operaciones atómicas](atomic-operations.md).

### Independencia de rutas

Ni el path absoluto, ni el nombre del padre, ni el nombre actual del archivo se incluyen en la cabecera o AAD. El archivo cifrado puede moverse dentro del filesystem sin invalidar su contenido. Las reglas de publicación y colisión siguen aplicándose en el destino.

## Límites y seguridad

- La cabecera está limitada a 1.036 bytes.
- El metadato de extensión está limitado a 1.020 bytes UTF-8 como cota estructural; el límite real del filesystem y la longitud del nombre completo pueden imponer un máximo menor.
- El parser debe validar longitudes antes de leer el campo variable.
- El modo de autenticación del contenido depende del keyset Streaming AEAD y de la cabecera como AAD.
- La cabecera no cifra la extensión original. En modalidad de nombre visible, esta metadata queda autenticada pero no confidencial.
- En modalidad de nombre cifrado, la extensión original solo aparece dentro del nombre cifrado.
- El formato no ofrece autenticación de identidad del emisor ni protección contra replay de versiones anteriores válidas.
- La seguridad de los keysets depende de la protección del contenedor MasterKey.

## Dependencia pendiente: extensión de salida y reconstrucción del nombre

El diseño actual conserva la extensión original, pero no registra la extensión que se utilizó para renombrar el archivo cifrado. Esto impide reconstruir de forma general el nombre base durante el descifrado si `new_extension` puede variar por operación.

Ejemplo: si `report.txt` se cifra como `report.locked`, el metadato `.txt` permite recuperar la extensión original, pero no permite deducir de forma inequívoca qué parte del nombre visible debe retirarse para obtener `report`. No se debe asumir que el sufijo cifrado es siempre `.encrypted` ni inferirlo a partir del nombre.

Por tanto, el contrato reversible debe escoger explícitamente una de estas estrategias antes de aprobar el formato:

1. **Sufijo cifrado fijo:** la librería utiliza un único sufijo de salida normativo; el descifrador puede retirarlo sin configuración adicional. En ese caso, `new_extension` no puede ser arbitrario.
2. **Sufijo cifrado suministrado al descifrar:** `decrypt()` recibe el mismo sufijo aplicado durante el cifrado. La aplicación debe conservar y proporcionar ese dato.
3. **Metadatos autocontenidos:** la cabecera almacena tanto la extensión original como la extensión de salida aplicada. Esto requiere definir un esquema de metadatos versionado con longitudes explícitas y ajustar el límite de cabecera.

La tercera estrategia mantiene la recuperación autocontenida y permite extensiones de salida variables, pero modifica el layout propuesto. No se debe implementar el parser ni las operaciones de archivo hasta seleccionar una estrategia y fijar el contrato exacto de ambos sufijos.

## Decisiones pendientes antes de declarar el formato cerrado

1. **Semántica exacta de extensión:** definir cómo se identifica la extensión original, especialmente nombres sin punto, nombres con varios puntos y dotfiles como `.profile`.
2. **Contrato de `new_extension`:** definir si acepta el punto inicial, si se permite cadena vacía/None y cómo se normaliza o rechaza cada entrada. No debe existir normalización silenciosa.
3. **Nombre de salida predeterminado:** fijar la extensión visible que se añade cuando el consumidor no proporciona `new_extension`, o decidir que no se cambia.
4. **Compatibilidad del perfil de metadatos:** confirmar que los límites de extensión y la cabecera propuesta son suficientes para todos los casos de la matriz v1.

Hasta resolver estos puntos, el layout de cabecera y el uso de Streaming AEAD quedan como propuesta técnica v1.0; no deben implementarse como contrato definitivo.

## Estado

- [x] Seleccionar Tink Streaming AEAD como responsable del cifrado segmentado.
- [x] Separar el formato de contenido del contenedor MasterKey y del codec de nombres.
- [x] Definir una envoltura mínima, con cabecera autenticada como AAD.
- [x] Definir que el flujo ciphertext Tink sigue directamente a la cabecera.
- [x] Definir que el descifrado debe validar el final completo del flujo antes de publicar plaintext.
- [ ] Seleccionar cómo se identifica y elimina la extensión de salida durante el descifrado.
- [ ] Aprobar la semántica de extensión original (dotfiles, múltiples puntos y nombres sin extensión) y el contrato exacto de `new_extension`.
- [ ] Actualizar el esquema de metadatos si se elige almacenar la extensión de salida.
- [ ] Aprobar el layout resultante como formato binario de archivo v1.0.
- [ ] Crear vectores golden y pruebas negativas del parser de cabecera.
- [ ] Validar round-trip de archivos vacíos, pequeños, multi-segmento y grandes.
- [ ] Verificar truncamiento, alteración, reordenamiento, AAD incorrecto y cierre incompleto.
- [ ] Implementar operaciones de filesystem y validar sobre NTFS/ext4 reales.

## Propuesta concreta de política de extensión (pendiente de aprobación)

Para cerrar los casos ambiguos se propone el siguiente contrato, sin cambiar todavía el estado del formato a aprobado:

### Identificación de la extensión original

- La extensión es el último sufijo iniciado por un punto que no sea el primer carácter del nombre.
- Un nombre sin punto separador no tiene extensión.
- Un *dotfile* cuyo único punto es el primero no tiene extensión: `.profile` conserva el nombre completo como base.
- En nombres con varios puntos solo se considera extensión el último sufijo: `archive.tar.gz` tiene base `archive.tar` y extensión `.gz`; `.config.json` tiene base `.config` y extensión `.json`.
- Un punto final no constituye una extensión: `report.` se interpreta como base `report.` sin extensión.
- Se conserva exactamente la secuencia original de caracteres y su capitalización. No se aplica normalización Unicode ni conversión de mayúsculas/minúsculas.

### Contrato propuesto de `new_extension`

- Tipo: `str | None`.
- `None`: usar la extensión original; si no existe, no añadir ninguna.
- Cadena vacía `""`: eliminar la extensión visible.
- Una cadena no vacía debe comenzar por exactamente un punto y contener al menos un carácter después de él, por ejemplo `.enc` o `.vault`.
- No se elimina ni añade el punto automáticamente. Entradas sin punto inicial, compuestas solo por puntos, con separadores de ruta, NUL o caracteres no válidos para el perfil de filesystem se rechazan; nunca se normalizan silenciosamente.
- La extensión se valida como un sufijo de un único componente y se vuelve a validar el nombre completo resultante contra los límites reales del destino.
- `new_extension` solo aplica cuando el nombre permanece visible. Si se solicita cifrado del nombre, la extensión completa queda dentro del nombre cifrado y proporcionar `new_extension` distinto de `None` se rechaza.

### Nombre de salida predeterminado propuesto

- Al cifrar con nombre visible y sin `new_extension`, usar `.fscrypt` como extensión de salida, independientemente de la extensión original.
- La extensión original se conserva en la cabecera autenticada y se restaura al descifrar.
- Al descifrar, si no se solicita una extensión alternativa, se restaura exactamente la extensión original; si el archivo original no tenía extensión, no se añade ninguna.
- El sufijo `.fscrypt` no es una señal de autenticidad ni sustituye la validación de magic, versión, cabecera y AEAD.
- Si el nombre se cifra, el nombre completo se transforma mediante el codec de nombres; no se añade `.fscrypt` visible.

### Ejemplos propuestos

| Nombre original | Base | Extensión original | Salida cifrada visible predeterminada |
|---|---|---|---|
| `document.txt` | `document` | `.txt` | `document.fscrypt` |
| `archive.tar.gz` | `archive.tar` | `.gz` | `archive.tar.fscrypt` |
| `.profile` | `.profile` | Ninguna | `.profile.fscrypt` |
| `README` | `README` | Ninguna | `README.fscrypt` |
| `report.` | `report.` | Ninguna | `report..fscrypt` |

La tabla describe únicamente la transformación del sufijo; los nombres resultantes todavía deben superar las restricciones del filesystem y la política de colisiones/no sobrescritura.

**Estado de esta propuesta:** recomendación para revisión. No constituye todavía un contrato normativo ni autoriza la implementación. Se requiere aprobación explícita antes de marcar la semántica de extensión o el formato binario v1.0 como cerrados.

