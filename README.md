# wuolah-wout-ads

Limpiador local y por lotes para PDFs descargados de Wuolah. Usa PyMuPDF para inspeccionar texto, enlaces y rectángulos de imagen del propio PDF. No envía documentos a servicios externos, no usa OCR ni llama a modelos. El procesamiento consume **cero tokens de IA**; el asistente solo necesita ejecutar un comando.

## Instalar

Requiere Python 3.10 o posterior.

```bash
python -m pip install .
wuolah-wout-ads apuntes.pdf
wuolah-wout-ads ./apuntes -o ./apuntes_limpios -j 4
```

Las carpetas se recorren recursivamente, conservando su estructura relativa, también con extensiones `.PDF` en mayúsculas. Se procesan hasta cuatro PDFs a la vez por defecto. El original nunca se sobrescribe. Las salidas existentes se omiten, a menos que indiques `--force`. `--json` imprime un resumen compacto para automatización, incluyendo páginas y regiones retiradas.

## Claude Code, Codex y OpenCode

El repo incluye skills para Claude Code (`.claude/skills/`), Codex (`.agents/skills/`) y OpenCode (`.opencode/skills/`), además de una copia canónica en `skills/wuolah-wout-ads/`. La instrucción del agente evita cargar texto del documento en el prompt: invoca el binario y resume el JSON. Instala primero el paquete en el entorno disponible para el asistente.

```bash
wuolah-wout-ads ./descargas -o ./descargas_limpias --json
```

## Alcance

El detector identifica páginas promocionales dedicadas con texto explícito de Wuolah; anuncios enlazados a destinos publicitarios que Wuolah oculta tras `track.wlh.es`; y el patrón gráfico de banner superior más banda lateral vertical. Este patrón se observó, por ejemplo, en la portada y el índice de un documento de 59 páginas: los anuncios de pie enlazados se limpian sin quitar el aviso legal contiguo. Los enlaces de seguimiento invisibles se eliminan también.

El detector no usa OCR ni visión artificial. Un banner sin enlace reconocible y fuera del patrón de margen puede no detectarse. Las páginas escaneadas y los enlaces a `wuolah.com` se conservan. También se mantienen por defecto logos, marcas de agua, QR, avisos legales y contenido académico. `removed_regions` cuenta rectángulos publicitarios borrados; un valor de cero no garantiza que un PDF no tenga anuncios.

Si el PDF no contiene una página promocional reconocible, se genera una copia en la ruta destino.

## Desarrollo

```bash
python -m pip install -e .
wuolah-wout-ads --help
```

MIT. Consulta [LICENSE](LICENSE).
