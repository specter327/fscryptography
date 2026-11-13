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
Se prefiere AES-256-GCM con nonce único y autenticación, usando un keyset independiente del destinado al contenido. AES-SIV se considera alternativa, pero su determinismo revela igualdad de nombres repetidos bajo una misma clave.

## Separación de claves
El contenedor MasterKey contiene keysets independientes para contenido y nombres. Los keysets se generan independientemente mediante el backend; no se reutiliza directamente una misma clave AEAD para distintos propósitos ni se diseña una KDF propia para separarlos.

## Nonces y AAD
La generación y unicidad de nonces debe delegarse al backend. Todo metadato que influya en interpretación o descifrado debe autenticarse como AAD o quedar dentro del formato autenticado.

## KDF y protección del contenedor
Argon2id es la KDF seleccionada para proteger el contenedor de claves cuando el consumidor proporciona una contraseña. La derivación utiliza un salt aleatorio y parámetros almacenados en el propio contenedor. Argon2id produce una clave de envoltura de 256 bits; esta clave protege mediante AEAD los keysets serializados.

La contraseña es necesaria al inicializar Crypto con un contenedor protegido. La contraseña no se almacena. Crypto.generate(password=...) es alias de Crypto.derive(text=...). Crypto.generate() sin contraseña genera un contenedor aleatorio no protegido por contraseña.

El algoritmo AEAD de envoltura, la API concreta y los parámetros de Argon2id requieren validación de dependencias y plataformas. Los campos que describen el contenedor y sus parámetros deben autenticarse. No se implementarán primitivas criptográficas propias.

La criptografía asimétrica para envolver claves queda fuera de la primera versión.
