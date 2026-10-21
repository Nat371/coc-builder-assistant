#!/usr/bin/env python3
"""Ensure the Accessibility service is declared in the final Android manifest."""
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path("android-source/coc-builder-assistant")
manifest = root / "app/src/main/AndroidManifest.xml"
config = root / "app/src/main/res/xml/accessibility_service_config.xml"
strings = root / "app/src/main/res/values/strings.xml"
if not manifest.exists():
    raise SystemExit(f"ERROR: AndroidManifest.xml tidak ditemukan: {manifest}")

ANDROID = "{http://schemas.android.com/apk/res/android}"
ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
tree = ET.parse(manifest)
m = tree.getroot()
app = m.find("application")
if app is None:
    raise SystemExit("ERROR: elemen application tidak ditemukan")

# Ensure app label is a valid resource.
strings.parent.mkdir(parents=True, exist_ok=True)
if not strings.exists():
    strings.write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources><string name="app_name">CoC Builder Assistant</string></resources>\n', encoding="utf-8")

config.parent.mkdir(parents=True, exist_ok=True)
config.write_text('''<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="100"
    android:canRetrieveWindowContent="true"
    android:canPerformGestures="true"
    android:description="@string/app_name" />
''', encoding="utf-8")

service_name = "com.example.cocbuilder.AutoAttackAccessibilityService"
services = [e for e in app.findall("service") if e.get(ANDROID + "name") == service_name]
if not services:
    service = ET.SubElement(app, "service", {
        ANDROID + "name": service_name,
        ANDROID + "label": "CoC Builder Assistant",
        ANDROID + "permission": "android.permission.BIND_ACCESSIBILITY_SERVICE",
        ANDROID + "exported": "true",
    })
    filt = ET.SubElement(service, "intent-filter")
    ET.SubElement(filt, "action", {ANDROID + "name": "android.accessibilityservice.AccessibilityService"})
    ET.SubElement(service, "meta-data", {
        ANDROID + "name": "android.accessibilityservice",
        ANDROID + "resource": "@xml/accessibility_service_config",
    })
else:
    service = services[0]
    service.set(ANDROID + "permission", "android.permission.BIND_ACCESSIBILITY_SERVICE")
    service.set(ANDROID + "exported", "true")
    if not any(a.get(ANDROID + "name") == "android.accessibilityservice.AccessibilityService"
               for f in service.findall("intent-filter") for a in f.findall("action")):
        filt = ET.SubElement(service, "intent-filter")
        ET.SubElement(filt, "action", {ANDROID + "name": "android.accessibilityservice.AccessibilityService"})
    metadata = [e for e in service.findall("meta-data") if e.get(ANDROID + "name") == "android.accessibilityservice"]
    if metadata:
        metadata[0].set(ANDROID + "resource", "@xml/accessibility_service_config")
    else:
        ET.SubElement(service, "meta-data", {
            ANDROID + "name": "android.accessibilityservice",
            ANDROID + "resource": "@xml/accessibility_service_config",
        })

tree.write(manifest, encoding="utf-8", xml_declaration=True)
# Fail the build if the required registration isn't present.
check = ET.parse(manifest).getroot()
app = check.find("application")
service = next((e for e in app.findall("service") if e.get(ANDROID + "name") == service_name), None)
assert service is not None
assert service.get(ANDROID + "permission") == "android.permission.BIND_ACCESSIBILITY_SERVICE"
assert any(e.get(ANDROID + "name") == "android.accessibilityservice" and e.get(ANDROID + "resource") == "@xml/accessibility_service_config" for e in service.findall("meta-data"))
print("Accessibility manifest registration ensured and verified.")
