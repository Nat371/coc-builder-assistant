#!/usr/bin/env python3
"""Inject the first Accessibility UI scaffold into the Android source tree."""
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path("android-source/coc-builder-assistant")
manifest = root / "app/src/main/AndroidManifest.xml"
java_root = root / "app/src/main/java/com/example/cocbuilder"
res_xml = root / "app/src/main/res/xml/accessibility_service_config.xml"

if not manifest.exists():
    raise SystemExit(f"ERROR: AndroidManifest.xml tidak ditemukan: {manifest}")

java_root.mkdir(parents=True, exist_ok=True)
res_xml.parent.mkdir(parents=True, exist_ok=True)

service = r'''package com.example.cocbuilder

import android.accessibilityservice.AccessibilityService
import android.graphics.PixelFormat
import android.graphics.Color
import android.graphics.Typeface
import android.view.Gravity
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Tahap 1: validasi Accessibility dan kontrol Start/Stop.
 * Belum melakukan pembacaan base atau tap otomatis di dalam game.
 */
class AutoAttackAccessibilityService : AccessibilityService() {
    private lateinit var windowManager: WindowManager
    private var panel: LinearLayout? = null
    private var status: TextView? = null
    private var running = false

    override fun onServiceConnected() {
        super.onServiceConnected()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        showPanel()
    }

    private fun showPanel() {
        if (panel != null) return
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(18, 14, 18, 14)
            setBackgroundColor(Color.argb(235, 28, 32, 40))
        }
        val heading = TextView(this).apply {
            text = "CoC Builder • Accessibility"
            setTextColor(Color.WHITE)
            textSize = 14f
            typeface = Typeface.DEFAULT_BOLD
        }
        status = TextView(this).apply {
            text = "Status: siap. Auto Attack belum aktif."
            setTextColor(Color.WHITE)
            textSize = 12f
            setPadding(0, 8, 0, 8)
        }
        val start = Button(this).apply {
            text = "START (uji kontrol)"
            setOnClickListener {
                running = true
                status?.text = "Mode uji aktif. Belum membaca layar atau menempatkan pasukan."
            }
        }
        val stop = Button(this).apply {
            text = "STOP"
            setOnClickListener {
                running = false
                status?.text = "Berhenti."
            }
        }
        root.addView(heading)
        root.addView(status)
        root.addView(start)
        root.addView(stop)
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.END
            x = 12
            y = 120
        }
        try {
            windowManager.addView(root, params)
            panel = root
        } catch (_: Exception) {
            panel = null
        }
    }

    private var lastEventReportAt = 0L

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        val now = android.os.SystemClock.elapsedRealtime()
        if (now - lastEventReportAt < 1200L) return

        val eventText = event.text
            .map { it.toString().trim() }
            .filter { it.isNotEmpty() }
            .distinct()
            .take(3)
            .joinToString(" | ")

        val packageLabel = event.packageName?.toString()?.substringAfterLast('.') ?: "layar"
        val detail = if (eventText.isNotBlank()) eventText.take(90) else "perubahan layar terdeteksi"
        status?.text = "${packageLabel}: ${detail}"
        lastEventReportAt = now
    }

    override fun onInterrupt() {
        running = false
        status?.text = "Terputus — berhenti."
    }

    override fun onDestroy() {
        running = false
        panel?.let {
            try { windowManager.removeView(it) } catch (_: Exception) {}
        }
        panel = null
        super.onDestroy()
    }
}
'''
(java_root / "AutoAttackAccessibilityService.kt").write_text(service, encoding="utf-8")

values_dir = root / "app/src/main/res/values"
values_dir.mkdir(parents=True, exist_ok=True)
strings_xml = values_dir / "strings.xml"
if not strings_xml.exists():
    strings_xml.write_text("""<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">CoC Builder Assistant</string>
</resources>
""", encoding="utf-8")

(res_xml).write_text('''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="100"
    android:canRetrieveWindowContent="true"
    android:canPerformGestures="true"
    android:description="@string/app_name" />
''', encoding="utf-8")

ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
tree = ET.parse(manifest)
manifest_el = tree.getroot()
application_el = manifest_el.find("application")
if application_el is None:
    raise SystemExit("ERROR: elemen <application> tidak ditemukan di AndroidManifest.xml")
ANDROID = "{http://schemas.android.com/apk/res/android}"
service_name = "com.example.cocbuilder.AutoAttackAccessibilityService"
exists = any(el.tag == "service" and el.get(ANDROID + "name") == service_name for el in application_el.iter())
if not exists:
    service_el = ET.SubElement(application_el, "service", {
        ANDROID + "name": service_name,
        ANDROID + "label": "CoC Builder Auto Attack (uji)",
        ANDROID + "permission": "android.permission.BIND_ACCESSIBILITY_SERVICE",
        ANDROID + "exported": "true",
    })
    ET.SubElement(service_el, "intent-filter")
    service_el[-1].append(ET.Element("action", {ANDROID + "name": "android.accessibilityservice.AccessibilityService"}))
    ET.SubElement(service_el, "meta-data", {
        ANDROID + "name": "android.accessibilityservice",
        ANDROID + "resource": "@xml/accessibility_service_config",
    })
tree.write(manifest, encoding="utf-8", xml_declaration=True)
print("Accessibility scaffold ditambahkan: panel Start/Stop uji. OCR dan tap otomatis belum diimplementasikan.")
