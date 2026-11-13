# ADR 0001: Diseño inicial

- Estado: aceptado como línea de diseño; detalles sujetos a validación.
- Fecha: 2026-11-12

## Contexto

Se requiere una librería Python autónoma para cifrar y descifrar contenido de archivos y nombres del filesystem mediante rutas, sin asumir exploración ni administración de recursos.

## Decisiones

1. Nombre del paquete: fscryptography.
2. API centrada en rutas del filesystem.
3. Operaciones de directorio transforman solo el nombre.
4. No hay API pública de cifrado de bytes/streams.
5. AES-256-GCM es la familia elegida para cifrado autenticado.
6. Procesamiento segmentado; tamaño objetivo predeterminado de 1 MiB.
7. Google Tink es candidato principal para Streaming AEAD.
8. Argon2id protege mediante contraseña el contenedor de claves cuando el consumidor elige esa modalidad.
9. `Crypto.generate(password=...)` es alias de `Crypto.derive(text=...)`; ambos devuelven un contenedor MasterKey protegido por contraseña.
10. `Crypto(master_key=..., password=...)` requiere la contraseña para abrir un contenedor protegido. Un contenedor aleatorio generado sin contraseña no requiere password.
11. El contenedor contiene keysets independientes para contenido y nombres.
12. `MasterKey` es un contenedor binario versionado, representado públicamente como Base64 estándar con padding y opaco para el consumidor.
13. El modo aleatorio almacena el payload de keysets sin cifrado de envoltura; el modo protegido cifra y autentica ese payload con una clave derivada mediante Argon2id.
14. Descifrado de recursos es autocontenido: recurso cifrado más el material MasterKey requerido para abrir sus keysets.
15. Temporales y publicación controlada; no sobrescribir por defecto.
16. No existe dependencia de fsresource-tree.
17. Asimetría para envolver/intercambiar claves queda fuera de v1.

## Consecuencias

El contenedor protegido debe incluir versión, identificador de KDF, salt, parámetros de coste, identificador AEAD, nonce y ciphertext autenticado de los keysets. La cabecera y los parámetros que controlan la interpretación se autentican como AAD. La contraseña no se persiste.

El modo aleatorio no ofrece autenticación criptográfica del contenedor frente a modificaciones deliberadas; el consumidor debe proteger el valor completo como secreto. Base64 no aporta protección.

La estructura lógica del contenedor está definida en `docs/master-key-format.md`. La disposición binaria exacta, la serialización de keysets, el AEAD de envoltura y los parámetros Argon2id deben validarse antes de implementar.

Antes de implementar también deben cerrarse formato autocontenido de recursos, contrato de errores, reglas de nombres y recuperación. La atomicidad debe describirse por niveles; `os.replace()` no garantiza transacción multioperación ni durabilidad universal.

## Rechazos

No implementar primitivas propias, no crear API genérica de bytes/streams, no añadir exploración recursiva ni lotes, no acoplar a fsresource-tree y no introducir múltiples backends sin necesidad demostrada.
