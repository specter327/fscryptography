# Operaciones atómicas y recuperación

## Objetivo

Un fallo no debe destruir el original ni publicar contenido parcial como resultado válido. Las operaciones de archivo utilizan temporales exclusivos dentro de directorios transaccionales, completan la transformación antes de publicar y nunca reemplazan un destino existente.

## Secuencia de archivo actualmente implementada

Tanto cifrado como descifrado siguen esta secuencia:

1. Validar el origen y registrar su identidad inicial (dispositivo/inodo cuando el sistema lo proporciona).
2. Crear el directorio transaccional y persistir el estado `prepared`.
3. Crear un temporal exclusivo dentro de la transacción.
4. Escribir el resultado completo; en descifrado, autenticar todos los segmentos y el cierre del flujo antes de publicar.
5. Ejecutar `flush` y `fsync` sobre el resultado y persistir `result_ready`.
6. Publicar con una primitiva atómica no-replace.
7. En GNU/Linux, sincronizar el directorio padre con `fsync` para persistir la entrada de destino.
8. Persistir `published`, revalidar la identidad del origen y retirarlo únicamente si coincide.
9. En GNU/Linux, sincronizar el directorio padre y persistir `source_removed` y `complete`.

El orden es deliberado: no se elimina el origen hasta haber publicado el destino. Si falla una transición del journal, no se debe continuar con una mutación posterior. Los recursos ya publicados permanecen para inspección; no hay rollback destructivo automático.

## Publicación y no sobrescritura

`os.replace()` no se utiliza para publicar recursos del usuario porque puede reemplazar un destino existente. En GNU/Linux se utiliza `renameat2(..., RENAME_NOREPLACE)`; si el kernel/filesystem no ofrece la primitiva, la operación falla de forma segura. En Windows se utiliza `os.rename`, cuya semántica no reemplaza un destino existente. No hay fallback a una secuencia check-then-rename.

El renombrado de directorios también usa publicación no-replace y sincroniza el directorio padre en GNU/Linux. La operación solo cambia el nombre del directorio; no recorre ni modifica sus hijos.

## Durabilidad por plataforma

- **GNU/Linux:** el archivo temporal se sincroniza antes de publicación y el directorio padre se sincroniza después de publicar y después de retirar el origen. Esto mejora la durabilidad de las entradas de directorio, pero las garantías finales dependen del kernel, filesystem, dispositivo y opciones de montaje.
- **Windows:** el archivo temporal se sincroniza y el cambio de nombre usa `os.rename`; la implementación actual no realiza un flush verificable del directorio padre. Por tanto, no promete durabilidad del cambio de nombre ante pérdida abrupta de energía.
- **Otros sistemas:** no están soportados por la implementación actual.

La matriz real NTFS/ext4 y las garantías ante cortes eléctricos todavía requieren validación empírica en los sistemas objetivo.

## Journal persistente y recuperación

El journal persistente v1 está implementado. Cada operación conserva un registro estricto con identidades de filesystem y estados persistidos. `Manager.inspect_recovery(parent)` ofrece inspección explícita, idempotente y de solo lectura.

No existe recuperación automática ni resolución destructiva de transacciones interrumpidas. Los temporales huérfanos no se eliminan automáticamente. Consulta [Journal persistente y protocolo de recuperación](recovery-journal.md) para el esquema, las clasificaciones y las garantías.

## Pruebas de concurrencia y modificación de recursos

La suite `tests/unit/test_filesystem_concurrency.py` añade:

- Ocho operaciones concurrentes de cifrado/descifrado sobre recursos independientes mediante una misma instancia de `Manager`.
- Dos operaciones simultáneas que compiten por cifrar el mismo origen; debe existir exactamente un ganador, un único resultado publicable y un round-trip íntegro.
- Inspección repetida del journal después de la contención para comprobar que sigue siendo de solo lectura.
- Modificación in-place del archivo origen durante cifrado y del ciphertext durante descifrado: la operación compara identidad, tamaño, `mtime` y `ctime` del descriptor antes de publicar y aborta si detecta cambios.
- Sustitución determinista del origen durante la retirada y sustitución del directorio padre durante la operación, cubiertas por pruebas GNU/Linux existentes en `tests/unit/test_filesystem.py`.
- Sustitución determinista de un directorio durante su renombrado, también cubierta en GNU/Linux.

La detección de modificación compara metadatos observables del descriptor; **no es una instantánea criptográfica del origen ni protege frente a un escritor hostil que pueda manipular metadatos, explotar la granularidad temporal del filesystem o modificar bytes y restaurarlos antes de la comprobación**. En Windows, la retirada mueve primero el origen a la entrada `source` del directorio transaccional, verifica su identidad después del movimiento y solicita el borrado mediante `SetFileInformationByHandle` sobre un handle abierto con `DELETE`. Si una entrada sustituta es movida por la carrera previa al renombrado, la identidad posterior no coincide y se intenta restaurar sin sobrescribir una entrada competidora. La eliminación afecta al objeto del handle ya verificado, no a una ruta que pueda resolverse de nuevo. El directorio transaccional conserva la ACL heredada del padre: esto cierra la carrera de sustitución de la ruta que podría provocar el borrado de un objeto distinto, pero no aísla el journal frente a otro proceso con permisos equivalentes para manipular ese directorio. La publicación GNU/Linux usa `renameat2(RENAME_NOREPLACE)` y ahora tiene una prueba determinista que crea un destino competidor justo antes del renombrado; el destino concurrente y el origen deben permanecer intactos. La prueba no sustituye la validación empírica en todos los filesystems.

## Estados tras interrupción

| Punto de interrupción | Estado esperado |
|---|---|
| Antes de publicar | El origen permanece; puede quedar un resultado temporal dentro de la transacción |
| Después de publicar y antes de retirar el origen | Origen y destino completos pueden coexistir |
| Después de retirar el origen | El destino es el único recurso visible; su persistencia depende de las garantías de sincronización de la plataforma |

Si origen y destino coexisten, no se debe eliminar ninguno sin verificar su identidad y contenido. La inspección no muta el filesystem.

## Límites actuales

- [x] Temporales exclusivos dentro de directorios transaccionales.
- [x] Publicación no-replace: `renameat2(RENAME_NOREPLACE)` en GNU/Linux y `os.rename` en Windows.
- [x] El plaintext permanece en temporal privado hasta completar la autenticación de Tink.
- [x] El origen solo se elimina después de publicar el destino.
- [x] Identidad del origen revalidada antes de retirarlo.
- [x] Journal persistente e inspección explícita de solo lectura.
- [x] Pruebas de concurrencia entre operaciones independientes y contención sobre un mismo origen.
- [x] Detección de cambios ordinarios de identidad/tamaño/mtime/ctime del descriptor durante streaming, en cifrado y descifrado.
- [x] Pruebas deterministas GNU/Linux de sustitución del padre, origen y directorio durante la operación.
- [ ] Garantía frente a escritores hostiles capaces de manipular/restaurar metadatos o competir dentro de su granularidad.
- [x] Retirada Windows mediante cuarentena transaccional, verificación de identidad por handle y disposición de borrado sobre ese mismo handle; sin afirmación de ACL privada ni aislamiento frente a procesos con permisos equivalentes.
- [x] Prueba GNU/Linux de colisión de destino justo en el punto de publicación.
- [x] Terminación abrupta del proceso antes y después de persistir `prepared`, `result_ready`, `published`, `source_retained`, `source_removed` y `complete`, mediante subprocess y `os._exit` en GNU/Linux.
- [ ] Flush verificable de directorio y garantías de durabilidad en Windows.
- [ ] Validación empírica en NTFS y ext4, incluidas colisiones case-insensitive/case-sensitive.
- [ ] Política de preservación de permisos, propietario y timestamps.

No se siguen enlaces simbólicos y solo se aceptan archivos regulares/directorios reales. Los enlaces duros, especiales y recursos de red quedan fuera de la matriz v1.

Las pruebas `test_windows_source_substitution_during_quarantine_is_never_deleted` y `test_windows_replacement_after_handle_open_is_not_deleted` fuerzan, respectivamente, una sustitución antes del movimiento a cuarentena y otra después de abrir/verificar el handle. Comprueban que el objeto sustituto no se elimina y que la disposición de borrado sigue ligada al handle del objeto esperado. Las pruebas de round-trip de Windows ejercitan la eliminación normal por handle. La durabilidad de las entradas de directorio en Windows sigue sin estar garantizada por `fsync` de directorio.


## Terminación abrupta del proceso

La prueba de integración `tests/integration/test_crash_recovery.py` ejecuta la operación en un proceso hijo y fuerza `os._exit` desde la persistencia del journal. Esto evita que se ejecuten bloques `finally`, destructores o limpieza normal. Para cada estado `prepared`, `result_ready`, `published`, `source_retained`, `source_removed` y `complete`, se interrumpe tanto antes como después de escribir el nuevo registro.

La prueba comprueba el estado visible del origen y destino, la clasificación que devuelve `inspect_recovery()`, la repetibilidad de la inspección y que el journal y el directorio transaccional no sean modificados por ella. En particular, contempla la diferencia entre el estado físico y el último estado durable del journal: por ejemplo, el destino puede estar publicado mientras el registro aún dice `result_ready`, o el origen puede haberse retirado mientras el registro todavía dice `source_retained`.

Esta prueba verifica terminación abrupta del proceso en GNU/Linux. No simula pérdida de energía, fallo del kernel, caché del dispositivo ni garantiza durabilidad física del hardware. Windows aún requiere una matriz equivalente de interrupciones y validación específica de su semántica de persistencia.
