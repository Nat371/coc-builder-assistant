#!/usr/bin/env python3
"""Install on-device ML Kit text recognition for captured Android frames."""
from pathlib import Path
import re

root = Path("android-source/coc-builder-assistant/app")
gradle = next((p for p in (root / "build.gradle.kts", root / "build.gradle") if p.exists()), None)
if gradle is None:
    raise SystemExit("ERROR: app/build.gradle(.kts) tidak ditemukan")

g = gradle.read_text(encoding="utf-8")
dependency = 'implementation("com.google.mlkit:text-recognition:16.0.1")' if gradle.suffix == ".kts" else "implementation 'com.google.mlkit:text-recognition:16.0.1'"
if "com.google.mlkit:text-recognition" not in g:
    match = re.search(r"dependencies\\s*\\{", g)
    if not match:
        raise SystemExit("ERROR: blok dependencies tidak ditemukan")
    g = g[:match.end()] + "\\n    " + dependency + g[match.end():]
    gradle.write_text(g, encoding="utf-8")

service = root / "src/main/java/com/example/cocbuilder/ScreenCaptureForegroundService.kt"
if not service.exists():
    raise SystemExit(f"ERROR: service tidak ditemukan: {service}")
s = service.read_text(encoding="utf-8")
imports = """import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
"""
if "com.google.mlkit.vision.text.TextRecognition" not in s:
    s = s.replace("import android.graphics.PixelFormat\\n", "import android.graphics.PixelFormat\\n" + imports, 1)

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
                                val input = InputImage.fromBitmap(bitmap, 0)
                                TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
                                    .process(input)
                                    .addOnSuccessListener { result ->
                                        val recognized = result.text.trim().replace(Regex("\\s+"), " ").take(350)
                                        val label = if (recognized.isBlank()) "belum ada teks terbaca" else recognized
                                        report("OCR berhasil diproses; resolusi ${w} × ${h}. Teks: ${label}")
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
    raise SystemExit("ERROR: blok capture yang diharapkan tidak ditemukan; file tidak diubah")

marker = """    // Sample pixels directly from the RGBA frame to verify that image content is readable."""
helper = """    // Convert the RGBA ImageReader frame to a bitmap while respecting row/pixel stride.
    private fun bitmapFromImage(image: android.media.Image): Bitmap? {
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
        raise SystemExit("ERROR: marker helper tidak ditemukan")
    s = s.replace(marker, helper + marker, 1)
service.write_text(s, encoding="utf-8")
print("ML Kit OCR dipasang pada frame tangkapan layar.")
