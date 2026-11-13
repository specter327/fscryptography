# Arquitectura

## Principios
La API pública, las operaciones de filesystem, el formato y el backend criptográfico deben mantener responsabilidades separadas. La arquitectura interna no debe filtrar objetos específicos del backend a la API pública.

## Componentes lógicos
- Crypto: inicialización, ciclo de vida y fachada de operaciones.
- File operations: cifrado y descifrado del contenido.
- Directory operations: transformación del nombre de directorio.
- Name codec: codificación y validación de nombres cifrados.
- Key management: generación, derivación, parsing y separación de claves.
- Format: encabezados, metadatos y versionado.
- Filesystem operations: rutas, temporales, publicación y rollback.
- Cryptographic backend: integración interna del backend elegido.

Esta división define responsabilidades, no obliga a crear un archivo por componente.

## Dependencias
La biblioteca estándar proporciona I/O, rutas y operaciones de sistema. Una biblioteca criptográfica mantenida proporciona las primitivas. Argon2id se integra mediante implementación mantenida si el backend AEAD no proporciona esa KDF.

Google Tink es el candidato prioritario para Streaming AEAD, pendiente de validar API Python, perfiles, serialización y empaquetado. La primera versión tendrá un backend, no una arquitectura de backends intercambiables.

## Flujo de cifrado
Validar origen y destino; preparar claves; crear temporal exclusivo en el mismo filesystem; leer y cifrar secuencialmente; finalizar el formato autenticado; preparar el nombre de destino; publicar; retirar el origen solo después de confirmar la publicación; limpiar recursos temporales.

## Flujo de descifrado
Reconocer y validar el formato; preparar temporal privado; descifrar y autenticar todos los segmentos; validar el cierre; preparar el nombre original; publicar únicamente tras autenticación completa; limpiar temporales y secretos de mejor esfuerzo.

## Restricciones
No implementar primitivas propias. No publicar plaintext parcial. No sobrescribir destinos por defecto. No asumir que múltiples renames forman una transacción. No prometer borrado seguro absoluto de secretos en memoria Python.
