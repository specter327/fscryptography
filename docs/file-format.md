# Formato de archivos y metadatos

## Objetivo
El descifrado debe requerir únicamente el archivo cifrado y la clave original. No se utilizarán sidecars, bases de datos ni configuración externa.

El formato debe identificar versión, transportar parámetros necesarios, autenticar metadatos relevantes y permitir detectar corrupción y truncamiento conforme al backend.

## Streaming AEAD
Se prefiere utilizar directamente el formato del backend Streaming AEAD, evitando una envoltura criptográfica propia innecesaria. Primero se debe validar qué encabezado y metadatos proporciona el backend, cómo serializa keysets y cómo garantiza la finalización del flujo.

## Metadatos adicionales
Podrían requerirse versión de fscryptography, tipo lógico de recurso y extensión original cuando se cifra el nombre. Solo incluir campos necesarios. Todo campo que influya en interpretación o descifrado debe autenticarse como AAD o integrarse en el formato autenticado.

## Extensión original
Cuando se cifra el nombre completo, la extensión original debe recuperarse desde metadatos autenticados, no inferirse del nombre cifrado.

## Versionado
El formato debe identificarse inequívocamente. Versiones desconocidas o estructuras malformadas se rechazan sin heurísticas. La compatibilidad de lectura entre versiones se definirá explícitamente.

## Pendiente
Estructura binaria exacta, campos, orden, tamaños, codificación, AAD, marcadores y migración. No implementar un formato provisional como definitivo.
