# Benchmark reproducible de Argon2id

## Estado

Herramienta de medición disponible para desarrollo. **El perfil 64 MiB / 3 / p=1 continúa siendo una propuesta** hasta obtener resultados en el hardware objetivo y aprobarlos explícitamente. Este benchmark no implementa ni modifica la apertura de `MasterKey`.

## Artefacto

El ejecutable `tests/backend_validation/benchmark_argon2id.py` mide la derivación Argon2id usando `argon2-cffi` y los parámetros seleccionados para la propuesta:

- Argon2id, versión 19 (`0x13`).
- Memoria: 65.536 KiB.
- Iteraciones: 3.
- Paralelismo: 1.
- Salida: 32 bytes.

No requiere dependencias adicionales a `argon2-cffi` y la biblioteca estándar de Python. No se ejecuta automáticamente en CI: sus tiempos dependen del hardware y no constituyen una prueba estable de regresión.

## Ejecución de referencia

Desde la raíz del repositorio, con `argon2-cffi` instalado:

```bash
python tests/backend_validation/benchmark_argon2id.py
```

Por defecto realiza dos derivaciones de calentamiento y siete lotes medidos para cada nivel de concurrencia (1 y 2). El nivel máximo está limitado por un presupuesto estimado predeterminado de 256 MiB de memoria Argon2. La herramienta aborta antes de ejecutar la KDF si la memoria configurada multiplicada por la concurrencia excede ese presupuesto.

Para guardar el informe:

```bash
python tests/backend_validation/benchmark_argon2id.py --json argon2id-benchmark.json
```

Los parámetros de ejecución se pueden ajustar explícitamente:

```bash
python tests/backend_validation/benchmark_argon2id.py \
  --iterations 10 \
  --warmup 3 \
  --concurrency 1 2 \
  --max-memory-mib 256
```

El presupuesto es una salvaguarda de memoria de trabajo Argon2 estimada, no una detección de RAM disponible ni una garantía contra OOM. Antes de elevarlo, comprobar memoria libre y cerrar cargas innecesarias.

## Métricas

El informe JSON incluye:

- Identificación del intérprete, plataforma, arquitectura, procesador y CPUs lógicas.
- Versión instalada de `argon2-cffi`.
- Parámetros Argon2id y memoria teórica estimada para la concurrencia máxima.
- Latencia por derivación: mínimo, mediana, máximo y percentil 95 (nearest-rank).
- Tiempo de pared por lote concurrente: mediana y percentil 95.

La memoria estimada corresponde al coste de trabajo configurado multiplicado por el número de derivaciones concurrentes. No incluye overhead del proceso, bibliotecas, runtime ni sistema operativo. No se presenta una medición portable de memoria residente máxima: comparar RSS entre sistemas requeriría instrumentación específica de plataforma y puede confundir el high-water mark histórico del proceso con el consumo de una ejecución concreta.

## Protocolo de medición recomendado

1. Ejecutar en el equipo más modesto que se pretenda soportar, conectado a corriente y en un modo de energía documentado.
2. Registrar modelo de CPU, RAM instalada, sistema operativo, arquitectura, versión de Python y versión de `argon2-cffi`.
3. Cerrar tareas intensivas y evitar medir durante actualizaciones, compilaciones u otras cargas concurrentes.
4. Ejecutar el comando predeterminado al menos tres veces como procesos independientes.
5. Conservar los informes JSON sin modificar y comparar mediana y p95, no una sola observación.
6. Repetir en cada plataforma objetivo, en particular en equipos de memoria limitada.
7. Evaluar la concurrencia según el presupuesto real de memoria de la aplicación. El resultado concurrente no debe interpretarse como autorización para que la librería cree concurrencia interna.

No combinar mediciones tomadas con distintos perfiles de energía, condiciones térmicas o cargas de fondo como si fueran equivalentes.

## Perfil alternativo y pruebas rápidas

El script admite parámetros personalizados para experimentación. Cualquier resultado cuyo perfil no sea exactamente 65.536 KiB / 3 / 1 queda etiquetado como `custom-profile-not-production`.

Un perfil reducido puede servir para comprobar el funcionamiento del script, pero **no** para estimar el rendimiento del perfil propuesto, validar seguridad ni justificar una decisión de producción. Los parámetros reducidos de los golden vectors tampoco son un perfil de producción.

## Seguridad y reproducibilidad

- El benchmark usa una contraseña y un salt fijos, públicos y exclusivos de esta herramienta. No son secretos ni deben reutilizarse en producción.
- No solicita, registra ni persiste contraseñas del usuario.
- No guarda ni muestra las claves derivadas; solo comprueba su longitud.
- El salt fijo hace repetible el trabajo de la KDF, pero no modela la generación aleatoria de salt de producción.
- La herramienta no abre contenedores MasterKey ni keysets Tink y no valida la implementación de producción.
- No debe ejecutarse automáticamente en cada push ni usarse como umbral de CI.

## Criterio de decisión

La propuesta actual plantea una latencia orientativa de 0,5–1,5 segundos para una apertura individual en hardware modesto. El benchmark debe aportar evidencia para decidir si ese objetivo es razonable en los dispositivos objetivo. No se debe reducir automáticamente el coste criptográfico para satisfacer el objetivo temporal.

La decisión final debe registrar:
- Equipos y plataformas medidos.
- Informes completos y condiciones de ejecución.
- Mediana y p95 por dispositivo.
- Memoria teórica por concurrencia y presupuesto operativo de la aplicación.
- Perfil aprobado o cambios explícitos a la política.

Hasta que se revisen esos datos, el perfil permanece propuesto y los límites de apertura siguen pendientes de aprobación.
