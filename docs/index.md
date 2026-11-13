# Documentación de fscryptography

Referencia técnica de la librería. El README es una presentación breve; las decisiones normativas y contratos viven aquí.

## Documentos
- [Alcance](scope.md)
- [Arquitectura](architecture.md)
- [Diseño criptográfico](cryptographic-design.md)
- [Gestión de claves](key-management.md)
- [Formato de MasterKey](master-key-format.md)
- [Cifrado de nombres](filename-encryption.md)
- [Formato de archivos](file-format.md)
- [Operaciones atómicas](atomic-operations.md)
- [API pública](api-reference.md)
- [Errores](errors.md)
- [Modelo de seguridad](security-model.md)
- [Compatibilidad](platform-compatibility.md)
- [ADR 0001: diseño inicial](decisions/0001-initial-design.md)

## Estado
**Definido** identifica requisitos acordados. **Propuesto** identifica el diseño preferido pendiente de validación. **Pendiente** señala decisiones aún abiertas. **Fuera de alcance** identifica capacidades que no pertenecen a la librería.

No se debe presentar una propuesta como funcionalidad implementada. La validación del backend, los formatos binarios y las garantías de recuperación preceden a la implementación.
