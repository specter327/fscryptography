# Operaciones atómicas y recuperación

## Objetivo

Un fallo no debe destruir el original ni publicar contenido parcial como resultado válido. Se utilizarán temporales y una fase de publicación.

## Cifrado de archivo

1. Validar origen y destino.
2. Crear temporal exclusivo en el mismo directorio/filesystem.
3. Escribir la cabecera del formato y procesar el contenido secuencialmente hacia el temporal.
4. Finalizar el cifrador y completar el flujo autenticado.
5. Cerrar y sincronizar cuando se requiera durabilidad.
6. Preparar y validar el nombre destino.
7. Publicar el resultado mediante una operación que falle si el destino ya existe.
8. Retirar el original solo después de confirmar la publicación.
9. Sincronizar directorio cuando aplique.

## Descifrado

El plaintext se escribe en temporal privado. No se publica en la ruta definitiva hasta autenticar todos los segmentos y el cierre del flujo, validar los metadatos y validar el nombre de destino. Ante fallo de autenticación, eliminar temporal y preservar ciphertext original.

## Niveles de garantía

- **Atomicidad de publicación individual:** el destino no aparece parcialmente escrito.
- **No sobrescritura:** la publicación debe fallar de forma atómica si el destino ya existe, incluyendo colisiones según la semántica real del filesystem.
- **Rollback ante errores controlables:** restaurar estado inicial mientras el proceso puede ejecutar recuperación.
- **Recuperación tras interrupción abrupta:** requiere journal/protocolo persistente; no la proporciona un simple temporal.
- **Durabilidad:** puede requerir flush, fsync del archivo y sincronización de directorio; depende de SO y filesystem.

os.replace() no se utiliza para publicar porque puede reemplazar un destino existente. En GNU/Linux se utiliza `renameat2(..., RENAME_NOREPLACE)`; si el kernel/filesystem no ofrece la primitiva, la operación falla de forma segura. En Windows se utiliza `os.rename`, cuya semántica no reemplaza un destino existente. No hay fallback a una secuencia check-then-rename. La matriz real NTFS/ext4 todavía requiere validación en los sistemas objetivo.

La atomicidad de una publicación individual no hace indivisible la secuencia completa de publicación del contenido, cambio del nombre y retirada del origen.

## Directorios

Renombrar un directorio dentro del mismo filesystem suele ser atómico como operación de namespace, pero la operación concreta debe preservar la política de no sobrescritura. No se modifica el contenido del directorio.

## Destinos y temporales

No sobrescribir destinos existentes por defecto. Crear temporales exclusivos y con permisos restrictivos, especialmente para plaintext. Limpiar temporales en errores controlables y definir política para huérfanos.

## Estado y límites actuales

- [x] Temporales exclusivos en el mismo directorio.
- [x] Publicación no-replace: `renameat2(RENAME_NOREPLACE)` en GNU/Linux y `os.rename` en Windows.
- [x] El contenido descifrado permanece en temporal privado hasta completar la autenticación de Tink.
- [x] El origen solo se elimina después de publicar el destino.
- [x] Si falla la retirada del origen después de publicar, se conservan ambos recursos y se informa `AtomicOperationError`.
- [ ] Sincronización del directorio padre y garantías de durabilidad ante pérdida abrupta de energía.
- [ ] Journal para recuperación transaccional tras interrupción abrupta.
- [ ] Validación empírica en NTFS y ext4, incluyendo colisiones case-insensitive/case-sensitive.
- [ ] Pruebas de concurrencia y cambios hostiles de rutas durante la operación.
- [ ] Política de preservación de permisos, propietario y timestamps.

No se siguen enlaces simbólicos y solo se aceptan archivos regulares/directorios reales. Los enlaces duros, especiales y recursos de red quedan fuera de la matriz v1.
