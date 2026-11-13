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
- Transaction journal (diseño): registro persistente de operaciones interrumpidas e inspección explícita de sus identidades.

Esta división define responsabilidades, no obliga a crear un archivo por componente.

## Dependencias

La biblioteca estándar proporciona I/O, rutas y operaciones de sistema. Google Tink proporciona las primitivas AEAD y Streaming AEAD. Argon2id se integra mediante argon2-cffi y AES-GCM de envoltura mediante cryptography.

La primera versión utiliza un único backend criptográfico; no se diseña una arquitectura de backends intercambiables.

## Estado de componentes

- **Implementado:** validación y codec de nombres Tink; generación/apertura de MasterKey; recuperación de keysets; API `generate()`/`Manager`; cambio y exportación de clave; formato binario de archivo v1.0; cifrado/descifrado de archivos con Tink Streaming AEAD; cifrado/descifrado de nombres de archivos y directorios; temporales privados; publicación no-replace; sincronización del archivo temporal y del directorio padre en GNU/Linux.
- **Diseño especificado, implementación pendiente:** protocolo de journal por transacción, formato estricto, estados persistentes, validación de identidades y recuperación inicial de solo lectura.
- **Pendiente de validación de plataforma:** comportamiento real en NTFS y ext4, límites Unicode exactos en Windows, colisiones bajo configuraciones case-sensitive y garantías de durabilidad.
- **Pendiente de robustecimiento:** integración del journal en operaciones, API tipada de inspección, resolución explícita de transacciones, flush de directorio en Windows, pruebas de concurrencia/cambios hostiles y preservación de metadatos de filesystem.

## Flujo de cifrado implementado

Validar origen y destino; crear temporal exclusivo en el mismo directorio; escribir la cabecera y cifrar secuencialmente; finalizar el flujo autenticado; sincronizar el archivo temporal; publicar sin reemplazar destinos existentes; sincronizar el directorio padre en GNU/Linux; revalidar y retirar el origen; volver a sincronizar el directorio padre en GNU/Linux. Si falla la primera sincronización del directorio, se conservan origen y destino.

## Flujo de descifrado implementado

Reconocer y validar la cabecera; preparar temporal privado; descifrar y autenticar todos los segmentos; validar el cierre; sincronizar el archivo temporal; validar el nombre original; publicar únicamente tras autenticación completa; sincronizar el directorio padre en GNU/Linux; retirar el ciphertext y sincronizar nuevamente el directorio padre.

## Recuperación y límites

No existe todavía journal persistente ni recuperación automática de operaciones interrumpidas abruptamente. Los temporales huérfanos no se eliminan automáticamente. Si la publicación se completó pero el origen no pudo retirarse, ambos recursos se conservan y se informa `AtomicOperationError`.

El protocolo propuesto está en `docs/recovery-journal.md`. La primera implementación será de inspección explícita y no mutará el filesystem. No implementar primitivas propias. No publicar plaintext parcial. No sobrescribir destinos por defecto. No asumir que múltiples renames forman una transacción. No prometer borrado seguro absoluto de secretos en memoria Python.
