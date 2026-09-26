# wuolah-wout-ads

Limpiador local y por lotes para PDFs descargados de Wuolah. Usa PyMuPDF para inspeccionar el texto del propio PDF, sin enviar documentos a servicios externos, sin OCR y sin llamadas a modelos. El procesamiento consume **cero tokens de IA**; el asistente solo necesita ejecutar un comando.

## Instalar

Requiere Python 3.10 o posterior.

```bash
python -m pip install .
wuolah-wout-ads apuntes.pdf
wuolah-wout-ads ./apuntes -o ./apuntes_limpios -j 4
```

Las carpetas se recorren recursivamente, conservando su estructura relativa. Se procesan hasta cuatro PDFs a la vez por defecto. El original nunca se sobrescribe. Las salidas existentes se omiten, a menos que indiques `--force`. `--json` imprime un resumen compacto para automatización.

## Claude Code, Codex y OpenCode

El repo incluye skills para Claude Code (`.claude/skills/`), Codex (`skills/wuolah-wout-ads/`, copiable a la carpeta de skills del usuario) y OpenCode (`.opencode/skills/`). La instrucción de agente es corta: invoca el binario y resume el resultado sin cargar texto del documento en el prompt. Instala primero el paquete en el entorno disponible para el asistente.

```bash
wuolah-wout-ads ./descargas -o ./descargas_limpias --json
```

## Alcance

La versión inicial elimina páginas promocionales dedicadas cuando su texto incluye frases publicitarias explícitas de Wuolah. La detección es conservadora para evitar quitar menciones normales de los apuntes. No elimina banners gráficos mezclados con contenido, PDFs escaneados ni anuncios que carezcan de texto reconocible. Revisa el JSON y conserva los originales hasta confirmar el resultado.

Si el PDF no contiene una página promocional reconocible, se genera una copia en la ruta destino.

## Desarrollo

```bash
python -m pip install -e .
wuolah-wout-ads --help
```

MIT. Consulta [LICENSE](LICENSE).
