#!/usr/bin/env python3
"""Use a mediaProjection foreground service for Android 14 screen capture."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

root = Path("android-source/coc-builder-assistant")
app = root / "app"
java_root = app / "src/main/java/com/example/cocbuilder"
manifest = app / "src/main/AndroidManifest.xml"
if not manifest.exists():
    raise SystemExit("ERROR: AndroidManifest.xml tidak ditemukan")

service_file = java_root / "ScreenCaptureForegroundService.kt"
service_file.write_text(r'''package com.example.cocbuilder

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

class ScreenCaptureForegroundService : Service() {
    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private val handler = Handler(Looper.getMainLooper())

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        createNotificationChannel()
        val notification = if (Build.VERSION.SDK_INT >= 26) {
            Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("CoC Builder Assistant")
                .setContentText("Tes tangkapan layar sedang berjalan")
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setOngoing(true)
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setContentTitle("CoC Builder Assistant")
                .setContentText("Tes tangkapan layar sedang berjalan")
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .build()
        }
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(NOTIFICATION_ID, notification, android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }

        val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, 0) ?: 0
        val data = if (Build.VERSION.SDK_INT >= 33) {
            intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent?.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        if (resultCode == 0 || data == null) {
            report("Gagal: data izin tangkapan layar tidak diterima service.")
            stopSelf()
            return START_NOT_STICKY
        }

        try {
            val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projection = manager.getMediaProjection(resultCode, data)
            val metrics = resources.displayMetrics
            val width = metrics.widthPixels.coerceAtLeast(1)
            val height = metrics.heightPixels.coerceAtLeast(1)
            reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
            projection?.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() {
                    cleanup()
                    stopSelf()
                }
            }, handler)
            display = projection?.createVirtualDisplay(
                "CoCBuilderCaptureTest", width, height, metrics.densityDpi,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader?.surface, null, handler
            )
            // Keep this single user-approved projection session alive until Android/user stops it.
            var lastReportAt = 0L
            val captureLoop = object : Runnable {
                override fun run() {
                    if (projection == null || reader == null) return
                    val image = try { reader?.acquireLatestImage() } catch (_: Exception) { null }
                    if (image != null) {
                        val w = image.width
                        val h = image.height
                        image.close()
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (now - lastReportAt >= 5000L) {
                            report("SESI AKTIF: frame diterima, resolusi ${w} × ${h}. Izin tidak perlu diminta ulang selama layanan ini tetap aktif.")
                            lastReportAt = now
                        }
                    } else {
                        val now = android.os.SystemClock.elapsedRealtime()
                        if (now - lastReportAt >= 5000L) {
                            report("Sesi perekaman aktif, menunggu frame layar…")
                            lastReportAt = now
                        }
                    }
                    handler.postDelayed(this, 500)
                }
            }
            handler.post(captureLoop)
        } catch (e: Exception) {
            report("Gagal mengambil frame: ${e.javaClass.simpleName}: ${e.message}")
            cleanup()
            stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun report(message: String) {
        val result = Intent(ACTION_RESULT).setPackage(packageName).putExtra(EXTRA_MESSAGE, message)
        sendBroadcast(result)
        // Reflect real capture-loop status in the persistent notification as well.
        val notification = if (Build.VERSION.SDK_INT >= 26) {
            Notification.Builder(this, CHANNEL_ID)
                .setContentTitle("CoC Builder Assistant")
                .setContentText(message.take(120))
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setOngoing(true)
                .build()
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
                .setContentTitle("CoC Builder Assistant")
                .setContentText(message.take(120))
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setOngoing(true)
                .build()
        }
        (getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager)
            .notify(NOTIFICATION_ID, notification)
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

    companion object {
        const val ACTION_RESULT = "com.example.cocbuilder.SCREEN_CAPTURE_RESULT"
        const val EXTRA_MESSAGE = "message"
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        private const val CHANNEL_ID = "coc_capture_test"
        private const val NOTIFICATION_ID = 7413
    }
}
''', encoding="utf-8")

activity_file = java_root / "ScreenCaptureTestActivity.kt"
activity_file.write_text(r'''package com.example.cocbuilder

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.graphics.Color
import android.widget.TextView

class ScreenCaptureTestActivity : Activity() {
    private val requestCode = 7412
    private var resultView: TextView? = null
    private val resultReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            resultView?.text = intent?.getStringExtra(ScreenCaptureForegroundService.EXTRA_MESSAGE) ?: "Tes selesai."
        }
    }

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
        val filter = IntentFilter(ScreenCaptureForegroundService.ACTION_RESULT)
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(resultReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        else @Suppress("DEPRECATION") run { registerReceiver(resultReceiver, filter) }
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
        val serviceIntent = Intent(this, ScreenCaptureForegroundService::class.java).apply {
            putExtra(ScreenCaptureForegroundService.EXTRA_RESULT_CODE, resultCode)
            putExtra(ScreenCaptureForegroundService.EXTRA_RESULT_DATA, data)
        }
        try {
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(serviceIntent) else startService(serviceIntent)
            resultView?.text = "Foreground service aktif. Sedang menguji frame…"
        } catch (e: Exception) {
            resultView?.text = "Gagal menjalankan foreground service: ${e.javaClass.simpleName}: ${e.message}"
        }
    }

    override fun onDestroy() {
        try { unregisterReceiver(resultReceiver) } catch (_: Exception) {}
        super.onDestroy()
    }
}
''', encoding="utf-8")

ANDROID = "{http://schemas.android.com/apk/res/android}"
ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
tree = ET.parse(manifest)
m = tree.getroot()
app_el = m.find("application")
if app_el is None:
    raise SystemExit("ERROR: elemen application tidak ditemukan")
permissions = {p.get(ANDROID + "name") for p in m.findall("uses-permission")}
for permission in ("android.permission.FOREGROUND_SERVICE", "android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION"):
    if permission not in permissions:
        ET.SubElement(m, "uses-permission", {ANDROID + "name": permission})
def ensure_service(name, attrs):
    found = next((s for s in app_el.findall("service") if s.get(ANDROID + "name") == name), None)
    if found is None:
        found = ET.SubElement(app_el, "service", attrs)
    else:
        for k,v in attrs.items(): found.set(k,v)
ensure_service(".ScreenCaptureForegroundService", {
    ANDROID + "name": ".ScreenCaptureForegroundService",
    ANDROID + "exported": "false",
    ANDROID + "foregroundServiceType": "mediaProjection",
})
# Ensure capture activity remains declared.
if not any(a.get(ANDROID + "name") == ".ScreenCaptureTestActivity" for a in app_el.findall("activity")):
    ET.SubElement(app_el, "activity", {ANDROID + "name": ".ScreenCaptureTestActivity", ANDROID + "exported": "false"})
tree.write(manifest, encoding="utf-8", xml_declaration=True)
print("MediaProjection foreground service installed and manifest permissions registered.")
