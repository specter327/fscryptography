# Formato de MasterKey

## Objetivo y contrato

`MasterKey` es un contenedor autocontenido, versionado y opaco para el consumidor. Transporta los keysets secretos que necesita `fscryptography` para cifrar y descifrar recursos. No es una clave AES individual ni el formato de un archivo cifrado.

La representación pública es una cadena Base64 estándar con padding. Su decodificación produce un contenedor binario. Base64 solo proporciona codificación; no aporta confidencialidad, integridad ni protección frente a exposición.

El consumidor puede almacenar o transportar la cadena, pero debe tratar su contenido como material secreto. No debe registrar el valor en logs, mensajes de error, telemetría ni salidas de diagnóstico.

## Modos

Se definen dos modos mutuamente excluyentes:

| Valor | Modo | Protección del payload |
|---:|---|---|
| `0x00` | Aleatorio | Sin cifrado de envoltura; el contenedor completo es secreto |
| `0x01` | Protegido por contraseña | AEAD con clave derivada mediante Argon2id |

El modo se declara explícitamente. No se permite inferirlo mediante heurísticas ni intentar ambos modos silenciosamente.

## Payload lógico

El esquema de payload `0x01` contiene exactamente dos keysets Tink independientes, en este orden:

1. Keyset de Streaming AEAD para contenido de archivos.
2. Keyset AEAD para nombres.

Cada keyset se serializa mediante el formato binario Protobuf soportado por Tink. No se utiliza JSON, `pickle` ni deserialización ejecutable. La serialización y recuperación de keysets debe permanecer confinada al módulo interno de gestión de claves y utilizar el token explícito de acceso a material secreto exigido por Tink.

El payload aplica framing propio únicamente para delimitar los dos mensajes Protobuf:

| Campo | Tamaño | Codificación |
|---|---:|---|
| Longitud del keyset de contenido | 4 bytes | Entero sin signo, big-endian |
| Keyset de contenido | Longitud indicada | Protobuf binario de Tink |
| Longitud del keyset de nombres | 4 bytes | Entero sin signo, big-endian |
| Keyset de nombres | Longitud indicada | Protobuf binario de Tink |

No se permiten longitudes cero, bytes sobrantes ni campos adicionales en el esquema `0x01`. Los dos keysets deben validarse como tipos de primitivas esperados; no basta con que sean Protobuf sintácticamente válido.

Límites estructurales propuestos para v1:
- Cada keyset serializado: máximo 32 KiB.
- Payload lógico: máximo 64 KiB.
- Longitud del payload exterior: máximo 64 KiB en modo aleatorio y 64 KiB + 16 bytes en modo protegido (tag GCM incluido).
- Los límites se comprueban antes de reservar memoria o invocar el parser Protobuf.

El perfil concreto del keyset AEAD de nombres y su compatibilidad multiplataforma siguen pendientes de validación. La estructura del payload no implica que ese backend ya esté seleccionado.

## Propuesta de formato binario v1

Todos los enteros multibyte usan big-endian. No hay padding implícito entre campos. La cabecera completa se utiliza como AAD en el modo protegido.

### Prefijo común

El prefijo ocupa exactamente 20 bytes:

| Offset | Tamaño | Campo | Valor / semántica |
|---:|---:|---|---|
| 0 | 8 | Magic | Bytes ASCII `FSCRKEY\0` |
| 8 | 1 | Major version | `0x01` |
| 9 | 1 | Minor version | `0x00` |
| 10 | 1 | Mode | `0x00` o `0x01` según la tabla de modos |
| 11 | 1 | Payload schema | `0x01` |
| 12 | 2 | Flags | `0x0000`; cualquier bit distinto de cero se rechaza en v1 |
| 14 | 2 | Header length | Longitud exacta de la cabecera, incluido el prefijo |
| 16 | 4 | Payload length | Longitud exacta de los bytes que siguen a la cabecera |

La longitud total del contenedor binario debe ser exactamente `header_length + payload_length`. No se aceptan bytes finales adicionales.

### Extensión del modo aleatorio

El modo `0x00` no añade campos a la cabecera:
- `header_length = 20`.
- El payload son directamente los bytes del payload lógico.
- No hay KDF, salt, nonce ni cifrado de envoltura.
- La cabecera no está autenticada criptográficamente. El parser valida estructura, pero no debe afirmar que detecta toda manipulación maliciosa del contenedor.

### Extensión del modo protegido

El modo `0x01` añade exactamente 41 bytes al prefijo; por tanto, `header_length = 61`.

| Offset | Tamaño | Campo | Valor / semántica |
|---:|---:|---|---|
| 20 | 1 | KDF identifier | `0x01` = Argon2id |
| 21 | 1 | Argon2 version | `0x13` = versión 19 |
| 22 | 4 | Memory cost | KiB, entero sin signo |
| 26 | 4 | Time cost | Iteraciones, entero sin signo |
| 30 | 2 | Parallelism | Grado de paralelismo, entero sin signo |
| 32 | 16 | Salt | Salt aleatorio de Argon2id |
| 48 | 1 | Wrapping AEAD identifier | `0x01` = AES-256-GCM |
| 49 | 12 | Nonce | Nonce GCM de 96 bits |

El payload es el resultado de AES-256-GCM aplicado al payload lógico:
- La clave de envoltura tiene 32 bytes y se deriva de la contraseña con Argon2id.
- La cabecera completa, desde el offset 0 hasta `header_length - 1`, se pasa sin transformación como AAD.
- El nonce se genera de forma segura y no se reutiliza con la misma clave.
- El resultado de AES-GCM incluye el tag de autenticación de 16 bytes.
- `payload_length` incluye ciphertext y tag.

La contraseña no se almacena. La API recibe texto y su codificación binaria propuesta es UTF-8 estricto, sin normalización Unicode implícita. El límite máximo de bytes de contraseña y los límites de aceptación de parámetros Argon2id deben fijarse antes de implementar; el parser debe rechazarlos antes de ejecutar la KDF si exceden la política.

## Reglas de parsing

El parser debe operar en este orden, sin ejecutar KDF ni deserializar keysets antes de validar el framing exterior:

1. Verificar tamaño mínimo, magic y versión soportada.
2. Verificar modo, schema y flags.
3. Verificar que `header_length` coincide exactamente con el modo y versión.
4. Verificar que `payload_length` no supera 64 KiB en modo aleatorio ni 64 KiB + 16 bytes en modo protegido, y que el tamaño total coincide exactamente con la entrada.
5. En modo protegido, validar identificadores, versión Argon2, tamaños fijos y límites de parámetros antes de ejecutar Argon2id.
6. En modo protegido, autenticar y descifrar el payload completo; no entregar bytes parciales.
7. Validar el framing interno, las longitudes y la ausencia de bytes sobrantes.
8. Parsear los dos keysets con Tink y verificar que corresponden a las primitivas esperadas.
9. Entregar ambos keysets solo si todas las validaciones concluyeron correctamente.

Cualquier fallo invalida el contenedor completo. Nunca se devuelve un keyset parcial ni se generan claves de reemplazo silenciosamente.

### Rechazos obligatorios

- Magic incorrecto, entrada truncada o versión no soportada.
- Modo, schema, identificador KDF/AEAD o flags desconocidos.
- Longitudes incoherentes, fuera de límites o que no coincidan con el tamaño real.
- Cabecera de tamaño inesperado, extensiones o bytes finales no definidos.
- Parámetros Argon2id fuera de la política, antes de ejecutar la KDF.
- Contraseña incorrecta, nonce/AAD/ciphertext/tag alterados.
- Payload interno truncado, longitudes cero, longitudes fuera de límites o bytes sobrantes.
- Protobuf malformado, keysets vacíos o keysets de tipo inesperado.

## Autenticación y límites de seguridad

En el modo protegido, todos los campos que controlan la interpretación del contenedor están incluidos en el AAD: magic, versiones, modo, schema, flags, longitudes, parámetros KDF, salt, identificador AEAD y nonce. Una alteración de cualquiera de ellos debe impedir la apertura, ya sea por rechazo estructural o por fallo de autenticación.

En el modo aleatorio no existe autenticación de la cabecera ni del payload frente a modificación deliberada. La integridad de los keysets solo puede comprobarse parcialmente mediante sus validaciones internas; no se debe presentar este modo como autenticado.

Base64 no es cifrado. El modo aleatorio debe protegerse como una credencial secreta. El modo protegido depende de la fortaleza de la contraseña, de la política de coste Argon2id y de AES-256-GCM.

## Compatibilidad y evolución

- La versión inicial propuesta es `1.0`.
- Una versión major desconocida se rechaza.
- Una versión minor desconocida también se rechaza en v1; no se ignoran extensiones no definidas.
- Los identificadores de algoritmos y esquemas son explícitos; nunca se seleccionan algoritmos mediante heurísticas.
- No hay downgrade automático ni fallback criptográfico.
- No se promete migración automática de contenedores antiguos.

## Estado de decisiones

**Propuesto en esta revisión, pendiente de aprobación:**
- Magic, campos, offsets, tamaños y big-endian del contenedor v1.
- Framing del payload con dos longitudes Protobuf.
- Límites estructurales de 32 KiB por keyset y 64 KiB por payload.
- Codificación UTF-8 estricta sin normalización implícita.

**Pendiente antes de implementar:**
- Parámetros de producción Argon2id y límites máximos/mínimos de aceptación, definidos mediante benchmark y análisis de abuso de recursos.
- Límite máximo de contraseña en bytes.
- Perfil AEAD concreto para nombres y pruebas de compatibilidad del backend.
- Vectores binarios golden definitivos y pruebas multiplataforma.
- Política de versiones y migración más allá de v1.

Esta especificación describe un formato propuesto; no implica que exista ya un parser o una implementación funcional.
