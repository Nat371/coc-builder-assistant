#!/usr/bin/env python3
"""Route MediaProjection capture through an Android 14 mediaProjection foreground service."""
from pathlib import Path
import re

app = Path("android-source/coc-builder-assistant/app")
java_root = app / "src/main/java/com/example/cocbuilder"
activity = java_root / "ScreenCaptureTestActivity.kt"
manifest = app / "src/main/AndroidManifest.xml"
if not activity.exists() or not manifest.exists():
    raise SystemExit("ERROR: capture activity or AndroidManifest.xml not found")

src = activity.read_text(encoding="utf-8")
start = src.find("        try {\n            val metrics = resources.displayMetrics", src.find("override fun onActivityResult"))
end_marker = "            cleanup()\n        }\n    }"
end = src.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("ERROR: could not locate capture block to replace")
end += len("            cleanup()\n        }")
replacement = """        try {
            val serviceIntent = Intent(this, ScreenCaptureForegroundService::class.java).apply {
                putExtra(ScreenCaptureForegroundService.EXTRA_RESULT_CODE, resultCode)
                putExtra(ScreenCaptureForegroundService.EXTRA_RESULT_DATA, data)
            }
            if (android.os.Build.VERSION.SDK_INT >= 26) {
                startForegroundService(serviceIntent)
            } else {
                startService(serviceIntent)
            }
            resultView?.text = "Izin diterima. Layanan tangkapan layar sedang berjalan. Periksa notifikasi untuk hasil tes."
        } catch (e: Exception) {
            resultView?.text = "Gagal memulai layanan tangkapan layar: ${e.javaClass.simpleName}: ${e.message}"
        }"""
src = src[:start] + replacement + src[end:]
# Remove activity-side projection cleanup fields/imports, which are no longer used for capture.
src = src.replace("    private var projection: MediaProjection? = null\n", "")
src = src.replace("    private var display: VirtualDisplay? = null\n", "")
src = src.replace("    private var reader: ImageReader? = null\n", "")
src = src.replace("        try { display?.release() } catch (_: Exception) {}\n        display = null\n        try { reader?.close() } catch (_: Exception) {}\n        reader = null\n        try { projection?.stop() } catch (_: Exception) {}\n        projection = null\n", "")
activity.write_text(src, encoding="utf-8")

service = java_root / "ScreenCaptureForegroundService.kt"
service.write_text(r'''package com.example.cocbuilder

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.DisplayMetrics
import android.view.WindowManager
import android.content.pm.ServiceInfo

/** One-shot capture test. Frames are read only to validate capture and are never saved or uploaded. */
class ScreenCaptureForegroundService : Service() {
    companion object {
        const val EXTRA_RESULT_CODE = "projection_result_code"
        const val EXTRA_RESULT_DATA = "projection_result_data"
        private const val CHANNEL_ID = "coc_capture_test"
        private const val NOTIFICATION_ID = 7413
    }

    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        createNotificationChannel()
        val initial = notification("Sedang menguji tangkapan layar…")
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, initial, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, initial)
        }

        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val data = if (Build.VERSION.SDK_INT >= 33) {
            intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        if (resultCode == 0 || data == null) {
            finishWith("Gagal: data izin tangkapan layar tidak tersedia")
            return START_NOT_STICKY
        }

        try {
            val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projection = manager.getMediaProjection(resultCode, data)
            projection?.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() {
                    cleanup()
                    stopSelf()
                }
            }, Handler(Looper.getMainLooper()))

            val metrics = DisplayMetrics()
            @Suppress("DEPRECATION")
            val wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
            @Suppress("DEPRECATION")
            wm.defaultDisplay.getRealMetrics(metrics)
            val width = metrics.widthPixels.coerceAtLeast(1)
            val height = metrics.heightPixels.coerceAtLeast(1)
            reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
            display = projection?.createVirtualDisplay(
                "CoCBuilderCaptureTest", width, height, metrics.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader?.surface, null, Handler(Looper.getMainLooper())
            )
            Handler(Looper.getMainLooper()).postDelayed({
                val image = try { reader?.acquireLatestImage() } catch (_: Exception) { null }
                if (image == null) {
                    finishWith("Izin aktif, tetapi frame belum terbaca. Coba lagi saat game terbuka.")
                } else {
                    val w = image.width
                    val h = image.height
                    image.close()
                    finishWith("BERHASIL: frame diterima, resolusi ${w} × ${h}. Gambar tidak disimpan.")
                }
            }, 1200)
        } catch (e: Exception) {
            finishWith("Gagal mengambil frame: ${e.javaClass.simpleName}: ${e.message}")
        }
        return START_NOT_STICKY
    }

    private fun finishWith(message: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, notification(message))
        Handler(Looper.getMainLooper()).postDelayed({
            cleanup()
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        }, 4500)
    }

    private fun notification(message: String): Notification {
        return if (Build.VERSION.SDK_INT >= 26) {
            Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setContentTitle("CoC Builder Assistant")
                .setContentText(message)
                .setStyle(Notification.BigTextStyle().bigText(message))
                .setOngoing(message.startsWith("Sedang"))
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setContentTitle("CoC Builder Assistant")
                .setContentText(message)
                .build()
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel(CHANNEL_ID, "Tes tangkapan layar", NotificationManager.IMPORTANCE_LOW)
            (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(channel)
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

xml = manifest.read_text(encoding="utf-8")
permissions = []
if "android.permission.FOREGROUND_SERVICE" not in xml:
    permissions.append('    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />')
if "android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION" not in xml:
    permissions.append('    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION" />')
if permissions:
    xml = re.sub(r"(<manifest[^>]*>)", r"\1\n" + "\n".join(permissions), xml, count=1)
if "ScreenCaptureForegroundService" not in xml:
    service_tag = '        <service android:name=".ScreenCaptureForegroundService" android:exported="false" android:foregroundServiceType="mediaProjection" />'
    xml = re.sub(r"</application>", service_tag + "\n</application>", xml, count=1)
manifest.write_text(xml, encoding="utf-8")
print("Patched MediaProjection to use a foreground service for Android 14.")
