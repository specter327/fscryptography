# Política de Argon2id y límites de apertura de MasterKey

## Estado

**Propuesta técnica para MasterKey v1; pendiente de benchmark en hardware modesto y aprobación final.**

Esta política define el perfil inicial de protección por contraseña y los límites que deben comprobarse antes de ejecutar Argon2id. No modifica el layout binario v1.0 aprobado: los parámetros continúan almacenándose en los campos ya definidos de la cabecera protegida.

Los valores de los fixtures de prueba no son parámetros de producción.

## Perfil de producción propuesto

| Parámetro | Valor |
|---|---:|
| Función | Argon2id |
| Versión | 0x13 (19) |
| Memoria | 65.536 KiB (64 MiB) |
| Iteraciones | 3 |
| Paralelismo | 1 |
| Salt | 16 bytes aleatorios |
| Clave derivada | 32 bytes |

El perfil prioriza una huella de memoria moderada y un coste temporal significativo sin multiplicar la memoria mediante paralelismo. No se debe interpretar como un valor universalmente óptimo: su aceptación definitiva depende de medirlo en el hardware más modesto que se pretenda soportar.

La implementación debe usar argon2-cffi y Argon2id. No debe implementar la función ni sustituirla por otra variante.

## Política de aceptación de parámetros

Para la primera implementación productiva de v1 se propone una **lista de aceptación estricta de un único perfil**:

- version == 0x13
- memory_cost == 65536
- time_cost == 3
- parallelism == 1

Cualquier otra combinación se rechaza antes de llamar a Argon2id. Esto incluye valores inferiores, superiores y combinaciones que individualmente parezcan razonables.

La regla evita que un contenedor manipulado solicite una cantidad arbitraria de memoria o CPU y evita aceptar una degradación silenciosa del coste. No se debe limitar, corregir, normalizar ni sustituir parámetros del contenedor.

Los parámetros se autentican como parte de la cabecera AAD, pero **la autenticación no protege contra el coste de una KDF ejecutada antes de verificar el tag**. Por ello, validar el perfil antes de la derivación es obligatorio.

Si en el futuro se necesita admitir otros costes por motivos de compatibilidad o evolución, deberán añadirse perfiles explícitos, versionados documentalmente y sujetos a límites de recursos. No se ampliará la aceptación mediante rangos abiertos.

## Límites de entrada previos a KDF

| Elemento | Límite propuesto | Validación |
|---|---:|---|
| Contenedor binario | 131.149 bytes | Antes de parsear campos variables |
| Texto Base64 | 174.868 caracteres ASCII | Antes de decodificar |
| Contraseña UTF-8 | 1.024 bytes | Antes de ejecutar Argon2id |
| Salt | Exactamente 16 bytes | Parser estructural |
| Nonce AES-GCM | Exactamente 12 bytes | Parser estructural |
| Tag AES-GCM | Exactamente 16 bytes | AEAD / longitud mínima |

El máximo binario deriva del modo protegido: cabecera de 61 bytes + payload lógico máximo de 131.072 bytes + tag GCM de 16 bytes. El máximo Base64 corresponde a la codificación estándar con padding de ese tamaño binario máximo.

La entrada Base64 debe validarse estrictamente. No se deben ignorar caracteres ajenos al alfabeto Base64, espacios, saltos de línea ni padding incorrecto. No se debe decodificar una entrada arbitrariamente grande para comprobar su tamaño después.

La contraseña debe recibirse como texto, codificarse una sola vez con UTF-8 estricto y comprobarse por longitud en bytes. Se rechazan cadenas vacías y entradas que excedan 1.024 bytes. No se aplica normalización Unicode, recorte de espacios ni transformación silenciosa. La contraseña no debe aparecer en excepciones, logs ni diagnósticos.

## Orden obligatorio de validación

Antes de cualquier operación costosa:

1. Comprobar que la entrada Base64 es texto válido, ASCII y no supera 174.868 caracteres.
2. Decodificar con validación estricta y comprobar el tamaño binario máximo.
3. Validar magic, versión, modo, schema, flags y longitudes.
4. Verificar que el tamaño total coincide exactamente con cabecera + payload.
5. En modo protegido, validar los identificadores KDF/AEAD, la versión Argon2id, los tamaños fijos y la combinación exacta de parámetros admitida.
6. Validar la contraseña como UTF-8 estricto y comprobar su longitud máxima.
7. Solo entonces ejecutar Argon2id y abrir el payload con AES-256-GCM.
8. No entregar ningún keyset hasta que AEAD, framing interno y ambos keysets hayan sido validados.

Un rechazo temprano debe ser barato y no debe reservar memoria proporcional a longitudes declaradas no validadas.

## Concurrencia y agotamiento de recursos

Una apertura protegida aceptada consume aproximadamente 64 MiB para el área de memoria Argon2id, además de memoria auxiliar del proceso. Varias aperturas simultáneas multiplican ese consumo.

La librería no debe crear concurrencia interna para abrir contenedores. La aplicación integradora debe limitar el número de aperturas simultáneas de acuerdo con su presupuesto de memoria. Si la librería incorpora posteriormente un mecanismo de admisión, deberá ser explícito, configurable y estar cubierto por pruebas; no debe introducir bloqueos globales ocultos ni alterar el contrato criptográfico.

El parser debe rechazar parámetros no admitidos sin intentar la KDF. Las pruebas de robustez deben demostrar que valores extremos de memoria, iteraciones o paralelismo se rechazan rápidamente.

## Benchmark requerido antes de cerrar el perfil

El perfil 64 MiB / 3 iteraciones / paralelismo 1 es una propuesta inicial, no una garantía de rendimiento.

El procedimiento y la herramienta reproducible están definidos en [Benchmark reproducible de Argon2id](argon2id-benchmark.md). El ejecutable es `tests/backend_validation/benchmark_argon2id.py`; mide latencia, distribución de tiempos y lotes concurrentes controlados. No forma parte de la API pública ni se ejecuta en CI por defecto.

Antes de declararlo definitivo se debe medir:

- Un equipo de escritorio o portátil de gama modesta.
- Un equipo de memoria limitada dentro de las plataformas objetivo.
- Tiempo por derivación, memoria teórica y comportamiento bajo aperturas concurrentes.
- Distribución de tiempos en ejecuciones repetidas, no solo una medición aislada.
- Compatibilidad del resultado derivado entre las versiones de Python y plataformas soportadas.

Como objetivo inicial de experiencia de uso, se propone que una apertura individual tarde aproximadamente entre 0,5 y 1,5 segundos en el equipo de referencia modesto. Este intervalo es un objetivo de benchmark, no un criterio criptográfico ni un límite que autorice reducir el coste sin revisión.

Si el perfil no resulta viable en el hardware objetivo, se debe revisar explícitamente el perfil y su política de seguridad antes de cambiarlo. No se debe rebajar automáticamente el coste en función del equipo.

## Fixtures y separación entre prueba y producción

Los vectores golden actuales utilizan parámetros Argon2id deliberadamente reducidos para mantener rápidas las pruebas. Son fixtures sintéticos y no representan contenedores que el parser productivo deba aceptar.

Las pruebas del formato pueden continuar validando esos vectores mediante su verificador exclusivo de tests. Las pruebas del parser productivo deben utilizar el perfil de producción aprobado y keysets Tink auténticos.

Debe existir al menos una prueba que confirme que el parser productivo rechaza los parámetros de fixture **antes de invocar Argon2id**.

## Decisiones pendientes

- [ ] Ejecutar benchmark del perfil propuesto en hardware modesto y plataformas objetivo.
- [ ] Aprobar o ajustar el perfil de producción a partir de esos resultados.
- [ ] Confirmar los límites de entrada y contraseña antes de congelar el contrato de implementación.
- [ ] Añadir pruebas del parser productivo que verifiquen rechazo previo a KDF y límites de concurrencia/admisión si se implementa.

Hasta completar estas decisiones, los valores de esta política deben tratarse como propuesta y no como comportamiento ya implementado.
