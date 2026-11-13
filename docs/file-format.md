# Formato de archivos y metadatos

## Alcance

Este formato representa el contenido de un archivo cifrado por fscryptography. No representa `MasterKey` ni el formato textual de nombres cifrados.

- El contenido se procesa mediante Tink Streaming AEAD con el keyset independiente de contenido almacenado en `MasterKey`.
- Los nombres se transforman por separado mediante el codec AEAD de nombres (`~1` + Base64URL).
- Cifrar un directorio transforma exclusivamente su nombre; nunca cifra ni recorre sus hijos.
- El archivo cifrado contiene los metadatos necesarios para interpretar el formato y reconstruir la extensión cuando el nombre permanece visible.
- No se utilizan sidecars, bases de datos ni configuración externa.

El formato no oculta el tamaño aproximado del contenido, el número de segmentos, la existencia del recurso ni la jerarquía del filesystem.

## Formato binario v1.0

Todos los enteros multibyte son unsigned big-endian. No existe padding.

### Cabecera fija (16 bytes)

| Offset | Tamaño | Campo | Valor |
|---:|---:|---|---|
| 0 | 8 | Magic | ASCII `FSCRFIL\\0` |
| 8 | 1 | Major | `0x01` |
| 9 | 1 | Minor | `0x00` |
| 10 | 2 | Flags | Máscara definida abajo |
| 12 | 4 | Header length | Longitud total, incluida metadata |

### Flags

| Bit | Nombre | Semántica |
|---:|---|---|
| 0 | `ORIGINAL_EXTENSION_PRESENT` | La extensión original está presente en metadata |
| 1 | `ENCRYPTED_NAME` | El nombre completo del archivo está cifrado |
| 2–15 | Reservados | Deben ser cero |

### Prefijo de metadata (4 bytes)

Inmediatamente después de la parte fija se encuentran dos longitudes u16 big-endian:

| Offset relativo | Tamaño | Campo |
|---:|---:|---|
| 0 | 2 | `original_extension_length` |
| 2 | 2 | `output_extension_length` |

Después del prefijo aparecen, en ese orden, los bytes UTF-8 de la extensión original y de la extensión de salida. No hay terminadores ni padding.

- La extensión original puede estar ausente (longitud cero); el bit 0 debe coincidir con su presencia.
- Para nombres visibles, la extensión de salida siempre se almacena. Una longitud cero significa que el nombre cifrado no lleva sufijo de salida.
- Para nombres cifrados, ambas longitudes deben ser cero y el bit 0 debe estar apagado.
- Ambas extensiones usan UTF-8 estricto, preservan exactamente sus bytes/caracteres y no se normalizan.
- Cada extensión tiene un máximo estructural de 1.020 bytes UTF-8.
- `header_length = 20 + original_extension_length + output_extension_length`.
- La cabecera máxima es 2.060 bytes.
- No se permiten bytes extra, longitudes inconsistentes, flags reservados, UTF-8 inválido ni metadatos incompatibles con los flags.

La extensión original y la extensión de salida están en claro cuando el nombre permanece visible. La cabecera completa se autentica como AAD; autenticación no equivale a confidencialidad.

### Flujo de contenido

Inmediatamente después de la cabecera comienza el flujo ciphertext producido por Tink Streaming AEAD.

- Plantilla: `AES256_GCM_HKDF_1MB`.
- Primitiva: `StreamingAead`.
- AAD: bytes exactos de la cabecera completa.
- Segmentación, nonces, tags y cierre autenticado: responsabilidad exclusiva de Tink.
- No se añade longitud plaintext ni framing propio de segmentos.
- No se intenta fallback a otra plantilla, versión, backend o clave.

El descifrado debe consumir el flujo hasta EOF y completar la validación final del backend. Un flujo truncado, alterado, reordenado o incompleto no es válido. El plaintext se escribe en un temporal privado y no se publica antes de autenticar el flujo completo.

## Política de extensiones v1.0

### Identificación de la extensión original

La extensión es el último sufijo iniciado por un punto que no sea el primer carácter y que no sea el último carácter del nombre.

| Nombre | Base | Extensión |
|---|---|---|
| `document.txt` | `document` | `.txt` |
| `archive.tar.gz` | `archive.tar` | `.gz` |
| `.profile` | `.profile` | Ninguna |
| `.config.json` | `.config` | `.json` |
| `README` | `README` | Ninguna |
| `report.` | `report.` | Ninguna |

Se preserva la capitalización y la secuencia Unicode exacta. No se aplica NFC/NFD/NFKC/NFKD, lowercase ni casefold.

### `new_extension`

En cifrado con nombre visible, el parámetro es `str | None`:

- `None`: usar la extensión predeterminada `.fscrypt`.
- `""`: no añadir extensión de salida.
- Una cadena no vacía debe comenzar por exactamente un punto y contener al menos un carácter adicional, por ejemplo `.enc` o `.vault`.
- No se añade ni elimina el punto automáticamente.
- El parser del formato rechaza separadores `/`, NUL y sufijos estructuralmente inválidos. Las restricciones adicionales (por ejemplo, caracteres prohibidos en Windows) se aplican al validar el nombre completo contra el perfil del filesystem de destino.
- Se valida el nombre completo resultante contra el límite real del componente de destino.

Cuando se cifra el nombre, la extensión completa forma parte del nombre cifrado. En ese modo, `new_extension` debe ser `None`; no se añade `.fscrypt`.

### Reconstrucción al descifrar

Para nombre visible, la cabecera autentica ambos sufijos. El descifrador:

1. Obtiene el nombre base actual.
2. Exige que el nombre actual termine exactamente en la extensión de salida almacenada, salvo que esta sea vacía.
3. Retira ese sufijo exacto.
4. Añade la extensión original almacenada, si existía.
5. Valida el componente completo y publica sin sobrescribir.

Esto permite extensiones de salida arbitrarias sin configuración externa y mantiene el round-trip del sufijo. Cambiar manualmente el sufijo visible del archivo puede impedir la reconstrucción del nombre, aunque no altera la validez criptográfica del flujo: path y basename no forman parte del AAD. Renombrar/mover el archivo conservando el sufijo de salida no invalida el contenido.

Para nombre cifrado, el descifrador recupera el nombre completo mediante el codec de nombres y no consulta extensiones en claro.

## Reglas de interpretación y publicación

1. Leer los 16 bytes fijos y validar magic, versión y límites.
2. Leer exactamente el prefijo y los bytes de metadata definidos por `header_length`.
3. Validar flags, longitudes, UTF-8 y coherencia entre campos.
4. Abrir Streaming AEAD usando la cabecera exacta como AAD.
5. Descifrar secuencialmente hasta EOF y exigir el cierre autenticado.
6. Validar/reconstruir el nombre destino.
7. Publicar solo después de validar contenido, metadatos y destino sin sobrescritura.

No se devuelve contenido parcial como válido. No se intenta recuperación heurística ni downgrade.

## Nombres y directorios

- El nombre cifrado se procesa con el keyset Tink AEAD independiente y el formato `~1` + Base64URL sin padding.
- El path, basename y nombre padre no forman parte del AAD del contenido.
- Un archivo puede moverse o renombrarse sin invalidar su autenticación criptográfica; la reconstrucción de extensión visible requiere conservar el sufijo autenticado.
- Un directorio cifra únicamente su propio nombre. Sus hijos permanecen intactos.

## Límites y seguridad

- Cabecera: 20–2.060 bytes.
- Extensión original/salida: máximo estructural individual de 1.020 bytes UTF-8; el límite real del filesystem y del componente completo prevalece.
- Validar longitudes antes de reservar memoria variable.
- Los metadatos de extensión visibles están autenticados, no cifrados.
- El formato no ofrece autenticación de identidad del emisor ni protección contra replay de versiones válidas anteriores.
- La seguridad de los keysets depende de la protección del contenedor MasterKey.

## Estado

- [x] Seleccionar Tink Streaming AEAD como responsable del cifrado segmentado.
- [x] Definir la envoltura binaria y cabecera autenticada como AAD.
- [x] Definir metadatos autocontenidos para extensión original y extensión de salida.
- [x] Cerrar la política de identificación de extensiones y `new_extension`.
- [x] Definir el modo de nombre cifrado sin extensiones visibles.
- [x] Implementar serialización y parser estricto de la cabecera v1.0.
- [x] Añadir pruebas unitarias iniciales del parser y de las reglas de extensión.
- [ ] Añadir vectores golden binarios versionados y pruebas de mutación/fuzzing.
- [ ] Implementar cifrado/descifrado de contenido con Tink Streaming AEAD.
- [ ] Implementar operaciones de filesystem y publicación no-replace por plataforma.
- [ ] Validar atomicidad, rollback y round-trip sobre NTFS/ext4 reales.
