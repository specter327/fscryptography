# Documentación de fscryptography

Referencia técnica de la librería. El README contiene la presentación del proyecto y el manual práctico de API; las decisiones normativas y contratos técnicos viven en esta documentación.

## Documentos
- [Alcance](scope.md)
- [Arquitectura](architecture.md)
- [Diseño criptográfico](cryptographic-design.md)
- [Validación del backend criptográfico](backend-validation.md)
- [Gestión de claves](key-management.md)
- [Formato de MasterKey](master-key-format.md)
- [Política de Argon2id y límites de apertura](argon2id-policy.md)
- [Benchmark reproducible de Argon2id](argon2id-benchmark.md)
- [Plan de pruebas del formato MasterKey](master-key-format-test-plan.md)
- [Cifrado de nombres](filename-encryption.md)
- [Formato de archivos](file-format.md)
- [Operaciones atómicas](atomic-operations.md)
- [Journal persistente y protocolo de recuperación](recovery-journal.md)
- [API pública](api-reference.md)
- [Errores y excepciones — contrato v1](errors.md)
- [Modelo de seguridad](security-model.md)
- [Compatibilidad](platform-compatibility.md)
- [Construcción y publicación en PyPI](releasing.md)
- [ADR 0001: diseño inicial](decisions/0001-initial-design.md)

## Estado
**Definido** identifica requisitos acordados. **Propuesto** identifica el diseño preferido pendiente de validación. **Pendiente** señala decisiones aún abiertas. **Fuera de alcance** identifica capacidades que no pertenecen a la librería.

No se debe presentar una propuesta como funcionalidad implementada. La implementación principal y la validación automatizada de backend, formatos y filesystem están presentes; la versión estable sigue condicionada a las validaciones residuales enumeradas en los documentos técnicos.


## Estado de madurez

La librería dispone de implementación funcional, formatos v1.0 documentados, pruebas unitarias, integración filesystem en runners ext4/NTFS, CI de dependencias mínimas y distribución wheel/sdist. Continúan pendientes la validación específica de Windows 11 cliente, fuzzing/property-based de parsers, escenarios ampliados de interrupción en Windows, revisión independiente y preparación final de release.
