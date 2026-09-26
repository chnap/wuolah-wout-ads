---
name: wuolah-wout-ads
description: Limpia localmente páginas promocionales de PDFs Wuolah, de forma rápida y por lotes.
---

# Wuolah Wout Ads

Cuando el usuario pida limpiar PDFs de Wuolah, ejecuta `wuolah-wout-ads <PDF-o-carpeta> -o <destino> --json`. Usa una carpeta de salida distinta para no tocar originales. Para carpetas usa `-j 4` salvo que el usuario pida otro nivel de paralelismo. Resume el número de archivos procesados, páginas retiradas, omisiones y errores a partir del JSON. No leas ni pegues el contenido del PDF en el prompt: el proceso es local y no necesita IA. No afirmes que se retiraron anuncios gráficos o banners; la detección actual cubre páginas promocionales con texto explícito.
