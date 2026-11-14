# Errores y excepciones

## Contrato público

Las operaciones que modifican recursos devuelven `None` al completarse correctamente. Los fallos se comunican mediante excepciones; no se devuelve `False` como sustituto de un error.

- Los errores de tipo y de valor de los argumentos conservan `TypeError` y `ValueError`.
- Los errores ordinarios del filesystem se conservan como excepciones estándar de Python cuando la operación todavía no ha cruzado una frontera transaccional que requiera reclasificar el estado.
- Los errores propios derivan de `FsCryptographyError`.
- Las traducciones de excepciones conservan la causa mediante `raise ... from exc`, salvo errores que se propagan sin traducción.
- Los mensajes no deben incluir contraseñas, claves, plaintext ni ciphertext completo.

No se garantiza que toda excepción del sistema permanezca sin traducir: la clasificación depende de la etapa de la operación. La matriz siguiente describe el comportamiento implementado.

## Jerarquía de excepciones

Todas las excepciones propias derivan de `FsCryptographyError`, que deriva de `Exception`.

- `FsCryptographyError`
  - `InvalidPathError`
  - `UnsupportedResourceError`
  - `FormatError`
    - `UnsupportedFormatVersionError`
  - `AuthenticationError`
  - `KeyDerivationError`
  - `DestinationConflictError`
  - `NameConstraintError`
  - `BackendError`
  - `ClosedInstanceError`
  - `AtomicOperationError`

### Definiciones

- **FsCryptographyError:** clase base pública para los errores propios de fscryptography.
- **InvalidPathError:** la ruta o el componente no puede utilizarse como entrada. No es un alias general de `FileNotFoundError`; ciertas comprobaciones de anclaje del directorio padre traducen el fallo de apertura a esta categoría.
- **UnsupportedResourceError:** el recurso existe, pero su tipo o condición no está admitido, por ejemplo symlink, reparse point, hard link adicional o tipo de recurso incorrecto.
- **FormatError:** encabezado, framing, metadatos o estructura binaria malformados, incompletos o no reconocibles.
- **UnsupportedFormatVersionError:** versión mayor/menor no admitida. Deriva de `FormatError`; no se intenta downgrade.
- **AuthenticationError:** fallo de autenticación AEAD, contraseña incorrecta al abrir un contenedor protegido, ciphertext alterado o flujo autenticado incompleto. No se distingue públicamente entre contraseña incorrecta y alteración del contenedor protegido.
- **KeyDerivationError:** fallo operativo del backend Argon2id. No se usa para contraseña incorrecta ni para parámetros rechazados antes de ejecutar Argon2id.
- **DestinationConflictError:** el destino ya existe y la publicación no debe reemplazarlo.
- **NameConstraintError:** nombre no representable, reservado o superior al límite del perfil de filesystem.
- **BackendError:** fallo inesperado al generar/serializar keysets Tink o al cifrar mediante Streaming AEAD. No es un contenedor genérico para errores de I/O.
- **ClosedInstanceError:** se intenta iniciar una operación o acceder a una propiedad operativa después de `Manager.close()`.
- **AtomicOperationError:** falla una publicación, sincronización o secuencia de staging/retirada que ya puede haber modificado el namespace. No implica rollback ni garantiza que el filesystem haya vuelto al estado inicial.

## Matriz de clasificación por operación

| Operación / etapa | Condición | Excepción observable |
|---|---|---|
| `generate()` / `Manager(...)` | Tipo de clave o contraseña incorrecto | `TypeError` |
| Apertura MasterKey | Base64 inválido/no canónico, magic, modo, schema, flags, longitudes o framing inválidos | `FormatError` |
| Apertura MasterKey | Versión no soportada | `UnsupportedFormatVersionError` |
| Apertura MasterKey | Falta contraseña o se proporciona para un contenedor sin contraseña | `ValueError` |
| Apertura MasterKey | Contraseña incorrecta o payload protegido alterado | `AuthenticationError` |
| Apertura MasterKey | Fallo Argon2id | `KeyDerivationError` |
| Apertura MasterKey | Keyset Tink inválido, incompleto o de primitive incompatible | `FormatError` |
| Generación MasterKey | Fallo inesperado al generar/serializar keysets o proteger el payload | `BackendError` |
| `change_key()` | La nueva clave falla al abrirse | La excepción de apertura correspondiente; el contexto anterior permanece activo |
| Cualquier operación del gestor | Gestor cerrado antes de iniciar | `ClosedInstanceError` |
| Resolución de ruta | Tipo no admitido o PathLike que devuelve bytes | `TypeError` |
| Resolución/validación de ruta | Ruta no identificable o padre no anclable bajo la política de la plataforma | `InvalidPathError` |
| Inspección de origen | Origen inexistente o error ordinario de stat/open, fuera de las traducciones explícitas | Excepción estándar del sistema, normalmente `FileNotFoundError` u `OSError` |
| Inspección de origen | Symlink, reparse point, hard link adicional o tipo de recurso incorrecto | `UnsupportedResourceError` |
| Validación de nombre/extensión | Argumento mal tipado o extensión inválida | `TypeError` / `ValueError` |
| Validación de nombre | Nombre no representable o fuera del límite del filesystem | `NameConstraintError` |
| Cifrado de archivo | Error de lectura/escritura del stream | Excepción estándar `OSError` |
| Cifrado de archivo | Fallo inesperado del primitive Streaming AEAD | `BackendError` |
| Descifrado de archivo | Encabezado malformado o versión no soportada | `FormatError` / `UnsupportedFormatVersionError` |
| Descifrado de archivo | Fallo del stream autenticado, incluido truncamiento o alteración detectados por Tink | `AuthenticationError` |
| Descifrado de archivo | Error de I/O del stream | Excepción estándar `OSError` |
| Cifrado/descifrado de nombre | Argumento de nombre mal tipado, envelope Base64URL inválido/truncado, o plaintext autenticado que no es UTF-8 válido | `TypeError` / `FormatError` |\n| Cifrado/descifrado de nombre | AEAD no autentica el ciphertext | `AuthenticationError` |\n| Cifrado de nombre | Primitive AEAD falla inesperadamente o devuelve un tipo inválido | `BackendError` |\n| Descifrado de nombre | Plaintext autenticado viola el perfil o el límite de componente | `NameConstraintError` |
| Publicación | Destino existente | `DestinationConflictError` |
| Publicación | Primitiva no-replace no disponible o fallo de publicación | `AtomicOperationError` |
| Transformación | Identidad/metadatos del origen cambian durante el streaming | `AtomicOperationError` |
| Retirada del origen | Falla staging, verificación, eliminación o sincronización después de publicar salida | `AtomicOperationError`; la salida puede permanecer publicada y el origen puede requerir inspección |
| Renombrado de directorio | Conflicto de destino | `DestinationConflictError` |
| Renombrado de directorio | Identidad cambiada o fallo al restaurar/confirmar el rename | `InvalidPathError` o `AtomicOperationError`, según si la restauración se confirmó |

### Fronteras transaccionales relevantes

1. Antes de publicar el resultado, errores de lectura/escritura que sean `OSError` se propagan como errores del sistema; errores de autenticación y formato mantienen su categoría.
2. Un conflicto de destino se expresa como `DestinationConflictError`; no se reemplaza el destino existente.
3. Después de publicar el resultado, la retirada del origen es una fase distinta. Si falla, se usa `AtomicOperationError` porque puede existir ya un resultado válido y el origen puede seguir presente, haberse movido a un nombre temporal o requerir inspección manual.
4. El adaptador interno `load_name_primitive()` traduce fallos al registrar/restaurar un keyset de nombres a `BackendError`; rechaza argumentos de tipo incorrecto con `TypeError` y bytes vacíos con `ValueError`.\n5. El cleanup de temporales es best-effort. Un error de cleanup no debe ocultar el error primario y no se garantiza limpieza tras terminación abrupta.
6. `AtomicOperationError` no significa que la operación se haya revertido. El llamador debe inspeccionar el estado real antes de reintentar.

## Excepciones estándar del sistema

Entre las excepciones estándar que pueden propagarse están:

- `FileNotFoundError`
- `FileExistsError`
- `PermissionError`
- `NotADirectoryError`
- `IsADirectoryError`
- `OSError`
- `TypeError`
- `ValueError`

La preservación depende de la etapa: por ejemplo, ciertos fallos de Windows al publicar o retirar el origen se traducen deliberadamente a `AtomicOperationError`, mientras que un error de lectura del stream se propaga como `OSError`.

## Reglas de clasificación

1. Validar límites y estructura antes de ejecutar operaciones costosas como Argon2id.
2. Rechazar versiones y parámetros no admitidos sin fallback ni downgrade.
3. Clasificar un contenedor protegido que no supera AES-GCM como `AuthenticationError`; no distinguir públicamente contraseña incorrecta de alteración autenticada.
4. Clasificar estructuras inválidas antes de autenticación como `FormatError`.
5. Clasificar truncamiento o alteración de un flujo Streaming AEAD como `AuthenticationError` cuando el backend detecte fallo de autenticación.
6. No confundir una ruta inexistente con un formato inválido.
7. No confundir un destino existente con un error criptográfico.
8. No utilizar `BackendError` como contenedor genérico de cualquier excepción.
9. Preservar la causa original al traducir excepciones.
10. No incluir secretos ni contenido sensible en mensajes, atributos de error o logs.
11. No afirmar rollback cuando el estado final no haya sido confirmado.

## Estado de cobertura

La jerarquía está implementada y exportada desde el paquete raíz. Se ha contrastado la clasificación anterior con las rutas de apertura MasterKey, cifrado/descifrado de archivos, publicación, retirada del origen y renombrado de directorios. La matriz describe el comportamiento de esas rutas; no constituye una auditoría independiente ni una garantía de que cada rama excepcional esté cubierta por un test específico. La suite de contrato y los tests de integración son la evidencia ejecutable; cualquier diferencia detectada por CI debe corregirse en código o documentación antes de declarar cerrada esta tarea.
