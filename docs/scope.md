# Alcance y responsabilidades

## Propósito

fscryptography proporciona una API Python para cifrar y descifrar contenido de archivos regulares y transformar nombres de archivos y directorios mediante rutas del sistema de archivos.

## Responsabilidades

- Cifrar y descifrar contenido de archivos regulares con Streaming AEAD.
- Cifrar y descifrar nombres de archivos y directorios con un keyset independiente.
- Procesar archivos grandes de forma secuencial y segmentada.
- Proteger confidencialidad e integridad mediante AEAD.
- Mantener junto al archivo los metadatos autenticados necesarios para reconstruir la extensión.
- Evitar publicar resultados parciales y no reemplazar destinos existentes.
- Registrar el estado transaccional e inspeccionar journals sin resolverlos automáticamente.

## Exclusiones

No explora ni descubre recursos, no busca ni filtra, no recorre árboles, no procesa lotes, no ofrece cifrado público de bytes arbitrarios ni streams del consumidor, y no administra almacenamiento, transporte, backup, intercambio, rotación ni recuperación externa de claves.

No depende de fsresource-tree ni de ninguna aplicación. Una aplicación puede combinar ambas librerías; fscryptography solo recibe rutas.

## Directorios

Las operaciones de directorio transforman exclusivamente su nombre. Nunca recorren, cifran ni descifran su contenido.

## Tipos de recurso admitidos y rechazados

- Se admiten archivos regulares con un único enlace duro y directorios.
- Se rechazan enlaces simbólicos, archivos con hard links múltiples, dispositivos, sockets, FIFOs y reparse points de Windows.
- No se siguen enlaces implícitamente.
- La librería no promete operar sobre puntos de montaje, proveedores de archivos virtuales, placeholders de nube ni todos los tipos especiales de filesystem.
- Las reglas específicas de NTFS/ext4 y sus límites se detallan en la documentación de compatibilidad.

## Metadatos visibles y no preservados

Cifrar nombres no oculta cantidad de recursos, jerarquía, tamaños, timestamps, permisos, propietarios ni patrones de acceso.

Las transformaciones de archivo crean objetos nuevos y no preservan automáticamente permisos, propietario/grupo, ACL, xattrs, alternate data streams, atributos especiales ni timestamps del origen. Las operaciones de directorio renombran el mismo objeto y no recorren sus hijos.

## Responsabilidad del consumidor

El consumidor debe realizar y verificar backups, proteger la MasterKey y su contraseña, definir una política de almacenamiento y coordinar operaciones sobre un mismo recurso. La librería no proporciona un gestor de backups ni recuperación automática.
