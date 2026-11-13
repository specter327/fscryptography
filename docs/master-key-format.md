# Formato de MasterKey

## Objetivo y contrato

`MasterKey` es un contenedor autocontenido, versionado y opaco para el consumidor. Transporta los keysets secretos que necesita `fscryptography` para cifrar y descifrar recursos. No es una clave AES individual, ni el formato de un archivo cifrado.

La representación pública es una cadena Base64 estándar con padding. Su decodificación produce un contenedor binario. Base64 solo proporciona codificación; no aporta confidencialidad, integridad ni protección frente a exposición.

El consumidor puede almacenar o transportar la cadena, pero debe tratarla como material secreto. No debe registrar su contenido en logs, mensajes de error, telemetría ni salidas de diagnóstico.

## Modos del contenedor

Se definen dos modos mutuamente excluyentes:

1. **Aleatorio sin contraseña.** Contiene los keysets serializados sin cifrado de envoltura. `Crypto(master_key=...)` puede abrirlo sin contraseña. La seguridad depende de la confidencialidad e integridad del valor completo.
2. **Protegido mediante contraseña.** Contiene un payload cifrado y autenticado que incluye los keysets serializados. `Crypto(master_key=..., password=...)` requiere la contraseña para abrirlo.

No se permite inferir el modo mediante heurísticas ni intentar ambos modos silenciosamente. El modo debe estar identificado explícitamente en el contenedor.

## Estructura lógica

El contenedor binario tendrá una cabecera versionada y un payload delimitado por longitud. La cabecera incluirá, como mínimo:

- Magic o identificador inequívoco de formato.
- Versión principal y secundaria del contenedor.
- Indicadores de modo y flags reservados.
- Identificador del esquema de payload.
- Longitud del payload.

Los campos variables y los parámetros criptográficos se codificarán de forma inequívoca y validable. La disposición binaria exacta —anchos, orden, endianness, límites y codificación de campos— se fijará en la especificación de implementación, después de validar las capacidades de serialización del backend. No se utilizará `pickle` ni otro mecanismo de deserialización ejecutable.

El parser debe validar límites y longitudes antes de asignar memoria o procesar campos. Debe rechazar truncamiento, datos sobrantes no permitidos, flags desconocidos, versiones principales no soportadas, identificadores desconocidos y estructuras malformadas.

## Payload y separación de dominios

El payload lógico contiene, como mínimo, dos keysets independientes:

- Keyset para cifrado autenticado del contenido de archivos.
- Keyset para cifrado autenticado de nombres de archivos y directorios.

Los keysets se generan independientemente mediante el backend criptográfico. No se derivan ambos dominios reutilizando directamente una misma clave AEAD.

La serialización debe utilizar el mecanismo soportado por el backend seleccionado. Tink Python documenta serialización binaria Protobuf de keysets, pero requiere un token explícito para acceder al material secreto. Ese mecanismo debe permanecer confinado al módulo interno de gestión de claves. No se inventará un formato de keyset propio ni se expondrá su estructura mediante la API pública.

La generación y recuperación del keyset Streaming AEAD con la plantilla `AES256_GCM_HKDF_1MB` quedó validada en Tink Python 1.16.1 mediante CI para Python 3.10–3.13. La prueba de Argon2id y AES-GCM para protección del contenedor ya está incorporada al workflow, pero su ejecución CI y la fijación de parámetros de producción siguen pendientes. Véase [Validación del backend criptográfico](backend-validation.md).

## Modo aleatorio

En el modo aleatorio, el payload contiene los keysets serializados sin cifrado de envoltura. No existe una contraseña ni una clave adicional de protección.

Por diseño, este modo no ofrece autenticación criptográfica del contenedor frente a modificaciones deliberadas. La implementación debe validar rigurosamente su estructura y el material serializado, pero no debe afirmar que detecta toda manipulación maliciosa del contenedor. Quien pueda modificar el valor puede sustituir o corromper el material de claves.

## Modo protegido mediante contraseña

El modo protegido utiliza Argon2id para derivar una clave de envoltura a partir de la contraseña y un salt aleatorio. Esa clave protege el payload mediante un esquema AEAD seleccionado y validado antes de implementar.

La integración seleccionada para el prototipo es Argon2id de `argon2-cffi` y AES-256-GCM de `cryptography` para el payload acotado del contenedor. Se añadió una prueba ejecutable para validar derivación, round-trip y rechazos de autenticación; queda pendiente que CI la ejecute satisfactoriamente. Las versiones mínimas y los parámetros de coste normativos siguen pendientes de validación de plataformas y benchmark.

El contenedor incluye:

- Identificador y versión de Argon2id.
- Salt.
- Parámetros de coste (memoria, iteraciones y paralelismo).
- Identificador del algoritmo AEAD de envoltura.
- Nonce.
- Ciphertext y tag de autenticación.

La cabecera y los parámetros que condicionan la interpretación del contenedor se autentican como AAD. Los parámetros de KDF deben someterse a límites de aceptación antes de ejecutar Argon2id para evitar consumos de recursos desproporcionados por entradas manipuladas.

La contraseña no se almacena. Al abrir el contenedor, una contraseña incorrecta y una alteración del ciphertext deben fallar sin entregar keysets parciales ni generar claves de reemplazo.

## Compatibilidad y evolución

- Las versiones principales incompatibles se rechazan.
- Las versiones secundarias solo pueden ignorarse si el contrato de esa versión garantiza que los campos añadidos son opcionales y seguros de ignorar.
- Los identificadores de KDF, AEAD y esquema de payload son explícitos; no se seleccionan algoritmos mediante heurísticas.
- La librería no debe degradar automáticamente a un algoritmo más débil si encuentra un identificador desconocido.
- La política de lectura de versiones antiguas se definirá explícitamente; no se promete migración automática en v1.

## Límites de seguridad

- Base64 no es cifrado.
- Un contenedor aleatorio sin contraseña debe protegerse como una credencial secreta.
- La protección mediante contraseña depende de la fortaleza de la contraseña, los parámetros Argon2id y la seguridad del AEAD de envoltura.
- La contraseña no se conserva en memoria como atributo persistente de `Crypto`; la limpieza de secretos en Python es de mejor esfuerzo.
- El contenedor no proporciona intercambio de claves, recuperación, rotación ni revocación.

## Pendiente de validación

Antes de implementar deben cerrarse:

- Compatibilidad del backend en las plataformas objetivo, más allá de la matriz Ubuntu/Python ya validada.
- Compatibilidad del backend y sus dependencias en las plataformas objetivo.
- Resultado CI de la prueba Argon2id/AES-GCM, parámetros y límites de Argon2id.
- Versiones mínimas normativas de `argon2-cffi` y `cryptography` y compatibilidad en plataformas objetivo.
- Disposición binaria exacta, tamaños máximos y límites de parsing.
- Normalización Unicode y límites de contraseña.
- Política concreta de compatibilidad y migración.
