#!/usr/bin/env python3
"""Add ML Kit text recognition to the existing screen-capture service."""
from pathlib import Path

app = Path("android-source/coc-builder-assistant/app")
gradle = next((p for p in (app / "build.gradle.kts", app / "build.gradle") if p.exists()), None)
if gradle is None:
    raise SystemExit("ERROR: app Gradle file not found")
g = gradle.read_text(encoding="utf-8")
if "com.google.mlkit:text-recognition" not in g:
    marker = "dependencies {"
    pos = g.find(marker)
    if pos < 0:
        raise SystemExit("ERROR: dependencies block not found")
    dependency = '    implementation("com.google.mlkit:text-recognition:16.0.1")\n' if gradle.suffix == ".kts" else "    implementation 'com.google.mlkit:text-recognition:16.0.1'\n"
    g = g[:pos + len(marker)] + "\n" + dependency + g[pos + len(marker):]
    gradle.write_text(g, encoding="utf-8")

p = app / "src/main/java/com/example/cocbuilder/ScreenCaptureForegroundService.kt"
s = p.read_text(encoding="utf-8")
if "com.google.mlkit.vision.text.TextRecognition" not in s:
    s = s.replace("import android.graphics.PixelFormat\n", "import android.graphics.PixelFormat\nimport android.graphics.Bitmap\nimport com.google.mlkit.vision.common.InputImage\nimport com.google.mlkit.vision.text.TextRecognition\nimport com.google.mlkit.vision.text.latin.TextRecognizerOptions\n", 1)

old = """                        val w = image.width
                        val h = image.height
                        val brightness = try { averageLuminancePercent(image) } catch (_: Exception) { null }
                        image.close()
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (now - lastReportAt >= 5000L) {
                            val visualInfo = brightness?.let { " Kecerahan rata-rata sampel: ${it}%." } ?: ""
                            report("SESI AKTIF: frame diproses, resolusi ${w} × ${h}.${visualInfo} Ini diagnostik visual dasar, belum mengenali pasukan atau markas.")
                            lastReportAt = now
                        }"""
new = """                        val w = image.width
                        val h = image.height
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (now - lastReportAt >= 5000L) {
                            lastReportAt = now
                            val bitmap = try { bitmapFromImage(image) } catch (_: Exception) { null }
                            image.close()
                            if (bitmap == null) {
                                report("Frame diterima (${w} × ${h}), tetapi konversi gambar untuk OCR gagal.")
                            } else {
                                TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
                                    .process(InputImage.fromBitmap(bitmap, 0))
                                    .addOnSuccessListener { result ->
                                        val recognized = result.text.trim().replace(Regex("\\\\s+"), " ").take(350)
                                        report("OCR berhasil diproses; resolusi ${w} × ${h}. Teks: ${if (recognized.isBlank()) "belum ada teks terbaca" else recognized}")
                                        bitmap.recycle()
                                    }
                                    .addOnFailureListener { error ->
                                        report("OCR gagal: ${error.javaClass.simpleName}: ${error.message ?: "tanpa detail"}")
                                        bitmap.recycle()
                                    }
                            }
                        } else {
                            image.close()
                        }"""
if old in s:
    s = s.replace(old, new, 1)
elif "TextRecognition.getClient" not in s:
    raise SystemExit("ERROR: capture-loop block not found; service not changed")

marker = "    // Sample pixels directly from the RGBA frame to verify that image content is readable."
helper = """    private fun bitmapFromImage(image: android.media.Image): Bitmap? {
        val plane = image.planes.firstOrNull() ?: return null
        val buffer = plane.buffer.duplicate()
        val width = image.width
        val height = image.height
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        if (pixelStride < 4 || rowStride <= 0) return null
        val pixels = IntArray(width * height)
        for (y in 0 until height) {
            val rowBase = y * rowStride
            for (x in 0 until width) {
                val offset = rowBase + x * pixelStride
                if (offset + 3 >= buffer.limit()) continue
                val red = buffer.get(offset).toInt() and 0xff
                val green = buffer.get(offset + 1).toInt() and 0xff
                val blue = buffer.get(offset + 2).toInt() and 0xff
                val alpha = buffer.get(offset + 3).toInt() and 0xff
                pixels[y * width + x] = (alpha shl 24) or (red shl 16) or (green shl 8) or blue
            }
        }
        return Bitmap.createBitmap(pixels, width, height, Bitmap.Config.ARGB_8888)
    }

"""
if "private fun bitmapFromImage" not in s:
    if marker not in s:
        raise SystemExit("ERROR: bitmap helper insertion point not found")
    s = s.replace(marker, helper + marker, 1)
p.write_text(s, encoding="utf-8")
print("ML Kit OCR integration installed.")
