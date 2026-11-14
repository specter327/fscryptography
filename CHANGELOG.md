# Historial de cambios

Los cambios de API, formatos, compatibilidad y seguridad se registran aquí. Las versiones del paquete, del formato de archivo y de MasterKey son independientes; véase docs/versioning.md.

## [Unreleased]

### Added
- Endurecimiento de concurrencia, transacciones, publicación sin reemplazo y retirada segura del origen.
- Validación de metadatos del filesystem, nombres Unicode, límites UTF-16 de Windows, PathLike y rutas largas.
- Matriz CI con evidencia de ext4 y NTFS, además de validación de dependencias mínimas.
- Vectores golden del encabezado de archivo y pruebas property-based acotadas.
- Política de seguridad y reporte privado de vulnerabilidades.

### Changed
- Cada operación conserva una instantánea coherente de primitivas durante la rotación de Manager.
- Se documenta que change_key() no re-encripta recursos existentes y que close() no garantiza borrado seguro de memoria.
- Se precisa el alcance de compatibilidad: Windows Server 2025/NTFS está probado en CI; Windows 11 cliente sigue pendiente.
- Se eliminan los directorios transaccionales persistentes; los temporales de resultado y staging son entradas hermanas efímeras. No hay recuperación automática tras interrupciones abruptas.

### Security
- Se rechazan symlinks, hard links múltiples y reparse points de Windows como recursos fuente.
- Se documentan los límites frente a procesos con permisos equivalentes, pérdida de energía y ausencia de auditoría independiente.

## [0.1.0] — Alpha inicial

Versión alpha inicial del paquete fscryptography. Consulta el README y la documentación versionada para el contrato de esta versión.
