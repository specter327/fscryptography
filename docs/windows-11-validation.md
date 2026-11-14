# Validación manual en Windows 11

## Objetivo

Este procedimiento obtiene evidencia reproducible de integración de `fscryptography` en **Windows 11 cliente x86-64**, sobre NTFS y CPython 3.11, 3.12 y 3.13.

La matriz GitHub Actions actual usa `windows-latest`, que en las ejecuciones documentadas resolvió a Windows Server 2025. Esa evidencia no se debe etiquetar como Windows 11. Este procedimiento requiere una máquina Windows 11 real o una VM que ejecute Windows 11 cliente; no basta con cambiar el nombre del runner.

La ejecución no declara soporte por sí sola. Deben completarse todos los casos y conservarse los logs.

## Preparación

1. Usa una instalación actualizada de Windows 11 x86-64.
2. Usa un volumen NTFS local. No uses SMB, OneDrive sincronizado, unidad extraíble ni filesystem virtual.
3. Ejecuta desde una cuenta estándar, sin elevar PowerShell.
4. Crea un checkout limpio de la rama candidata de la PR #29.
5. Conserva backups; la suite de filesystem crea, renombra y elimina recursos de prueba.

Registra el commit exacto:

```powershell
git rev-parse HEAD
git status --short
```

El árbol de trabajo debe estar limpio.

## Captura del entorno

Ejecuta desde la raíz del repositorio y conserva la salida:

```powershell
New-Item -ItemType Directory -Force artifacts\windows-11-validation | Out-Null
Start-Transcript -Path artifacts\windows-11-validation\session.txt

Get-ComputerInfo |
  Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture |
  Format-List

[System.Environment]::OSVersion.Version
python --version
python -c "import platform, sys; print(sys.version); print(platform.platform()); print(platform.machine())"
git rev-parse HEAD
git status --short

$workspace = (Get-Location).Path
$drive = (Get-Item $workspace).PSDrive.Name
Get-Volume -DriveLetter $drive |
  Select-Object DriveLetter, FileSystem, FileSystemLabel, AllocationUnitSize |
  Format-List
```

El resultado debe identificar Windows 11 (no Windows Server), arquitectura x64 y NTFS.

## Matriz Python

Repite el procedimiento en entornos virtuales separados para CPython 3.11, 3.12 y 3.13. Usa intérpretes oficiales x64.

Ejemplo para cada intérprete (ajusta el launcher si no está disponible):

```powershell
py -3.11 -m venv .venv-win311
.\.venv-win311\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest -q -s tests/real_resources
python -m pytest -q tests
python -m pip freeze
deactivate
```

Cambia `-3.11` y el nombre del entorno por `-3.12` / `.venv-win312` y `-3.13` / `.venv-win313`. No reutilices el mismo entorno virtual entre versiones.

La suite de filesystem `tests/real_resources` es obligatoria. Si no existe en el commit evaluado, no la sustituyas silenciosamente: ejecuta `python -m pytest --collect-only -q` y registra la estructura real y el motivo.

## Casos manuales complementarios

Además de las suites automatizadas, ejecuta en un directorio temporal NTFS:

- Round-trip de archivo vacío, archivo pequeño, archivo mayor que varios segmentos de 1 MiB y nombre Unicode.
- Round-trip de nombre cifrado con componentes cercanos al límite admitido.
- Colisión con destino existente: confirmar que no se sobrescribe.
- Archivo abierto por otro proceso: registrar el error y verificar el estado de origen/destino.
- Permisos insuficientes bajo una cuenta estándar.
- Nombres reservados de Windows, caracteres no permitidos y trailing dot/space: confirmar rechazo controlado antes de modificar el origen.
- Symlink y reparse point: confirmar rechazo conforme al contrato.
- Errores inducidos solo en fixtures desechables: verificar que no se publica plaintext parcial y documentar cualquier temporal residual. No simules pérdida de energía en un equipo con datos reales.

Para cada caso registra el resultado esperado y observado, excepción exacta, estado de origen/destino y archivos residuales. No incluyas claves, contraseñas ni contenido sensible en los logs.

## Criterios de aceptación

- Los tres intérpretes pasan las suites de filesystem real y el resto de tests.
- No hay fallos, skips inesperados ni errores de entorno sin explicar.
- El entorno queda identificado como Windows 11 cliente, build exacto, NTFS y x86-64.
- Los errores inducidos no destruyen el original ni publican plaintext parcial.
- Las colisiones no sobrescriben destinos existentes.
- Cada fallo se reproduce o se clasifica como incidencia del entorno con evidencia.

Un fallo bloquea la declaración de soporte hasta corregirlo o documentar una exclusión técnicamente justificada.

## Artefactos y reporte

Guarda por versión de Python la transcripción, salida de pytest/código de salida, `pip freeze`, commit SHA, estado Git, build de Windows, arquitectura y tipo de filesystem.

Al finalizar:

```powershell
Stop-Transcript
```

Publica un resumen sin secretos en la pull request que proponga el cambio o la versión evaluada, o conserva el reporte como artefacto de validación asociado al commit. Incluye dispositivo/VM, build, NTFS, versiones Python, SHA, conteo de pruebas, skips y fallos. Adjunta logs sanitizados si contienen rutas o información del equipo.

## Resultado actual

- [ ] Windows 11 cliente x64 identificado.
- [ ] CPython 3.11: filesystem y suite completa aprobados.
- [ ] CPython 3.12: filesystem y suite completa aprobados.
- [ ] CPython 3.13: filesystem y suite completa aprobados.
- [ ] Casos manuales complementarios aprobados.
- [ ] Evidencias revisadas y resumen añadido a la PR.

La matriz CI Windows Server 2025 / NTFS permanece como evidencia separada y no marca ninguna casilla de Windows 11.
