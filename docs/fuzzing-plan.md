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

## Fase A — Repetición reproducible de Hypothesis

En un checkout limpio de la rama candidata:

```bash
python -m pip install -e ".[test]"
git rev-parse HEAD
python -m pytest --collect-only -q
python -m pytest -q --hypothesis-show-statistics tests
```

Conserva SHA, versión Python/dependencias, estadísticas Hypothesis y salida completa. Para reproducir un fallo, conserva la semilla/ejemplo mínimo que Hypothesis informe y conviértelo en una regresión determinista.

No asumas un perfil Hypothesis adicional si no está declarado por el proyecto. No cambies el número de ejemplos de CI sin revisar antes el tiempo de ejecución y la cobertura real.

## Fase B — Campaña prolongada

Ejecuta en un runner dedicado, sin datos importantes, con CPU y memoria monitorizadas. La campaña inicial recomendada es de 24 horas por plataforma Linux y Windows; si el presupuesto no lo permite, registra explícitamente el tiempo menor y no lo describas como campaña de 24 horas.

Ejemplo Bash para una campaña de 24 horas que repite la suite existente y conserva cada salida:

```bash
mkdir -p artifacts/fuzz
deadline=$((SECONDS + 24 * 60 * 60))
iteration=0
while (( SECONDS < deadline )); do
  iteration=$((iteration + 1))
  printf 'iteration=%s start=%s\n' "$iteration" "$(date -Is)" \
    | tee -a artifacts/fuzz/campaign.log
  python -m pytest -q --hypothesis-show-statistics tests \
    > "artifacts/fuzz/run-${iteration}.log" 2>&1
  status=$?
  printf 'iteration=%s exit=%s end=%s\n' "$iteration" "$status" "$(date -Is)" \
    | tee -a artifacts/fuzz/campaign.log
  if (( status != 0 )); then
    echo "Failure detected; stopping campaign." | tee -a artifacts/fuzz/campaign.log
    exit "$status"
  fi
done
```

En Windows PowerShell, usa un bucle equivalente con `Get-Date` e invocación de `python -m pytest`, redirigiendo una salida distinta por iteración. No ejecutes campañas concurrentes que compitan por el mismo directorio de fixtures.

Esta repetición prolonga la exploración Hypothesis existente, pero no garantiza inputs nuevos en cada iteración. Para fuzzing coverage-guided real, añade posteriormente un harness dedicado (por ejemplo, Atheris para superficies Python compatibles) y define corpus, cobertura, límites de recursos y sanitización antes de declararlo operativo.

## Fase C — Corpus y regresiones

Mantén corpus sintéticos versionados por superficie. Cada hallazgo debe incluir identificador/severidad, SHA del commit, versiones de entorno, entrada mínima reproducible o fixture, comando/semilla, resultado esperado y observado, traza sin secretos, corrección y test de regresión.

No almacenes dumps de memoria, MasterKeys, contraseñas, datos personales ni ciphertexts de usuarios.

## Fase D — Criterios de cierre

Una campaña solo puede marcarse aprobada cuando:

- Se completó el tiempo planificado y se registró el tiempo efectivo.
- No quedan fallos sin triage.
- Los hallazgos corregidos tienen pruebas de regresión.
- Los casos de parser y formato corren en CI normal.
- Se registraron commit, intérprete, SO, dependencias, CPU/memoria y artefactos.
- Se separan claramente pruebas Hypothesis repetidas de cualquier fuzzing coverage-guided.

Cualquier crash, excepción inesperada, consumo desproporcionado de memoria/CPU o publicación de plaintext parcial bloquea el cierre.

## Estado

- [x] Identificar pruebas property-based existentes como evidencia acotada, no fuzzing prolongado.
- [x] Definir superficies, invariantes, corpus y política de regresiones.
- [x] Definir procedimiento reproducible para campaña prolongada.
- [ ] Ejecutar campaña de 24 horas en GNU/Linux.
- [ ] Ejecutar campaña de 24 horas en Windows 11 cliente.
- [ ] Triar todos los hallazgos y añadir regresiones.
- [ ] Implementar y ejecutar harness coverage-guided si se decide incluirlo en el alcance de la versión estable.
