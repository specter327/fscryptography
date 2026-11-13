# Política de seguridad

## Versiones soportadas

Antes de 1.0.0, el proyecto está en fase alpha y no ofrece una política de compatibilidad estable. Se priorizarán correcciones de seguridad en la última versión publicada. No existe soporte LTS ni compromiso de mantener ramas antiguas.

Una versión estable 1.0.0 tendrá una política de soporte que se definirá antes de su publicación.

## Reportar una vulnerabilidad

**No publiques vulnerabilidades explotables, ciphertexts privados, MasterKeys, contraseñas ni datos de usuarios en issues, discusiones o pull requests públicos.**

1. Utiliza la función privada **Report a vulnerability** de GitHub Security Advisories para este repositorio, si está disponible.
2. Si la función privada no está habilitada, contacta al mantenedor mediante su perfil de GitHub para solicitar un canal privado. No incluyas detalles técnicos sensibles en el primer mensaje público.
3. Espera una respuesta antes de publicar detalles o una prueba de concepto.

El mantenedor debe habilitar GitHub Private Vulnerability Reporting en la configuración del repositorio antes de declarar el proyecto listo para uso estable. La disponibilidad de esa función depende de la configuración de GitHub; este documento no afirma que esté habilitada actualmente.

## Información útil para el reporte

Incluye, cuando sea seguro:

- Versión de fscryptography y hash del commit.
- Sistema operativo, build, arquitectura y versión de Python.
- Filesystem y opciones de montaje relevantes.
- Pasos mínimos para reproducir el comportamiento.
- Impacto observado y condiciones necesarias para explotarlo.
- Una prueba de concepto mínima sin secretos ni datos reales.

No adjuntes archivos originales, claves, contraseñas, tokens ni información personal. Usa datos sintéticos.

## Coordinación y respuesta

La recepción, análisis, corrección y divulgación se coordinarán de forma privada. El proyecto no promete un SLA de respuesta ni una fecha fija de publicación. La severidad, el alcance afectado y la disponibilidad de una corrección determinarán el calendario.

No publiques una vulnerabilidad antes de acordar la divulgación coordinada, salvo que exista una obligación legal o un riesgo urgente que requiera otra actuación. La asignación de CVE no está garantizada.

## Alcance de seguridad

El modelo de seguridad, las garantías, exclusiones y límites están descritos en [docs/security-model.md](docs/security-model.md). En particular:

- No se protege un host comprometido, el kernel, administradores, procesos privilegiados ni procesos hostiles con permisos equivalentes al usuario que ejecuta la librería.
- No se garantiza borrado seguro de secretos en memoria Python.
- No se ocultan tamaños, estructura, cantidades, timestamps, permisos ni patrones de acceso.
- Los tests CI no equivalen a una auditoría criptográfica independiente ni a pruebas de pérdida de energía.
- El consumidor debe conservar backups y proteger MasterKey y contraseña.

## Auditoría independiente

A la fecha de este documento no se ha declarado ni completado una auditoría de seguridad criptográfica independiente. No interpretes la existencia de pruebas automatizadas o de este documento como certificación, auditoría o garantía de ausencia de vulnerabilidades.
