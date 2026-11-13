# Journal persistente y protocolo de recuperación

## Estado

**Implementación disponible: journal v1 e inspección de solo lectura.** Las operaciones de archivo y directorio persisten transacciones y `Manager.inspect_recovery(parent)` permite inspeccionarlas. No existe resolución automática ni limpieza automática. Se cubren terminaciones abruptas del proceso en GNU/Linux antes y después de persistir cada estado de archivo; sigue pendiente la matriz equivalente en Windows y la validación ante pérdida real de energía.

## Objetivos y límites

El journal debe permitir reconocer una operación interrumpida y reconstruir con evidencia qué recursos pertenecen a ella. La primera implementación de recuperación será de inspección: leerá los registros, comprobará identidades y emitirá un diagnóstico. No borrará, renombrará, reemplazará ni restaurará recursos automáticamente.

La recuperación no se ejecutará al construir `Manager`. Requerirá una llamada explícita del consumidor. Una futura operación de resolución deberá ser separada de la inspección y exigir evidencia suficiente para cada mutación.

El journal no es una copia de seguridad, no sustituye la autenticación de contenido y no hace transaccional al filesystem. No se garantiza durabilidad equivalente en Windows y GNU/Linux.

## Ubicación y aislamiento

Cada operación tendrá un directorio transaccional único, creado dentro del directorio padre de los recursos:

```text
<parent>/
    .fscryptography-txn-<32 lowercase hex>/
        journal.json
        result
```

- El identificador se genera con una fuente criptográfica aleatoria y no se reutiliza.
- En GNU/Linux, el directorio se crea con permisos restrictivos (0700); el archivo de journal con permisos 0600.
- En Windows, los permisos heredados del directorio padre gobiernan el acceso; no se promete endurecimiento de ACL en esta fase.
- No se siguen enlaces simbólicos para el directorio transaccional ni para el journal.
- El temporal de resultado reside dentro del directorio transaccional. Su publicación al directorio padre es un rename dentro del mismo filesystem.
- El nombre de transacción y el nombre de journal se validan estrictamente. No se aceptan rutas absolutas ni componentes con separadores.

Los nombres de recursos se almacenan como componentes individuales, nunca como rutas. El directorio padre se determina por la ruta que el usuario entrega a la operación de inspección; el registro no puede redirigir la recuperación a otro directorio.

## Registro v1

El journal es JSON UTF-8, con codificación canónica (claves ordenadas, separadores compactos, sin BOM ni newline final). Tamaño máximo: 16 KiB. Se rechazan claves duplicadas, campos desconocidos, tipos incorrectos, enteros fuera de rango, UTF-8 inválido y cualquier byte adicional no válido.

Campos obligatorios:

| Campo | Tipo | Semántica |
|---|---|---|
| `format` | entero | Versión del formato de journal: 1 |
| `transaction_id` | string | 32 hex minúsculas; debe coincidir con el sufijo del directorio |
| `operation` | string | `file_encrypt`, `file_decrypt`, `dir_encrypt` o `dir_decrypt` |
| `state` | string | Estado persistido de la transacción |
| `parent_identity` | objeto | Identidad del directorio padre: `device` e `inode` |
| `source_name` | string | Basename original |
| `destination_name` | string | Basename de destino |
| `temporary_name` | string o null | Debe ser `result` para operaciones de archivo; null para renombrado de directorio |
| `source_identity` | objeto | Identidad inicial del origen: `device` e `inode` |
| `result_identity` | objeto o null | Identidad del resultado completo una vez sincronizado |
| `created_ns` | entero | Tiempo UTC de creación en nanosegundos |

Las identidades usan los valores de `st_dev` y `st_ino` obtenidos mediante `stat`/ `fstat`. Si una plataforma no proporciona una identidad estable y utilizable, la recuperación debe marcar el registro como no verificable; no debe degradar la comparación a nombre, tamaño o timestamp.

Los valores de `source_name` y `destination_name` deben ser componentes válidos no vacíos: se rechazan `.`, `..`, NUL, separadores POSIX y separadores Windows. Se valida también que no coincidan cuando la operación requiere un cambio de nombre. No se normaliza Unicode.

## Estados y barreras de persistencia

Estados permitidos:

1. `prepared`: journal creado y sincronizado antes de crear/escribir el resultado.
2. `result_ready`: resultado completo, autenticado cuando aplica, cerrado y sincronizado; su identidad ya está guardada en el journal.
3. `published`: el resultado se ha publicado en el destino y la entrada de destino se ha sincronizado donde el sistema lo permite.
4. `source_removed`: el origen se ha retirado y el cambio de namespace se ha sincronizado donde el sistema lo permite.
5. `complete`: la operación terminó; se puede retirar el directorio transaccional después de persistir el estado.

Cada transición se persiste mediante: escribir un journal temporal exclusivo dentro del directorio transaccional, `flush`, `fsync` del archivo, reemplazar atómicamente `journal.json`, y sincronizar el directorio transaccional en GNU/Linux. La escritura parcial nunca debe reemplazar un journal válido.

La creación del directorio transaccional y su entrada en el padre se sincroniza en GNU/Linux antes de avanzar. Después de publicar el resultado, se sincronizan tanto el directorio padre como el directorio transaccional antes de retirar el origen. Después de retirar el origen, se sincroniza el padre antes de registrar `source_removed`.

En Windows, Python no ofrece en esta implementación un flush verificable y portable del directorio. El journal puede ayudar a diagnosticar estados, pero no se debe anunciar durabilidad de namespace ante pérdida abrupta de energía.

## Orden obligatorio para operaciones de archivo

1. Validar origen y destino y capturar identidad del origen abierto.
2. Crear el directorio transaccional y persistir `prepared`.
3. Crear `result` de forma exclusiva dentro de la transacción.
4. Producir el resultado completo; para descifrado, completar autenticación antes de publicarlo.
5. Sincronizar el archivo `result`, capturar su identidad y persistir `result_ready`.
6. Publicar `result` en el destino con una primitiva atómica no-replace.
7. Sincronizar el padre y el directorio transaccional donde esté soportado.
8. Persistir `published`.
9. Revalidar la identidad del origen y retirarlo únicamente si coincide exactamente.
10. Sincronizar el padre donde esté soportado.
11. Persistir `source_removed`, luego `complete`.
12. Conservar el journal `complete` como evidencia. La limpieza se difiere hasta definir una política de retención y eliminación segura independiente.

Si falla una transición, no se debe continuar con una mutación posterior. Los recursos ya publicados permanecen. El journal debe permanecer disponible para inspección.

## Operaciones de directorio

El renombrado de directorio utiliza el mismo protocolo, pero no tiene archivo `result`: el propio directorio cambia de nombre. El journal se crea y persiste antes del rename; se registra la identidad inicial del directorio; se publica con no-replace; se sincroniza el padre donde esté soportado; y la inspección determina si la identidad aparece bajo el nombre original o el de destino.

La operación nunca recorre ni modifica el contenido del directorio.

## Inspección y clasificación

La inspección es estrictamente de solo lectura. Para cada transacción debe:

1. Abrir el directorio transaccional sin seguir symlinks y comprobar que su nombre cumple el patrón exacto.
2. Abrir el journal como archivo regular, limitar su tamaño y analizarlo con parser estricto.
3. Validar el esquema completo, la versión, el identificador y todos los basenames.
4. Verificar que la identidad del directorio padre coincide con la registrada.
5. Consultar origen, destino y temporal sin seguir symlinks.
6. Comparar identidades observadas con las identidades registradas.
7. Emitir un estado diagnóstico sin cambiar el filesystem.

Clasificaciones mínimas:

- `prepared_no_output`: origen coincide; no existe resultado verificable.
- `result_incomplete_or_unverified`: existe temporal, pero no coincide con una identidad de resultado persistida.
- `result_ready`: temporal coincide con la identidad del resultado; destino no existe y origen coincide.
- `published_source_present`: destino coincide con resultado y origen coincide.
- `published_source_missing`: destino coincide con resultado y el origen no existe.
- `source_removed`: destino coincide con resultado, origen no existe y el estado del journal refleja retirada.
- `ambiguous`: colisión, identidad distinta, symlink, padre distinto, nombre inválido o cualquier combinación no cubierta.
- `corrupt`: journal malformado, desconocido, truncado o incompatible.

Las clasificaciones no autorizan mutaciones. En particular, nunca se elimina un temporal, destino, origen o directorio transaccional durante la inspección.

## Reglas de seguridad

- El journal es entrada no confiable, incluso si está en un directorio oculto.
- No se interpolan rutas del journal; solo se resuelven basenames validados bajo el padre solicitado.
- Nunca se usa `os.replace` para publicar recursos del usuario.
- Nunca se elimina un recurso basándose únicamente en el nombre, tamaño o timestamp.
- Nunca se restaura un origen si ya existe un destino, ni viceversa, sin comparar identidades y contenido según una futura política explícita.
- Cualquier diferencia de identidad, padre, tipo de archivo o estado se clasifica como ambigua y se conserva todo.
- La inspección no requiere ni utiliza la clave maestra: no descifra, autentica ni modifica contenido.
- Los registros no contienen claves, contraseñas, plaintext ni ciphertext.
- No se limpian automáticamente transacciones antiguas ni registros corruptos.

## Pruebas requeridas antes de habilitar el protocolo

- Interrupción simulada después de cada barrera persistente.
- Journal truncado, JSON inválido, claves duplicadas, campos desconocidos y versiones futuras.
- Identificadores y basenames hostiles, traversal, separadores, NUL y Unicode inválido.
- Symlinks en directorio transaccional, journal, temporal, origen y destino.
- Padre reemplazado o movido; identidad de padre distinta.
- Inode/device mismatch en origen, temporal y destino.
- Destino preexistente y colisiones concurrentes.
- Fallo de escritura, fsync, rename, unlink y limpieza.
- Inspección repetida: debe ser idempotente y no modificar ningún recurso.
- Matriz GNU/Linux y Windows, distinguiendo explícitamente las garantías de durabilidad.

## API pública

La API pública expone `Manager.inspect_recovery(parent) -> tuple[RecoveryRecord, ...]`. Cada `RecoveryRecord` es una dataclass congelada con identificador, operación, estado, clasificación y nombres de recursos. La inspección no necesita la clave maestra, no se ejecuta en el constructor y nunca modifica el filesystem. No existe todavía API de resolución.

## Cobertura de endurecimiento añadida

La suite de inspección incluye ahora casos adicionales para:

- JSON vacío, truncado, duplicado, inválido, con BOM, constantes no permitidas y newline no canónico.
- Identidad del directorio padre distinta de la registrada.
- Sustitución del resultado temporal y del destino por objetos con identidad diferente.
- Directorio transaccional presentado como symlink.
- Inspecciones repetidas para comprobar idempotencia y ausencia de mutaciones.
- Fallo inyectado al reemplazar el journal: el registro previo debe permanecer legible.
- Fallo inyectado al sincronizar la entrada del directorio padre: el journal `prepared` debe quedar disponible para inspección.

Estos casos amplían la cobertura de fallos simulados; no equivalen a pruebas de pérdida real de energía ni a pruebas de concurrencia hostil. Siguen pendientes la matriz exhaustiva de fallos en cada operación filesystem, carreras entre validación y mutación, sustitución concurrente del padre/recursos y pruebas sobre filesystems alternativos.

## Terminación abrupta del proceso (GNU/Linux)

La prueba de integración `tests/real_resources/test_crash_recovery.py` usa un proceso hijo y `os._exit` para terminar sin ejecutar `finally`, limpieza de contexto ni cierre ordenado de la aplicación. Se fuerza la terminación inmediatamente antes y después de persistir cada estado de archivo:

- `prepared`
- `result_ready`
- `published`
- `source_retained`
- `source_removed`
- `complete`

La prueba comprueba la clasificación resultante y el estado físico de origen y destino. También ejecuta la inspección varias veces y verifica que no cambie el journal ni el contenido del directorio transaccional.

El estado durable puede ir por detrás del filesystem: si el proceso termina después de publicar pero antes de persistir `published`, el journal conserva `result_ready` mientras el destino ya existe; si el proceso termina después de retirar el origen pero antes de persistir `source_removed`, el journal conserva `source_retained` aunque el destino sea el único recurso visible. Por eso la clasificación se basa en las identidades observadas y no solo en el campo `state`.

La prueba no representa un corte eléctrico ni un fallo del kernel/dispositivo. Tampoco valida la durabilidad física de los datos. La cobertura de terminación abrupta en Windows y las garantías reales de NTFS siguen pendientes.
