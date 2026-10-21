#!/usr/bin/env python3
"""Replace the placeholder service with a safe Accessibility tree inspector prototype."""
from pathlib import Path

root = Path("android-source/coc-builder-assistant")
target = root / "app/src/main/java/com/example/cocbuilder/AutoAttackAccessibilityService.kt"
if not target.exists():
    raise SystemExit(f"ERROR: Accessibility service not found: {target}")

source = r'''package com.example.cocbuilder

import android.accessibilityservice.AccessibilityService
import android.graphics.PixelFormat
import android.graphics.Color
import android.graphics.Typeface
import android.view.Gravity
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/**
 * Prototype inspector: shows the foreground package and accessible text labels.
 * It does not take screenshots, identify troop icons, or automate game actions.
 */
class AutoAttackAccessibilityService : AccessibilityService() {
    private lateinit var windowManager: WindowManager
    private var panel: LinearLayout? = null
    private var status: TextView? = null
    private var details: TextView? = null
    private val targetGamePackage = "com.supercell.clashofclans"
    private var foregroundPackage = "Belum terdeteksi"

    override fun onServiceConnected() {
        super.onServiceConnected()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        showPanel()
        setStatus("Layanan aktif. Buka game, lalu tekan INSPEKSI UI.")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event ?: return
        val packageName = event.packageName?.toString() ?: return
        // Opening this helper or Android's capture-consent dialog changes the latest event.
        // Keep the game package separate so our own Activity is not mistaken for Clash of Clans.
        if (packageName == targetGamePackage) {
            foregroundPackage = packageName
            setStatus("CoC terdeteksi: $foregroundPackage")
        } else if (foregroundPackage == "Belum terdeteksi") {
            setStatus("Menunggu Clash of Clans… paket saat ini: $packageName")
        }
    }

    private fun setStatus(message: String) {
        status?.post { status?.text = message }
    }

    private fun inspectTree() {
        val root = rootInActiveWindow
        if (root == null) {
            details?.text = "Tidak ada pohon Accessibility yang dapat dibaca."
            return
        }
        val lines = mutableListOf<String>()
        fun visit(node: AccessibilityNodeInfo, depth: Int) {
            if (lines.size >= 80) return
            val label = listOfNotNull(
                node.text?.toString()?.takeIf { it.isNotBlank() },
                node.contentDescription?.toString()?.takeIf { it.isNotBlank() }
            ).distinct().joinToString(" — ")
            if (label.isNotBlank()) {
                lines.add("  ".repeat(depth.coerceAtMost(5)) + label)
            }
            for (i in 0 until node.childCount) {
                val child = node.getChild(i) ?: continue
                visit(child, depth + 1)
                child.recycle()
                if (lines.size >= 80) break
            }
        }
        visit(root, 0)
        root.recycle()
        details?.text = if (lines.isEmpty()) {
            "Paket: $foregroundPackage\nTidak ada teks/label yang dapat dibaca. Game mungkin memakai kanvas grafis; ini belum mengenali ikon pasukan."
        } else {
            "Paket: $foregroundPackage\n\n" + lines.joinToString("\n")
        }
    }

    private fun showPanel() {
        if (panel != null) return
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(16, 12, 16, 12)
            setBackgroundColor(Color.argb(242, 25, 29, 38))
        }
        val heading = TextView(this).apply {
            text = "CoC Builder • Inspector"
            setTextColor(Color.WHITE)
            textSize = 16f
            typeface = Typeface.DEFAULT_BOLD
        }
        status = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 12f
            setPadding(0, 8, 0, 8)
        }
        val inspect = Button(this).apply {
            text = "INSPEKSI UI"
            setOnClickListener { inspectTree() }
        }
        val close = Button(this).apply {
            text = "TUTUP PANEL"
            setOnClickListener {
                panel?.let { try { windowManager.removeView(it) } catch (_: Exception) {} }
                panel = null
            }
        }
        details = TextView(this).apply {
            text = "Hasil inspeksi akan muncul di sini."
            setTextColor(Color.WHITE)
            textSize = 12f
            setPadding(0, 8, 0, 8)
        }
        val scroll = ScrollView(this).apply { addView(details) }
        root.addView(heading)
        root.addView(status)
        root.addView(inspect)
        root.addView(close)
        root.addView(scroll, LinearLayout.LayoutParams(420, 300))
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
            y = 100
        }
        try {
            windowManager.addView(root, params)
            panel = root
        } catch (e: Exception) {
            status?.text = "Gagal menampilkan panel: ${e.message}"
        }
    }

    override fun onInterrupt() {
        setStatus("Layanan terputus.")
    }

    override fun onDestroy() {
        panel?.let { try { windowManager.removeView(it) } catch (_: Exception) {} }
        panel = null
        super.onDestroy()
    }
}
'''
target.write_text(source, encoding="utf-8")
print("Accessibility inspector installed.")
