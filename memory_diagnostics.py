# memory_diagnostics.py
# Spezialisierte Speicher-Diagnose um Memory-Lecks zu identifizieren

from memory_monitor import monitor_memory
import gc

def diagnose_web_request_memory(log_path=None):
    """Misst Speicherverbrauch vor und nach Web-Request-Simulation"""
    from log_utils import log_message
    
    try:
        # Baseline messen
        gc.collect()
        baseline = gc.mem_free()
        
        # Simuliere typische Web-Request-Operationen
        log_message(log_path, "[Diagnose] Web-Request Memory-Test gestartet", force=True)
        
        # Test 1: HTTP Header Parsing
        test_header = "GET /index.html HTTP/1.1\r\nHost: 192.168.1.100\r\nConnection: keep-alive\r\n\r\n"
        header_parts = test_header.split('\r\n')
        gc.collect()
        after_header = gc.mem_free()
        
        # Test 2: HTML Template Loading
        html_chunk = "<html><head><title>Test</title></head><body>" + "x" * 1000 + "</body></html>"
        gc.collect()
        after_html = gc.mem_free()
        
        # Test 3: JSON Response Creation
        json_data = '{"alarm1":{"time":"07:00","text":"Aufstehen","days":"1234567","active":true}}'
        gc.collect()
        after_json = gc.mem_free()
        
        # Speicher-Verbrauch loggen
        log_message(log_path, "[Diagnose] Baseline: {}KB".format(baseline//1024), force=True)
        log_message(log_path, "[Diagnose] Nach Header: {}KB (Verlust: {})".format(
            after_header//1024, baseline - after_header), force=True)
        log_message(log_path, "[Diagnose] Nach HTML: {}KB (Verlust: {})".format(
            after_html//1024, after_header - after_html), force=True)
        log_message(log_path, "[Diagnose] Nach JSON: {}KB (Verlust: {})".format(
            after_json//1024, after_html - after_json), force=True)
        
        # Cleanup und finale Messung
        del test_header, header_parts, html_chunk, json_data
        gc.collect()
        final = gc.mem_free()
        
        total_leak = baseline - final
        log_message(log_path, "[Diagnose] Final: {}KB, Gesamt-Leck: {} bytes".format(
            final//1024, total_leak), force=True)
        
        return total_leak
        
    except Exception as e:
        log_message(log_path, "[Diagnose Fehler] {}".format(str(e)))
        return -1


def diagnose_rtc_memory(log_path=None):
    """Misst Speicherverbrauch bei RTC-Operationen"""
    from log_utils import log_message
    from time_config import aktualisiere_zeit
    
    try:
        gc.collect()
        baseline = gc.mem_free()
        
        log_message(log_path, "[Diagnose] RTC Memory-Test gestartet", force=True)
        
        # Mehrere RTC-Lesungen simulieren
        for i in range(5):
            time_result = aktualisiere_zeit(log_path)
            if i == 0:
                after_first = gc.mem_free()
        
        gc.collect()
        after_rtc = gc.mem_free()
        
        log_message(log_path, "[Diagnose] RTC Baseline: {}KB".format(baseline//1024), force=True)
        log_message(log_path, "[Diagnose] Nach erster RTC-Lesung: {}KB (Verlust: {})".format(
            after_first//1024, baseline - after_first), force=True)
        log_message(log_path, "[Diagnose] Nach 5 RTC-Lesungen: {}KB (Verlust: {})".format(
            after_rtc//1024, baseline - after_rtc), force=True)
        
        return baseline - after_rtc
        
    except Exception as e:
        log_message(log_path, "[Diagnose RTC Fehler] {}".format(str(e)))
        return -1


def diagnose_lcd_memory(log_path=None):
    """Misst Speicherverbrauch bei LCD-Operationen"""
    from log_utils import log_message
    
    try:
        gc.collect()
        baseline = gc.mem_free()
        
        log_message(log_path, "[Diagnose] LCD Memory-Test gestartet", force=True)
        
        # Simuliere LCD-Strings
        display_strings = [
            "Aktuelle Zeit: 14:25",
            "Naechster Alarm: 07:00",
            "Temperatur: 22.5°C",
            "Status: OK"
        ]
        
        for msg in display_strings:
            formatted_msg = "LCD: " + msg + " " * (16 - len(msg))  # 16-Char LCD padding
            
        gc.collect()
        after_lcd = gc.mem_free()
        
        log_message(log_path, "[Diagnose] LCD Baseline: {}KB".format(baseline//1024), force=True)
        log_message(log_path, "[Diagnose] Nach LCD-Operationen: {}KB (Verlust: {})".format(
            after_lcd//1024, baseline - after_lcd), force=True)
        
        return baseline - after_lcd
        
    except Exception as e:
        log_message(log_path, "[Diagnose LCD Fehler] {}".format(str(e)))
        return -1


def run_comprehensive_memory_diagnosis(log_path=None):
    """Fuehrt vollstaendige Speicher-Diagnose durch"""
    from log_utils import log_message
    
    log_message(log_path, "=== SPEICHER-DIAGNOSE GESTARTET ===", force=True)
    
    results = {}
    
    # Test Web-Request Memory
    results['web'] = diagnose_web_request_memory(log_path)
    
    # Test RTC Memory  
    results['rtc'] = diagnose_rtc_memory(log_path)
    
    # Test LCD Memory
    results['lcd'] = diagnose_lcd_memory(log_path)
    
    # Zusammenfassung
    log_message(log_path, "=== DIAGNOSE-ZUSAMMENFASSUNG ===", force=True)
    total_leak = 0
    for component, leak in results.items():
        if leak > 0:
            log_message(log_path, "[{}] Memory-Leck: {} bytes".format(
                component.upper(), leak), force=True)
            total_leak += leak
        else:
            log_message(log_path, "[{}] OK - kein Leck erkannt".format(
                component.upper()), force=True)
    
    log_message(log_path, "[GESAMT] Erkannte Lecks: {} bytes".format(total_leak), force=True)
    log_message(log_path, "=== DIAGNOSE BEENDET ===", force=True)
    
    return results


def diagnose_boot_memory_loss(log_path=None):
    """Analysiert warum so viel Speicher beim Boot verloren geht"""
    from log_utils import log_message
    import time
    
    log_message(log_path, "[Boot-Diagnose] System-Module laden...", force=True)
    
    # Messe Speicher nach wichtigen Import-Schritten
    measurements = []
    
    try:
        gc.collect()
        measurements.append(("Baseline", gc.mem_free()))
        
        # Import-Tests (diese sind normalerweise schon geladen, aber zeigt Overhead)
        import machine
        gc.collect()
        measurements.append(("machine import", gc.mem_free()))
        
        import socket
        gc.collect() 
        measurements.append(("socket import", gc.mem_free()))
        
        import uselect
        gc.collect()
        measurements.append(("uselect import", gc.mem_free()))
        
        # Hardware-Initialisierung simulieren
        test_pin = machine.Pin(2, machine.Pin.OUT)  # Test-Pin
        gc.collect()
        measurements.append(("Pin erstellt", gc.mem_free()))
        
        # String-Operationen (typisch fuer LCD/Log)
        big_string = "Alarm: " + "Test" * 100  # Simuliert grosse Log-Messages
        gc.collect()
        measurements.append(("String-Ops", gc.mem_free()))
        
        del big_string, test_pin
        gc.collect()
        measurements.append(("Nach Cleanup", gc.mem_free()))
        
        # Ergebnisse loggen
        log_message(log_path, "[Boot-Diagnose] Speicher-Verlauf:", force=True)
        for i, (stage, memory) in enumerate(measurements):
            if i > 0:
                loss = measurements[i-1][1] - memory
                log_message(log_path, "  {}: {}KB (-{} bytes)".format(
                    stage, memory//1024, loss), force=True)
            else:
                log_message(log_path, "  {}: {}KB".format(stage, memory//1024), force=True)
                
    except Exception as e:
        log_message(log_path, "[Boot-Diagnose Fehler] {}".format(str(e)))