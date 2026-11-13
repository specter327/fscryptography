# Diseño criptográfico

## Objetivos
Confidencialidad e integridad autenticada del contenido y nombres. No se implementarán primitivas ni protocolos criptográficos propios.

## Contenido
Decisión de diseño: AES-256-GCM mediante Streaming AEAD para archivos grandes. El procesamiento será secuencial y segmentado para mantener memoria acotada. El esquema debe detectar alteración, reordenamiento, truncamiento y flujos incompletos conforme a las garantías del backend.

Tamaño de segmento objetivo predeterminado: **1 MiB**. Solo se expondrán tamaños configurables que el backend admita realmente. El tamaño interno puede incluir overhead y no equivaler exactamente a 1 MiB de plaintext.

## Backend
Google Tink es el candidato principal. La plantilla AES256_GCM_HKDF_1MB es relevante para el perfil inicial.

Antes de adoptarlo se debe validar:
- API Python de cifrado/descifrado de archivos.
- Creación, serialización y carga de keysets.
- Perfiles y tamaños de segmento admitidos.
- Detección de truncamiento y corrupción.
- Compatibilidad de versiones, plataformas y distribución PyPI.

Referencias: [Tink](https://github.com/tink-crypto/tink), [Streaming AEAD](https://developers.google.com/tink/streaming-aead), [tipos de clave soportados](https://developers.google.com/tink/supported-key-types).

## Nombres
Se prefiere AES-256-GCM con nonce único y autenticación, usando clave distinta de la destinada al contenido. AES-SIV se considera alternativa, pero su determinismo revela igualdad de nombres repetidos bajo una misma clave.

## Separación de claves
No reutilizar directamente una misma clave AEAD para contenido y nombres. Utilizar keysets independientes o derivación con separación de dominios respaldada por una construcción reconocida. No diseñar una KDF propia.

## Nonces y AAD
La generación y unicidad de nonces debe delegarse al backend. Todo metadato que influya en interpretación o descifrado debe autenticarse como AAD o quedar dentro del formato autenticado.

## KDF
Argon2id es la KDF seleccionada conceptualmente para contraseñas. Debe conservarse salt, versión y parámetros para reproducir la derivación. Los parámetros de coste predeterminados requieren validación en plataformas objetivo.

La criptografía asimétrica para envolver claves queda fuera de la primera versión.
