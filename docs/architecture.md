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
- Filesystem operations: rutas, temporales, publicación y rollback.
- Cryptographic backend: integración interna de Tink, Argon2id y AES-GCM de envoltura.

Esta división define responsabilidades, no obliga a crear un archivo por componente.

## Dependencias

La biblioteca estándar proporciona I/O, rutas y operaciones de sistema. Google Tink proporciona las primitivas AEAD y Streaming AEAD. Argon2id se integra mediante argon2-cffi y AES-GCM de envoltura mediante cryptography.

La primera versión utiliza un único backend criptográfico; no se diseña una arquitectura de backends intercambiables.

## Estado de componentes

- **Implementado:** validación y codec de nombres Tink; generación/apertura de MasterKey; recuperación de keysets; API `generate()`/`Manager`; cambio y exportación de clave; formato binario de archivo v1.0; cifrado/descifrado de archivos con Tink Streaming AEAD; cifrado/descifrado de nombres de archivos y directorios; temporales privados y publicación no-replace en Windows/Linux.
- **Pendiente de validación de plataforma:** comportamiento real en NTFS y ext4, límites Unicode exactos en Windows, colisiones bajo configuraciones case-sensitive y garantías de durabilidad.
- **Pendiente de robustecimiento:** sincronización del directorio padre, journal de recuperación abrupta, pruebas de concurrencia/cambios hostiles y preservación de metadatos de filesystem.

## Flujo de cifrado implementado

Validar origen y destino; preparar claves; crear temporal exclusivo en el mismo filesystem; escribir la cabecera de formato y cifrar secuencialmente hacia el temporal; finalizar el flujo autenticado; preparar y validar el nombre de destino; publicar sin reemplazar destinos existentes; retirar el original solo después de confirmar la publicación; limpiar recursos temporales.

## Flujo de descifrado implementado

Reconocer y validar la cabecera; preparar temporal privado; descifrar y autenticar todos los segmentos; validar el cierre; preparar y validar el nombre original; publicar únicamente tras autenticación completa; limpiar temporales y secretos de mejor esfuerzo.

## Restricciones

No implementar primitivas propias. No publicar plaintext parcial. No sobrescribir destinos por defecto. No asumir que múltiples renames forman una transacción. No prometer borrado seguro absoluto de secretos en memoria Python.
