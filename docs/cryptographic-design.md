# Diseño criptográfico

## Objetivos

Confidencialidad e integridad autenticada del contenido y nombres. No se implementarán primitivas ni protocolos criptográficos propios.

## Contenido

Decisión de diseño: AES-256-GCM mediante Streaming AEAD para archivos grandes. El procesamiento será secuencial y segmentado para mantener memoria acotada. El esquema debe detectar alteración, reordenamiento, truncamiento y flujos incompletos conforme a las garantías del backend.

Tamaño de segmento objetivo predeterminado: **1 MiB**. Solo se expondrán tamaños configurables que el backend admita realmente. El tamaño interno puede incluir overhead y no equivaler exactamente a 1 MiB de plaintext.

## Backend

Google Tink es el candidato prioritario. La plantilla Python `AES256_GCM_HKDF_1MB` existe, pero su generación de keysets en Python no está cerrada documentalmente: el módulo de plantillas advierte que esas plantillas no pueden utilizarse actualmente para generar keysets, mientras que la guía general muestra ejemplos de generación para Streaming AEAD con otro perfil. Por tanto, Tink Python no se considera todavía validado para el perfil GCM-HKDF elegido.

La decisión queda condicionada a una prueba ejecutable con una versión concreta que cubra generación, serialización, carga, cifrado y descifrado de streams, integridad y plataformas objetivo. No se cambiará silenciosamente a AES-CTR-HMAC.

La validación de APIs, keysets, Argon2id y AEAD de envoltura se mantiene en [Validación del backend criptográfico](backend-validation.md).

## Nombres

Se prefiere AES-256-GCM con nonce único y autenticación, usando un keyset independiente del destinado al contenido. AES-SIV se considera alternativa, pero su determinismo revela igualdad de nombres repetidos bajo una misma clave.

## Separación de claves

El contenedor MasterKey contiene keysets independientes para contenido y nombres. Los keysets se generan independientemente mediante el backend; no se reutiliza directamente una misma clave AEAD para distintos propósitos ni se diseña una KDF propia para separarlos.

## Nonces y AAD

La generación y unicidad de nonces debe delegarse al backend. Todo metadato que influya en interpretación o descifrado debe autenticarse como AAD o quedar dentro del formato autenticado.

## KDF y protección del contenedor

Argon2id es la KDF seleccionada para proteger el contenedor de claves cuando el consumidor proporciona una contraseña. La derivación utiliza un salt aleatorio y parámetros almacenados en el propio contenedor. Argon2id produce una clave de envoltura de 256 bits; esta clave protege mediante AEAD los keysets serializados.

La API low-level de `argon2-cffi` ofrece derivación binaria de longitud fija mediante Argon2id. `cryptography` ofrece AES-GCM para el payload acotado del contenedor. Ambos son candidatos de integración; versiones mínimas, parámetros y compatibilidad deben fijarse antes de implementar.

La contraseña es necesaria al inicializar Crypto con un contenedor protegido. La contraseña no se almacena. Crypto.generate(password=...) es alias de Crypto.derive(text=...). Crypto.generate() sin contraseña genera un contenedor aleatorio no protegido por contraseña.

Los campos que describen el contenedor y sus parámetros deben autenticarse. No se implementarán primitivas propias.

La criptografía asimétrica para envolver claves queda fuera de la primera versión.
