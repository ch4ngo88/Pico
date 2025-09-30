# memory_monitor.py
import gc
from log_utils import log_message, log_once_per_day

# --------------------------------------------------------------------
# Memory Management
# --------------------------------------------------------------------
_last_gc_time = 0
_gc_counter = 0

def monitor_memory(log_path=None, force_gc=False):
    """
    Überwacht Speicherverbrauch und führt bei Bedarf Garbage Collection durch.
    Loggt nur wichtige Änderungen.
    """
    global _last_gc_time, _gc_counter
    
    try:
        import time
        now = time.time()
        
        # Automatische GC alle 3 Minuten oder bei Bedarf (optimiert von 5 Min)
        if force_gc or (now - _last_gc_time > 180):
            free_before = gc.mem_free()
            gc.collect()
            free_after = gc.mem_free()
            _last_gc_time = now
            _gc_counter += 1
            
            # Nur bei signifikanten Änderungen loggen
            freed = free_after - free_before
            if abs(freed) > 1024 or _gc_counter % 20 == 0:  # Alle 20 GCs oder >1KB befreit
                log_message(log_path, "[Memory] GC #{}: {} bytes frei (+{})".format(_gc_counter, free_after, freed))
            
            # Warnung bei niedrigem Speicher
            if free_after < 12288:  # Weniger als 12KB (optimiert von 10KB)
                log_message(log_path, "[Memory WARNING] Nur noch {} bytes frei!".format(free_after), force=True)
                
        return gc.mem_free()
        
    except Exception as e:
        log_message(log_path, "[Memory Monitor Fehler] {}".format(str(e)))
        return 0


def emergency_cleanup(log_path=None):
    """Notfall-Speicher-Aufräumung"""
    try:
        import time
        log_message(log_path, "[Memory] Notfall-Cleanup gestartet", force=True)
        
        # Optimierte GC-Durchläufe (weniger Zyklen, mehr Zeit)
        for i in range(3):
            gc.collect()
            time.sleep(0.2)  # Längerer Sleep für bessere GC-Effizienz
        
        free_mem = gc.mem_free()
        log_message(log_path, "[Memory] Notfall-Cleanup beendet: {} bytes frei".format(free_mem), force=True)
        return free_mem
        
    except Exception as e:
        log_message(log_path, "[Memory Cleanup Fehler] {}".format(str(e)))
        return 0


def get_memory_stats():
    """Gibt aktuelle Memory-Stats zurück"""
    try:
        return {
            'free': gc.mem_free(),
            'allocated': gc.mem_alloc(),
            'gc_count': _gc_counter
        }
    except Exception:
        return {'free': 0, 'allocated': 0, 'gc_count': 0}