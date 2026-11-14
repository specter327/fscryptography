# Versionado y compatibilidad

## Tres versiones independientes

El proyecto mantiene versionados separados:

1. Versión del paquete Python: project.version y fscryptography.__version__.
2. Formato de archivo: cabecera FSCRFIL, actualmente v1.0.
3. Formato MasterKey: contenedor FSCRKEY, actualmente v1.0.

Cambiar la versión del paquete no cambia implícitamente los formatos binarios. Un archivo v1.0 y una MasterKey v1.0 se identifican por sus propios encabezados.

## API Python

Mientras el paquete permanezca en 0.x, la API pública puede cambiar entre versiones alpha/minor; cada cambio debe registrarse en CHANGELOG.md y documentarse.

La versión 1.0.0 congelará, como mínimo:

- Funciones, clases y métodos públicos exportados.
- Nombres, tipos, valores por defecto y semántica de parámetros.
- Retornos, excepciones públicas y comportamiento de Manager.
- Contrato de rutas, tipos de recursos, metadatos y errores.
- Sistemas operativos, versiones de Python y filesystems efectivamente soportados.

Después de 1.0.0, los cambios incompatibles de API requieren una versión mayor. Las correcciones compatibles pueden publicarse como patch; las adiciones compatibles como minor.

## Formato binario de archivos

El formato actual es FSCRFIL v1.0, documentado en file-format.md, con vectores golden versionados en tests.

- La estructura v1.0 queda congelada: no reinterpretar campos, flags ni bytes reservados.
- No añadir campos obligatorios ni cambiar la semántica de metadatos en v1.0.
- El parser rechaza versiones desconocidas; no intenta downgrade ni heurísticas.
- Una estructura incompatible requiere una nueva versión de formato y un parser explícito para cada versión admitida.
- Los lectores futuros deben mantener pruebas de conformidad y vectores golden para cada versión que declaren soportada.

El parser actual acepta exactamente major 1, minor 0. No se promete compatibilidad automática con hipotéticas versiones 1.1 o 2.0.

## Formato MasterKey

El contenedor actual es FSCRKEY v1.0, documentado en master-key-format.md.

- No cambiar el framing, parámetros KDF, identificadores ni semántica de keysets de v1.0.
- El parser rechaza versiones, perfiles KDF y esquemas no admitidos.
- Una versión nueva requiere dispatch explícito y vectores golden nuevos.
- El contenedor MasterKey y el formato de archivo son independientes; cambiar uno no modifica el otro.

## Cambio de clave frente a migración de datos

Manager.change_key() sustituye el contexto criptográfico para operaciones futuras. No vuelve a cifrar archivos existentes, no reescribe cabeceras y no migra nombres.

Un recurso cifrado con una MasterKey anterior requiere esa misma MasterKey para descifrarse. El consumidor debe conservar un inventario de claves y planificar explícitamente cualquier migración. La librería no ofrece actualmente una herramienta de re-encriptación masiva ni de rotación global.

## Versiones soportadas

- Durante alpha (0.x): se prioriza la versión publicada más reciente; no hay LTS.
- La política de soporte estable se definirá antes de publicar 1.0.0.
- Los formatos v1.0 tienen su propia política de compatibilidad y no heredan automáticamente el ciclo de vida de la versión del paquete.

## Release gates

Antes de declarar 1.0.0:

- [ ] API pública y jerarquía de errores revisadas y congeladas.
- [ ] Formatos FSCRFIL v1.0 y FSCRKEY v1.0 revisados, golden vectors y política de evolución publicadas.
- [ ] CHANGELOG completo y procedimiento de migración/retención de claves documentado.
- [ ] Matriz de plataformas y límites soportados verificados.
- [ ] Política de vulnerabilidades habilitada y canal privado comprobado.
- [ ] TestPyPI validado desde instalación limpia.
