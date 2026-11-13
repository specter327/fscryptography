# Alcance y responsabilidades

## Propósito
fscryptography proporciona una API Python para cifrar y descifrar contenido de archivos y nombres de archivos y directorios mediante rutas del sistema de archivos.

## Responsabilidades
- Cifrar y descifrar contenido de archivos regulares.
- Cifrar y descifrar nombres de archivos y directorios.
- Procesar archivos grandes con segmentación interna y memoria acotada.
- Proteger confidencialidad e integridad mediante cifrado autenticado.
- Mantener junto al recurso la información necesaria para recuperarlo.
- Evitar publicar resultados parciales ante fallos controlables.

## Exclusiones
No explora ni descubre recursos, no busca ni filtra, no recorre árboles, no procesa lotes, no administra colecciones, no ofrece cifrado público de bytes arbitrarios ni streams del consumidor, y no administra almacenamiento, transporte, rotación o recuperación externa de claves.

No depende de fsresource-tree ni de ninguna aplicación. Una aplicación puede combinar ambas librerías; fscryptography solo recibe rutas.

## Directorios
Las operaciones de directorio transforman exclusivamente su nombre. Nunca recorren, cifran ni descifran su contenido.

## Tipos de recurso
El alcance inicial contempla archivos regulares y directorios. Enlaces simbólicos, enlaces duros, dispositivos, sockets, FIFOs y puntos de montaje requieren política explícita. No se deben seguir enlaces implícitamente.

## Metadatos visibles
Cifrar nombres no oculta cantidad de recursos, jerarquía, tamaños, timestamps, permisos, propietarios ni patrones de acceso.
