# Operaciones atómicas y recuperación

## Objetivo

Un fallo no debe destruir el original ni publicar contenido parcial como resultado válido. Las operaciones de archivo utilizan un temporal exclusivo en el mismo directorio, completan la transformación antes de publicar y nunca reemplazan un destino existente.

## Secuencia de archivo

Tanto cifrado como descifrado siguen esta secuencia:

1. Validar el origen y registrar su identidad inicial (dispositivo/inodo cuando el sistema lo proporciona).
2. Crear un temporal exclusivo en el directorio de destino.
3. Escribir el resultado completo; en descifrado, autenticar todos los segmentos y el cierre del flujo antes de publicar.
4. Ejecutar `flush` y `fsync` sobre el archivo temporal y cerrarlo.
5. Publicar con una primitiva atómica no-replace.
6. En GNU/Linux, sincronizar el directorio padre con `fsync` para persistir la entrada de destino.
7. Comprobar nuevamente la identidad del origen y retirarlo.
8. En GNU/Linux, volver a sincronizar el directorio padre para persistir la retirada.

El orden de los pasos 5–7 es deliberado: no se elimina el origen hasta haber publicado y sincronizado el destino. Si falla la primera sincronización, ambos recursos permanecen. Si falla la segunda sincronización, el destino ya fue publicado y el origen retirado; se informa el estado de incertidumbre de durabilidad mediante `AtomicOperationError`, sin intentar una restauración potencialmente destructiva.

## Publicación y no sobrescritura

`os.replace()` no se utiliza porque puede reemplazar un destino existente. En GNU/Linux se utiliza `renameat2(..., RENAME_NOREPLACE)`; si el kernel/filesystem no ofrece la primitiva, la operación falla de forma segura. En Windows se utiliza `os.rename`, cuya semántica no reemplaza un destino existente. No hay fallback a una secuencia check-then-rename.

El renombrado de directorios también usa publicación no-replace y sincroniza el directorio padre en GNU/Linux. La operación solo cambia el nombre del directorio; no recorre ni modifica sus hijos.

## Durabilidad por plataforma

- **GNU/Linux:** el archivo temporal se sincroniza antes de publicación y el directorio padre se sincroniza después de publicar y después de retirar el origen. Esto mejora la durabilidad de las entradas de directorio, pero las garantías finales dependen del kernel, filesystem, dispositivo y opciones de montaje.
- **Windows:** el archivo temporal se sincroniza y el cambio de nombre usa `os.rename`; la implementación actual no realiza un flush verificable del directorio padre. Por tanto, no promete durabilidad del cambio de nombre ante pérdida abrupta de energía.
- **Otros sistemas:** no están soportados por la implementación actual.

La matriz real NTFS/ext4 y las garantías ante cortes eléctricos todavía requieren validación empírica en los sistemas objetivo.

## Recuperación y estados tras interrupción

No existe todavía un journal persistente ni una API de recuperación automática. No se deben borrar temporales huérfanos automáticamente: sin un registro transaccional no es posible demostrar que un temporal no pertenece a una operación activa o que su eliminación sea segura.

Los estados posibles tras una interrupción son:

| Punto de interrupción | Estado esperado |
|---|---|
| Antes de publicar | El origen permanece; puede quedar un temporal incompleto |
| Después de publicar y antes de retirar el origen | Origen y destino completos pueden coexistir |
| Después de retirar el origen | El destino es el único recurso visible; su persistencia depende de las garantías de sincronización de la plataforma |

Si origen y destino coexisten, no se debe eliminar ninguno sin verificar su contenido y decidir cuál conservar. El temporal `.fscryptography-*` no es un resultado válido hasta completar publicación; su limpieza debe hacerse únicamente después de verificar que ninguna operación está activa.

## Límites actuales

- [x] Temporales exclusivos en el mismo directorio.
- [x] Publicación no-replace: `renameat2(RENAME_NOREPLACE)` en GNU/Linux y `os.rename` en Windows.
- [x] El plaintext permanece en temporal privado hasta completar la autenticación de Tink.
- [x] El origen solo se elimina después de publicar el destino.
- [x] Identidad del origen revalidada antes de retirarlo.
- [x] `fsync` del archivo temporal antes de publicar.
- [x] `fsync` del directorio padre en GNU/Linux después de publicar y retirar.
- [x] Si falla la sincronización posterior a la publicación, el origen se conserva.
- [ ] Journal persistente y recuperación transaccional tras interrupción abrupta.
- [ ] Flush verificable de directorio y garantías de durabilidad en Windows.
- [ ] Validación empírica en NTFS y ext4, incluidas colisiones case-insensitive/case-sensitive.
- [ ] Pruebas de concurrencia y cambios hostiles de rutas durante la operación.
- [ ] Política de preservación de permisos, propietario y timestamps.

No se siguen enlaces simbólicos y solo se aceptan archivos regulares/directorios reales. Los enlaces duros, especiales y recursos de red quedan fuera de la matriz v1.
