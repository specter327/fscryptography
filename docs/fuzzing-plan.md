# Plan de fuzzing y pruebas prolongadas

## Objetivo y límites

Este plan amplía la evidencia de las pruebas property-based existentes. Busca entradas malformadas, excepciones no clasificadas, violaciones de invariantes y regresiones en parsers y fronteras criptográficas.

Las pruebas Hypothesis actuales son acotadas. Repetirlas durante más tiempo aumenta la exploración, pero **no equivale a fuzzing coverage-guided**, fuzzing de memoria nativa, revisión criptográfica ni auditoría independiente. Este plan no debe presentarse como certificación.

## Superficies prioritarias

1. Parser de cabecera de archivo: truncamientos en cada offset, flags, versiones, longitudes, campos reservados y bytes adicionales.
2. Contenedor MasterKey: Base64 inválido, padding, límites de tamaño, protobuf malformado, campos duplicados/desconocidos, keysets truncados y tipos de primitive incorrectos.
3. Perfil KDF protegido: identificadores/versiones/parámetros no admitidos, salt/nonce truncados y contraseñas UTF-8 en los límites del contrato.
4. Codec de nombres: Base64URL inválido, marcador, ciphertext vacío/truncado, UTF-8 inválido, longitudes y equivalencias de nombres específicas del filesystem.
5. Framing y Streaming AEAD: ciphertext truncado, alterado, concatenado o con trailer incompleto; confirmar que nunca se publica plaintext parcial.
6. Límites de operaciones filesystem: nombres en límites de bytes/UTF-16, colisiones, recursos sustituidos y fallos de I/O durante publicación/retirada.

No uses secretos reales ni corpus derivados de archivos privados.

## Invariantes

- Las entradas arbitrarias no provocan excepciones inesperadas fuera del contrato público.
- Los parsers rechazan formatos inválidos antes de ejecutar KDF costosas cuando el perfil puede validarse previamente.
- Los límites de longitud se aplican antes de asignaciones o trabajo costoso.
- Ninguna entrada no autenticada se publica como plaintext definitivo.
- Un fallo conserva el origen conforme al contrato documentado y no sobrescribe destinos existentes.
- Las excepciones públicas permanecen clasificadas y estables.
- Un caso que encuentre un defecto se reduce, se conserva como fixture/regresión y se ejecuta en CI.

## Fase A — Ejecución reproducible

En un checkout limpio de la rama candidata:

```bash
python -m pip install -e ".[test]"
git rev-parse HEAD
python -m pytest --collect-only -q
python -m pytest -q --hypothesis-show-statistics tests
```

Conserva SHA, versión Python/dependencias, estadísticas Hypothesis y salida completa. Para reproducir un fallo, conserva la semilla/ejemplo mínimo que Hypothesis informe y conviértelo en una regresión determinista.

No asumas un perfil Hypothesis adicional si no está declarado por el proyecto. No cambies el número de ejemplos de CI sin revisar antes el tiempo de ejecución y la cobertura real.

## Fase B — Campaña prolongada opcional

El repositorio incluye `tools/fuzz/run_hypothesis_campaign.py`, un ejecutor multiplataforma basado exclusivamente en la biblioteca estándar. Repite la suite existente, conserva un log por iteración y escribe `campaign.json` con SHA, intérprete, sistema, versiones disponibles de paquetes, duración efectiva, comando y códigos de salida.

Si en el futuro se necesita evidencia adicional, puede ejecutarse una campaña prolongada en un runner dedicado. **No forma parte de los criterios de cierre de esta versión**. Ejemplo de ejecución opcional de 24 horas:

```bash
python -m pip install -e ".[test]"
python tools/fuzz/run_hypothesis_campaign.py --duration-seconds 86400 --output-dir artifacts/fuzz/linux
```

En Windows PowerShell, el mismo comando Python es válido:

```powershell
py -m pip install -e ".[test]"
py tools/fuzz/run_hypothesis_campaign.py --duration-seconds 86400 --output-dir artifacts/fuzz/windows-11
```

Para comprobar operativamente el ejecutor antes de una campaña opcional:

```bash
python tools/fuzz/run_hypothesis_campaign.py --duration-seconds 60 --output-dir artifacts/fuzz/smoke
```

Cada directorio de salida es de una sola campaña: el ejecutor se niega a sobrescribir un `campaign.json` existente. Usa un directorio nuevo para cada ejecución. El código de salida distinto de cero indica que una iteración falló; detén el análisis y realiza triage antes de reanudar. Una interrupción externa puede dejar el manifiesto con estado `running`; no la registres como campaña completada.

Ejecuta en un runner dedicado, sin datos importantes, con CPU y memoria monitorizadas externamente. Registra también el modelo de CPU, memoria disponible, versión/build exactos del SO, filesystem y configuración del volumen, ya que estos datos dependen del entorno y no se infieren de forma fiable desde el ejecutor. No ejecutes campañas concurrentes que compitan por el mismo directorio de fixtures.

Esta repetición prolonga la exploración Hypothesis existente, pero no garantiza inputs nuevos en cada iteración. No equivale a fuzzing coverage-guided. Para añadir Atheris u otro motor de cobertura, define primero superficies compatibles, corpus sintético, cobertura, límites de recursos y soporte por plataforma; no se considera parte de esta tarea.

## Fase C — Corpus y regresiones

Mantén corpus sintéticos versionados por superficie. Cada hallazgo debe incluir identificador/severidad, SHA del commit, versiones de entorno, entrada mínima reproducible o fixture, comando/semilla, resultado esperado y observado, traza sin secretos, corrección y test de regresión.

No almacenes dumps de memoria, MasterKeys, contraseñas, datos personales ni ciphertexts de usuarios.

## Fase D — Criterios de cierre

Para cerrar la validación automatizada de esta versión:

- Los casos deterministas y property-based acotados corren en CI normal.
- Los fallos conocidos tienen pruebas de regresión.
- Se registran commit, intérprete, SO y dependencias de los resultados CI.
- Se distinguen las pruebas Hypothesis acotadas de cualquier fuzzing coverage-guided.

La campaña prolongada de la Fase B queda como actividad opcional de aseguramiento adicional, no como condición de cierre. Si se ejecuta, cualquier crash, excepción inesperada, consumo desproporcionado de recursos o publicación de plaintext parcial requiere triage.

## Estado

- [x] Identificar pruebas property-based existentes como evidencia acotada, no fuzzing prolongado.
- [x] Definir superficies, invariantes, corpus y política de regresiones.
- [x] Definir procedimiento reproducible para campaña prolongada.
- [x] Añadir ejecutor multiplataforma que conserva manifiesto y logs por iteración.
- [ ] Campaña prolongada opcional en GNU/Linux (fuera del alcance de cierre de esta versión).
- [ ] Campaña prolongada opcional en Windows 11 cliente (fuera del alcance de cierre de esta versión).
- [ ] Implementar y ejecutar harness coverage-guided si se decide incluirlo en el alcance de la versión estable.

## Ejecución en infraestructura CI y selección del entorno

Si se decide ejecutar en el futuro, la campaña completa de 24 horas **no se debe ejecutar como un único job de GitHub-hosted Actions**. Los límites de duración de los jobs y la disponibilidad efímera del runner hacen que ese enfoque no sea una sustitución fiable de un equipo dedicado. Tampoco se debe dividir una campaña en segmentos y sumar sus duraciones como si fueran una única ejecución continua: cada segmento reinicia el proceso y puede cambiar el estado exploratorio de Hypothesis.

Usa GitHub Actions para validar el código y el contrato del ejecutor, no para declarar completada la campaña prolongada. Si se ejecuta, la evidencia de 24 horas debe proceder de un equipo dedicado o runner self-hosted controlado, con el manifiesto y los logs completos conservados como artefactos.

### Distinción de plataformas Windows

La campaña prolongada en Windows también es opcional. La validación de compatibilidad de filesystem en Windows 11 cliente se trata por separado en `docs/windows-11-validation.md`.

Un job de Actions que use `windows-latest` valida el entorno Windows administrado por GitHub; **no demuestra compatibilidad en una instalación cliente de Windows 11**. Para cerrar ese requisito, ejecuta la campaña en un equipo Windows 11 real y registra la edición, versión y build exactas del sistema, además de Python, filesystem y hardware.

### Lista de preparación antes de cada campaña

1. Crear un checkout limpio de la rama y registrar el SHA exacto.
2. Confirmar que no existen cambios locales sin registrar y que no se reutiliza un directorio de salida.
3. Instalar las dependencias de prueba desde el proyecto.
4. Ejecutar primero la campaña operativa de 60 segundos en un directorio nuevo.
5. Revisar que el manifiesto termina con `status: completed`, que contiene al menos una iteración y que cada log referenciado existe.
6. Solo entonces iniciar la campaña de 86400 segundos en otro directorio nuevo.
7. Monitorizar CPU, memoria, espacio en disco y temperatura externamente durante la ejecución.
8. Al terminar, conservar sin modificar `campaign.json`, `campaign.log` y todos los `run-*.log`; calcular hashes del paquete de evidencia si se va a transferir.
9. Revisar el código de salida y el manifiesto. Cualquier fallo, interrupción o estado `running` requiere triage; no se contabiliza como campaña aprobada.

No ejecutes simultáneamente dos campañas sobre el mismo checkout ni compartas el directorio de salida entre plataformas. Para comparar resultados, registra cada entorno como una campaña independiente.
