# Arquitectura

## Principios

La API pública, las operaciones de filesystem, el formato y el backend criptográfico mantienen responsabilidades separadas. La arquitectura interna no debe filtrar objetos específicos del backend a la API pública.

## Componentes lógicos

- Manager: inicialización, ciclo de vida, almacenamiento binario de la clave y contexto reutilizable de operaciones.
- File operations: cifrado y descifrado del contenido.
- Directory operations: transformación del nombre de directorio.
- Name codec: codificación y validación de nombres cifrados.
- Key management: generación, derivación, parsing y separación de claves.
- Format: cabeceras, metadatos y versionado.
- Filesystem operations: rutas, temporales, publicación no-replace, sincronización y manejo de fallos.
- Cryptographic backend: integración interna de Tink, Argon2id y AES-GCM de envoltura.
- Transaction journal: registro persistente de operaciones y diagnóstico explícito de solo lectura, con validación de esquema e identidades de recursos.

Esta división define responsabilidades, no obliga a crear un archivo por componente.

## Dependencias

La biblioteca estándar proporciona I/O, rutas y operaciones de sistema. Google Tink proporciona las primitivas AEAD y Streaming AEAD. Argon2id se integra mediante argon2-cffi y AES-GCM de envoltura mediante cryptography.

La primera versión utiliza un único backend criptográfico; no se diseña una arquitectura de backends intercambiables.

## Estado de componentes

- **Implementado:** validación y codec de nombres Tink; generación/apertura de MasterKey; recuperación de keysets; API `generate()`/`Manager`; cambio y exportación de clave; formato binario de archivo v1.0; cifrado/descifrado de archivos con Tink Streaming AEAD; cifrado/descifrado de nombres de archivos y directorios; temporales privados; publicación no-replace; sincronización del archivo temporal y del directorio padre en GNU/Linux.
- **Implementado:** journal persistente por transacción, formato estricto, estados persistentes, validación de identidades e inspección explícita de solo lectura.
- **Pendiente:** resolución o limpieza explícita de transacciones, política de retención, robustecimiento frente a fallos inyectados y validación integral de filesystem.
- **Pendiente de validación de plataforma:** comportamiento real en NTFS y ext4, límites Unicode exactos en Windows, colisiones bajo configuraciones case-sensitive y garantías de durabilidad.
- **Pendiente de robustecimiento:** resolución explícita de transacciones, flush de directorio en Windows, pruebas de concurrencia/cambios hostiles y preservación de metadatos de filesystem.

## Flujo de cifrado implementado

Validar origen y destino; crear temporal exclusivo en el mismo directorio; escribir la cabecera y cifrar secuencialmente; finalizar el flujo autenticado; sincronizar el archivo temporal; publicar sin reemplazar destinos existentes; sincronizar el directorio padre en GNU/Linux; revalidar y retirar el origen; volver a sincronizar el directorio padre en GNU/Linux. Si falla la primera sincronización del directorio, se conservan origen y destino.

## Flujo de descifrado implementado

Reconocer y validar la cabecera; preparar temporal privado; descifrar y autenticar todos los segmentos; validar el cierre; sincronizar el archivo temporal; validar el nombre original; publicar únicamente tras autenticación completa; sincronizar el directorio padre en GNU/Linux; retirar el ciphertext y sincronizar nuevamente el directorio padre.

## Recuperación y límites

El journal persistente registra las etapas de las operaciones y `Manager.inspect_recovery()` permite inspeccionar su estado sin modificar recursos. No existe recuperación automática ni resolución destructiva de operaciones interrumpidas abruptamente. Los temporales huérfanos no se eliminan automáticamente. Si la publicación se completó pero el origen no pudo retirarse, ambos recursos se conservan y se informa `AtomicOperationError`.

El contrato del journal está en `docs/recovery-journal.md`. La inspección implementada es explícita y de solo lectura; no muta el filesystem. No implementar primitivas propias. No publicar plaintext parcial. No sobrescribir destinos por defecto. No asumir que múltiples renames forman una transacción. No prometer borrado seguro absoluto de secretos en memoria Python.
