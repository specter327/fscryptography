# Diseño criptográfico

## Objetivos

Confidencialidad e integridad autenticada del contenido y nombres. No se implementarán primitivas ni protocolos criptográficos propios.

## Contenido

Decisión de diseño: AES-256-GCM mediante Streaming AEAD para archivos grandes. El procesamiento será secuencial y segmentado para mantener memoria acotada. El esquema debe detectar alteración, reordenamiento, truncamiento y flujos incompletos conforme a las garantías del backend.

Tamaño de segmento objetivo predeterminado: **1 MiB**. Solo se expondrán tamaños configurables que el backend admita realmente. El tamaño interno puede incluir overhead y no equivaler exactamente a 1 MiB de plaintext.

## Backend

Google Tink es el backend seleccionado para el prototipo. La plantilla Python `AES256_GCM_HKDF_1MB` superó una prueba ejecutable con Tink 1.16.1 y Python 3.10–3.13 en Ubuntu: generación de keyset, serialización/recuperación, round-trip y rechazo de AAD incorrecto, truncamiento y alteración. La compatibilidad con otros sistemas operativos/plataformas y la integración sobre archivos reales siguen pendientes. No se cambiará silenciosamente a AES-CTR-HMAC.

La validación de APIs, keysets, Argon2id y AEAD de envoltura se mantiene en [Validación del backend criptográfico](backend-validation.md).

## Nombres

Se prefiere AES-256-GCM con nonce único y autenticación, usando un keyset independiente del destinado al contenido. AES-SIV se considera alternativa, pero su determinismo revela igualdad de nombres repetidos bajo una misma clave.

## Separación de claves

El contenedor MasterKey contiene keysets independientes para contenido y nombres. Los keysets se generan independientemente mediante el backend; no se reutiliza directamente una misma clave AEAD para distintos propósitos ni se diseña una KDF propia para separarlos.

## Nonces y AAD

La generación y unicidad de nonces debe delegarse al backend. Todo metadato que influya en interpretación o descifrado debe autenticarse como AAD o quedar dentro del formato autenticado.

## KDF y protección del contenedor

Argon2id es la KDF seleccionada para proteger el contenedor de claves cuando el consumidor proporciona una contraseña. La derivación utiliza un salt aleatorio y parámetros almacenados en el propio contenedor. Argon2id produce una clave de envoltura de 256 bits; esta clave protege mediante AEAD los keysets serializados.

La API low-level de `argon2-cffi` ofrece derivación binaria de longitud fija mediante Argon2id. `cryptography` ofrece AES-GCM para el payload acotado del contenedor. Esta composición está seleccionada para el prototipo y cuenta con una prueba de integración automatizada incorporada a CI. La prueba CI pasó en Python 3.10–3.13 con `argon2-cffi 25.1.0` y `cryptography 46.0.7`. Antes de implementar la protección del contenedor deben cerrarse los parámetros normativos de Argon2id, las versiones mínimas y la compatibilidad en plataformas objetivo.

La contraseña es necesaria al inicializar Crypto con un contenedor protegido. La contraseña no se almacena. Crypto.generate(password=...) es alias de Crypto.derive(text=...). Crypto.generate() sin contraseña genera un contenedor aleatorio no protegido por contraseña.

Perfil Argon2id aprobado para MasterKey v1: versión 19, memoria 65.536 KiB, 3 iteraciones, paralelismo 1, salt de 16 bytes y salida de 32 bytes. El parser debe aceptar exactamente este perfil y rechazar cualquier otra combinación antes de ejecutar la KDF. Los límites de entrada y contraseña se detallan en [la política Argon2id](argon2id-policy.md) y siguen pendientes de confirmación contractual.

Los campos que describen el contenedor y sus parámetros deben autenticarse. No se implementarán primitivas propias.

La criptografía asimétrica para envolver claves queda fuera de la primera versión.
