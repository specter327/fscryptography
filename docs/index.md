# Documentación de fscryptography

Referencia técnica y normativa de la biblioteca. El README funciona como presentación y manual práctico de la API; los contratos y decisiones técnicas se desarrollan aquí.

## Introducción
- [Presentación del proyecto](product-overview.md)
- [Alcance](scope.md)
- [Arquitectura](architecture.md)

## API y uso
- [Manual de uso](../README.md#manual-de-uso-de-la-api)
- [Referencia de API pública](api-reference.md)
- [Errores y excepciones — contrato v1](errors.md)

## Diseño y formatos criptográficos
- [Diseño criptográfico](cryptographic-design.md)
- [Gestión de claves](key-management.md)
- [Formato MasterKey](master-key-format.md)
- [Política de Argon2id y límites de apertura](argon2id-policy.md)
- [Benchmark reproducible de Argon2id](argon2id-benchmark.md)
- [Plan de pruebas del formato MasterKey](master-key-format-test-plan.md)
- [Cifrado de nombres](filename-encryption.md)
- [Formato de archivos](file-format.md)

## Filesystem y recuperación
- [Operaciones atómicas](atomic-operations.md)
- [Journal persistente e inspección de recuperación](recovery-journal.md)
- [Compatibilidad de plataformas](platform-compatibility.md)
- [Modelo de seguridad](security-model.md)
- [Endurecimiento del filesystem](filesystem-hardening.md)

## Calidad y distribución
- [Validación del backend criptográfico](backend-validation.md)
- [Construcción y publicación en PyPI](releasing.md)
- [ADR 0001: diseño inicial](decisions/0001-initial-design.md)

## Estado

**Definido** identifica requisitos acordados. **Propuesto** identifica el diseño preferido pendiente de validación. **Pendiente** señala decisiones aún abiertas. **Fuera de alcance** identifica capacidades que no pertenecen a la biblioteca.

No se debe presentar una propuesta como funcionalidad implementada. Las garantías de formatos, backend y recuperación deben distinguirse de los aspectos que todavía requieren validación.
