#!/usr/bin/env python3
"""Add an explicit, one-shot Android screen-capture permission test."""
from pathlib import Path
import re

root = Path("android-source/coc-builder-assistant")
app = root / "app"
java_root = app / "src/main/java/com/example/cocbuilder"
service = java_root / "AutoAttackAccessibilityService.kt"
if not service.exists():
    raise SystemExit(f"ERROR: service not found: {service}")

activity = java_root / "ScreenCaptureTestActivity.kt"
activity.write_text(r'''package com.example.cocbuilder

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.ImageReader
import android.media.projection.MediaProjectionManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.TextView
import android.view.Gravity
import android.graphics.Color
import android.view.WindowManager
import android.media.projection.MediaProjection
import android.hardware.display.VirtualDisplay

/**
 * One-shot permission and capture validation. Does not store or upload the screen image,
 * recognize troops, or perform game actions. Android shows its own consent dialog.
 */
class ScreenCaptureTestActivity : Activity() {
    private val requestCode = 7412
    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var resultView: TextView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        resultView = TextView(this).apply {
            text = "Meminta izin tangkapan layar Android…"
            textSize = 18f
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.rgb(30, 34, 42))
            setPadding(32, 32, 32, 32)
            gravity = Gravity.CENTER
        }
        setContentView(resultView)
        val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        startActivityForResult(manager.createScreenCaptureIntent(), requestCode)
    }

    @Deprecated("Uses Android's system screen-capture consent result")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != this.requestCode) return
        if (resultCode != RESULT_OK || data == null) {
            resultView?.text = "Izin ditolak. Tidak ada layar yang diambil."
            return
        }
        try {
            val metrics = resources.displayMetrics
            val width = metrics.widthPixels.coerceAtLeast(1)
            val height = metrics.heightPixels.coerceAtLeast(1)
            reader = ImageReader.newInstance(width, height, android.graphics.PixelFormat.RGBA_8888, 2)
            val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projection = manager.getMediaProjection(resultCode, data)
            projection?.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() {
                    cleanup()
                }
            }, Handler(Looper.getMainLooper()))
            display = projection?.createVirtualDisplay(
                "CoCBuilderCaptureTest", width, height, metrics.densityDpi,
                android.hardware.display.DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader?.surface, null, Handler(Looper.getMainLooper())
            )
            Handler(Looper.getMainLooper()).postDelayed({
                val image = try { reader?.acquireLatestImage() } catch (_: Exception) { null }
                if (image == null) {
                    resultView?.text = "Izin berhasil, tetapi frame belum terbaca. Coba ulangi saat game terbuka."
                } else {
                    val w = image.width
                    val h = image.height
                    image.close()
                    resultView?.text = "BERHASIL: tangkapan layar diterima. Resolusi: ${w} × ${h}.\n\nIni hanya tes pengambilan frame; pengenalan ikon pasukan belum diterapkan. Tekan kembali untuk menutup."
                }
                cleanup()
            }, 900)
        } catch (e: Exception) {
            resultView?.text = "Gagal mengambil frame: ${e.javaClass.simpleName}: ${e.message}"
            cleanup()
        }
    }

    private fun cleanup() {
        try { display?.release() } catch (_: Exception) {}
        display = null
        try { reader?.close() } catch (_: Exception) {}
        reader = null
        try { projection?.stop() } catch (_: Exception) {}
        projection = null
    }

    override fun onDestroy() {
        cleanup()
        super.onDestroy()
    }
}
''', encoding="utf-8")

manifest = app / "src/main/AndroidManifest.xml"
if not manifest.exists():
    candidates = list(app.glob("src/*/AndroidManifest.xml"))
    if not candidates:
        raise SystemExit("ERROR: AndroidManifest.xml not found")
    manifest = candidates[0]
xml = manifest.read_text(encoding="utf-8")
if "ScreenCaptureTestActivity" not in xml:
    activity_tag = '<activity android:name=".ScreenCaptureTestActivity" android:exported="false" />'
    xml = re.sub(r"</application>", f"    {activity_tag}\n</application>", xml, count=1)
    manifest.write_text(xml, encoding="utf-8")

src = service.read_text(encoding="utf-8")
if "import android.content.Intent" not in src:
    src = src.replace("package com.example.cocbuilder\n", "package com.example.cocbuilder\n\nimport android.content.Intent\n", 1)
if "TES SCREEN CAPTURE" not in src:
    marker = '''        val close = Button(this).apply {'''
    insertion = '''        val capture = Button(this).apply {
            text = "TES SCREEN CAPTURE"
            isEnabled = true
            isClickable = true
            minHeight = 52
            setOnClickListener {
                setStatus("Tombol tes ditekan. Membuka izin tangkapan layar…")
                try {
                    val intent = Intent(this@AutoAttackAccessibilityService, ScreenCaptureTestActivity::class.java)
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    startActivity(intent)
                } catch (e: Exception) {
                    setStatus("Gagal membuka tes: ${e.javaClass.simpleName}")
                }
            }
        }
'''
    if marker not in src:
        raise SystemExit("ERROR: could not find panel button insertion point")
    src = src.replace(marker, insertion + marker, 1)
    src = src.replace("        root.addView(inspect)\n", "        root.addView(inspect)\n        root.addView(capture)\n", 1)
    service.write_text(src, encoding="utf-8")

print("Installed one-shot screen-capture consent/frame test; no OCR or game automation.")
