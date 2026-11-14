# Prueba de integración: 100 archivos

El repositorio incluye `scripts/100_files_roundtrip.py`, una demostración de extremo a extremo para verificar la transformación de archivos mediante la API pública de `fscryptography`.

## Qué comprueba

1. Crea 10 directorios y 100 archivos desechables con extensiones variadas.
2. Genera contenido de texto y contenido binario con firmas de formato representativas.
3. Calcula SHA-256 de cada archivo original.
4. Genera una MasterKey aleatoria, mantenida únicamente en memoria.
5. Cifra cada archivo mediante `Manager.file.encrypt()`.
6. Comprueba que el origen desapareció y que se publicó el destino `.fscrypt`.
7. Descifra cada ciphertext mediante `Manager.file.decrypt()`.
8. Verifica que el ciphertext fue retirado y que el archivo original fue restaurado.
9. Compara SHA-256 para comprobar la identidad exacta del contenido recuperado.
10. Falla inmediatamente si encuentra una discrepancia o una transformación incompleta.

Los archivos se generan localmente; la prueba no necesita acceso a Internet. Los archivos binarios son fixtures sintéticos, no documentos multimedia completos. El objetivo es probar que la API procesa bytes arbitrarios sin depender de la extensión.

## Ejecución

Desde la raíz del repositorio, con el paquete y sus dependencias instalados:

```bash
python scripts/100_files_roundtrip.py
```

Opciones:

```bash
# Generar y verificar 250 archivos.
python scripts/100_files_roundtrip.py --count 250

# Conservar el workspace para inspeccionar los archivos restaurados.
python scripts/100_files_roundtrip.py --keep-workspace

# Elegir un directorio de trabajo que no exista o esté vacío.
python scripts/100_files_roundtrip.py --workspace ./tmp/fscryptography-roundtrip

# Reproducir los fixtures de texto con otra semilla.
python scripts/100_files_roundtrip.py --seed 12345
```

Sin `--keep-workspace` ni `--workspace`, la prueba crea un directorio temporal aislado y lo elimina después de un resultado correcto. Si la prueba falla, conserva el directorio temporal e imprime su ruta para facilitar el diagnóstico.

## Resultado esperado

Al terminar correctamente, el resumen debe indicar:

- 100 archivos generados.
- 100 archivos cifrados.
- 100 archivos descifrados.
- 100/100 hashes SHA-256 coincidentes.
- 0 ciphertexts pendientes.
- Estado `PASS`.

La salida también muestra una línea por transformación, con nombre de origen, nombre de destino, tamaño y prefijo del SHA-256. No imprime la MasterKey ni el contenido de los archivos.

## Integración continua

El workflow `.github/workflows/backend-validation.yml` ejecuta esta prueba en el job de pruebas unitarias de Linux, después de instalar el paquete en modo editable y ejecutar las pruebas unitarias y de formato. El script usa la misma API pública documentada; no importa módulos privados de implementación.

## Alcance

Esta prueba valida un round-trip secuencial de archivos regulares en el filesystem del runner. No constituye una auditoría criptográfica, una prueba de recuperación ante pérdida de energía, una prueba de concurrencia ni una validación de todos los filesystems y plataformas soportados. Los nombres de directorios se crean para organizar los fixtures; la API de directorios no se usa para cifrar recursivamente el árbol.
