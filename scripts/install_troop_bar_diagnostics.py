#!/usr/bin/env python3
"""Add conservative bottom HUD/ troop-bar candidate diagnostics to OCR frames."""
from pathlib import Path

app = Path("android-source/coc-builder-assistant/app")
service = app / "src/main/java/com/example/cocbuilder/ScreenCaptureForegroundService.kt"
if not service.exists():
    raise SystemExit(f"ERROR: screen capture service not found: {service}")
s = service.read_text(encoding="utf-8")

old = 'report("OCR: $screenState; resolusi ${w} × ${h}. Teks: ${if (recognized.isBlank()) "belum ada teks terbaca" else recognized}")'
new = 'val slotDiagnostics = analyzeBottomHud(bitmap)\n                                        report("OCR: $screenState; resolusi ${w} × ${h}. Teks: ${if (recognized.isBlank()) "belum ada teks terbaca" else recognized}. $slotDiagnostics")'
if "analyzeBottomHud(bitmap)" not in s:
    if old not in s:
        raise SystemExit("ERROR: OCR report insertion point not found; no changes made")
    s = s.replace(old, new, 1)

marker = "    private fun bitmapFromImage("
helper = r'''    /**
     * Conservative visual diagnostics for the lower HUD. It reports only candidate
     * vertical boundaries; it does not claim to identify troop types or quantities.
     */
    private fun analyzeBottomHud(bitmap: Bitmap): String {
        return try {
            val width = bitmap.width
            val height = bitmap.height
            if (width < 20 || height < 20) return "Analisis bar pasukan: gambar terlalu kecil."
            val yStart = (height * 0.76f).toInt().coerceIn(0, height - 1)
            val yEnd = (height * 0.97f).toInt().coerceIn(yStart + 1, height)
            val stepY = ((yEnd - yStart) / 18).coerceAtLeast(1)
            val score = FloatArray(width)
            for (x in 1 until width) {
                var sum = 0L
                var samples = 0
                var y = yStart
                while (y < yEnd) {
                    val a = bitmap.getPixel(x - 1, y)
                    val b = bitmap.getPixel(x, y)
                    val dr = kotlin.math.abs(android.graphics.Color.red(a) - android.graphics.Color.red(b))
                    val dg = kotlin.math.abs(android.graphics.Color.green(a) - android.graphics.Color.green(b))
                    val db = kotlin.math.abs(android.graphics.Color.blue(a) - android.graphics.Color.blue(b))
                    sum += (dr + dg + db).toLong()
                    samples++
                    y += stepY
                }
                score[x] = if (samples > 0) sum.toFloat() / samples else 0f
            }
            val window = (width / 180).coerceAtLeast(2)
            val smoothed = FloatArray(width)
            for (x in 1 until width - 1) {
                var sum = 0f
                var n = 0
                for (j in (x - window).coerceAtLeast(1)..(x + window).coerceAtMost(width - 1)) {
                    sum += score[j]
                    n++
                }
                smoothed[x] = if (n > 0) sum / n else 0f
            }
            val candidates = mutableListOf<Pair<Int, Float>>()
            for (x in window + 1 until width - window - 1) {
                val v = smoothed[x]
                if (v >= 28f && v >= smoothed[x - 1] && v >= smoothed[x + 1]) {
                    if (candidates.lastOrNull()?.first?.let { x - it < window * 3 } == true) {
                        if (v > candidates.last().second) candidates[candidates.lastIndex] = x to v
                    } else {
                        candidates.add(x to v)
                    }
                }
            }
            val strongest = candidates.sortedByDescending { it.second }.take(12).sortedBy { it.first }
            if (strongest.isEmpty()) {
                "Analisis bar pasukan: batas slot belum terdeteksi jelas; ikon/jumlah belum diklasifikasikan."
            } else {
                val positions = strongest.joinToString(", ") { (x, _) -> "${(x * 100 / width)}%" }
                "Analisis bar bawah: ${strongest.size} batas visual kandidat pada posisi layar ${positions}; ini perkiraan, bukan identifikasi pasukan/jumlah."
            }
        } catch (e: Exception) {
            "Analisis bar pasukan gagal: ${e.javaClass.simpleName}."
        }
    }

'''
if "private fun analyzeBottomHud" not in s:
    if marker not in s:
        raise SystemExit("ERROR: bitmap helper insertion point not found")
    s = s.replace(marker, helper + marker, 1)
service.write_text(s, encoding="utf-8")
print("Added conservative troop-bar boundary diagnostics.")
