# Política de Argon2id y límites de apertura de MasterKey

## Estado

**Perfil Argon2id v1 aprobado para la referencia de hardware evaluada.** La validación de portabilidad en otros equipos se omite por decisión del proyecto y no se presenta como realizada.

Esta política define el perfil de protección por contraseña y los límites que deben comprobarse antes de ejecutar Argon2id. No modifica el layout binario v1.0 aprobado: los parámetros continúan almacenándose en los campos ya definidos de la cabecera protegida.

Los valores de los fixtures de prueba no son parámetros de producción. La aprobación del perfil no implica que el parser productivo o la gestión de claves estén implementados.

## Perfil de producción aprobado

| Parámetro | Valor |
|---|---:|
| Función | Argon2id |
| Versión | 0x13 (19) |
| Memoria | 65.536 KiB (64 MiB) |
| Iteraciones | 3 |
| Paralelismo | 1 |
| Salt | 16 bytes aleatorios |
| Clave derivada | 32 bytes |

El perfil prioriza una huella de memoria moderada y un coste temporal significativo sin multiplicar la memoria mediante paralelismo. Se aprobó con base en las mediciones del equipo de referencia Linux x86_64 descritas en [Benchmark reproducible de Argon2id](argon2id-benchmark.md). No constituye una garantía universal de rendimiento ni certifica plataformas no medidas.

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

| Elemento | Límite normativo v1 | Validación |
|---|---:|---|
| Contenedor binario | 131.149 bytes máximo | Antes de parsear campos variables |
| Texto Base64 | 174.868 caracteres ASCII máximo | Antes de decodificar |
| Contraseña UTF-8 | 1.024 bytes máximo; no vacía | Antes de ejecutar Argon2id |
| Salt | Exactamente 16 bytes | Parser estructural |
| Nonce AES-GCM | Exactamente 12 bytes | Parser estructural |
| Tag AES-GCM | Exactamente 16 bytes | AEAD / longitud mínima |

El máximo binario deriva del modo protegido: cabecera de 61 bytes + payload lógico máximo de 131.072 bytes + tag GCM de 16 bytes. El máximo Base64 corresponde a la codificación estándar con padding de ese tamaño binario máximo.

Estos límites quedan aprobados como parte del contrato normativo de MasterKey v1. No son valores configurables por el consumidor ni límites sugeridos. La entrada Base64 debe validarse estrictamente. No se deben ignorar caracteres ajenos al alfabeto Base64, espacios, saltos de línea ni padding incorrecto. No se debe decodificar una entrada arbitrariamente grande para comprobar su tamaño después.

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

## Validación de rendimiento y alcance de la aprobación

El benchmark del perfil 64 MiB / 3 iteraciones / paralelismo 1 se ejecutó en el equipo de referencia del proyecto. El procedimiento, las métricas de latencia y las mediciones RSS están registradas en [Benchmark reproducible de Argon2id](argon2id-benchmark.md).

La evaluación cubrió 30 lotes por nivel de concurrencia (1 y 2), con cinco llamadas de calentamiento, y mediciones separadas de RSS mediante GNU `/usr/bin/time -v`. El equipo registró RSS máximo de 85.712 KiB con una derivación y 151.180 KiB con dos derivaciones simultáneas. Ambas ejecuciones finalizaron sin swap y con código de salida cero.

Se adopta una latencia individual orientativa de 0,5–1,5 segundos como objetivo de experiencia de uso, no como criterio criptográfico ni como autorización para reducir el coste. Las mediciones observadas quedaron dentro de ese intervalo en sus medianas; los máximos concurrentes pueden superar un segundo.

Por decisión del proyecto no se realizarán más pruebas de portabilidad en otros equipos en esta fase. La aprobación se limita al perfil de producción v1 y a la referencia medida; no certifica el rendimiento ni la memoria en todas las plataformas. No se debe rebajar automáticamente el coste en función del equipo.

## Fixtures y separación entre prueba y producción

Los vectores golden actuales utilizan parámetros Argon2id deliberadamente reducidos para mantener rápidas las pruebas. Son fixtures sintéticos y no representan contenedores que el parser productivo deba aceptar.

Las pruebas del formato pueden continuar validando esos vectores mediante su verificador exclusivo de tests. Las pruebas del parser productivo deben utilizar el perfil de producción aprobado y keysets Tink auténticos.

Debe existir al menos una prueba que confirme que el parser productivo rechaza los parámetros de fixture **antes de invocar Argon2id**.

## Decisiones y trabajo pendiente

- [x] Ejecutar benchmark repetido del perfil en el equipo de referencia del proyecto.
- [x] Aprobar Argon2id v19 / 65.536 KiB / 3 / 1 como perfil de producción v1.
- [x] Confirmar los límites de entrada y contraseña como parte del contrato normativo de MasterKey v1.
- [ ] Añadir pruebas del parser productivo que verifiquen rechazo previo a KDF y límites de concurrencia/admisión si se implementa.

El perfil criptográfico y los límites de entrada de MasterKey v1 están aprobados. La implementación productiva y sus pruebas siguen pendientes.
