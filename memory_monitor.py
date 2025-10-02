# memory_monitor.py
import gc
from log_utils import log_message, log_once_per_day

# --------------------------------------------------------------------
# Memory Management & Diagnose
# --------------------------------------------------------------------
_last_gc_time = 0
_gc_counter = 0
_memory_history = []  # Speicher-Verlauf fuer Diagnose (Tuples)
_boot_memory = None   # Speicher direkt nach Boot
_max_history = 30     # Behalte letzte 30 Messungen
_low_strikes = 0      # aufeinanderfolgende Low-Memory-Treffer
_last_emergency_ts = 0
_last_low_log_ts = 0  # Throttle fuer LOW-Logs

def record_boot_memory():
    """Speichere Speicher direkt nach Boot fuer Vergleich"""
    global _boot_memory
    if _boot_memory is None:
        _boot_memory = gc.mem_free()
        # Notiz: Nicht in die Konsole loggen, wenn noch kein Logfile existiert.
        # Der erste echte Log-Aufruf erfolgt spaeter mit log_path.


def _add_memory_sample(free_mem, context=""):
    """Fuegt Speicher-Sample zur Historie hinzu (als Tuple: (t, free, ctx))"""
    global _memory_history, _max_history
    import time
    _memory_history.append((time.time(), free_mem, context))
    if len(_memory_history) > _max_history:
        _memory_history.pop(0)


def analyze_memory_trend(log_path=None):
    """Analysiert Speicher-Trend und findet Lecks"""
    if len(_memory_history) < 5:
        return
    
    # Berechne Speicher-Verlust ueber Zeit
    first = _memory_history[0]
    last = _memory_history[-1]
    time_diff = last[0] - first[0]
    memory_diff = last[1] - first[1]
    
    if time_diff > 300:  # Nur wenn mindestens 5 Minuten Daten
        leak_rate = memory_diff / time_diff  # bytes per second
        
        if leak_rate < -10:  # Mehr als 10 bytes/sec Verlust
            log_message(log_path, "[Memory LEAK DETECTED] {:.1f} bytes/sec Verlust ueber {:.1f}min".format(
                leak_rate, time_diff/60), force=True)
            
            # Finde groessten Sprung
            max_drop = 0
            drop_context = ""
            for i in range(1, len(_memory_history)):
                drop = _memory_history[i-1][1] - _memory_history[i][1]
                if drop > max_drop:
                    max_drop = drop
                    drop_context = _memory_history[i][2]
            
            if max_drop > 2048:
                log_message(log_path, "[Memory] Groesster Speicherverlust: {} bytes bei '{}'".format(
                    max_drop, drop_context), force=True)


def monitor_memory(log_path=None, force_gc=False, context=""):
    """
    ueberwacht Speicherverbrauch mit detaillierter Diagnose.
    """
    global _last_gc_time, _gc_counter
    
    try:
        import time
        now = time.time()
        
        # Speichere Boot-Speicher beim ersten Aufruf
        record_boot_memory()
        
        current_free = gc.mem_free()
        _add_memory_sample(current_free, context)
        
        # Automatische GC alle 3 Minuten oder bei Bedarf
        if force_gc or (now - _last_gc_time > 180):
            free_before = current_free
            gc.collect()
            free_after = gc.mem_free()
            _last_gc_time = now
            _gc_counter += 1
            
            # Diagnose-Info bei jedem GC
            freed = free_after - free_before
            boot_loss = _boot_memory - free_after if _boot_memory else 0
            
            # Log-Spam eliminiert: nur bei bedeutender Aenderung (>=32KB) oder forced GC
            SHOULD_LOG_GC = (
                force_gc or
                (freed >= 32768)  # >= 32KB freigegeben
            )
            if SHOULD_LOG_GC:
                log_message(log_path, "[Memory] GC #{}: {}KB frei (+{}), Boot-Verlust: {}KB".format(
                    _gc_counter, free_after//1024, freed, boot_loss//1024))
            
            # Analysiere Trend alle 10 GCs
            if _gc_counter % 10 == 0:
                analyze_memory_trend(log_path)
            
            # Warnung bei niedrigem Speicher
            if free_after < 15360:
                log_message(log_path, "[Memory WARNING] Nur noch {}KB frei! Context: {}".format(
                    free_after//1024, context), force=True)
                
            return free_after
        
        return current_free
        
    except Exception as e:
        log_message(log_path, "[Memory Monitor Fehler] {}".format(str(e)))
        return 0


def emergency_cleanup(log_path=None):
    """Notfall-Speicher-Aufraeumung"""
    try:
        import time
        log_message(log_path, "[Memory] Notfall-Cleanup gestartet", force=True)
        
        # Optimierte GC-Durchlaeufe (weniger Zyklen, mehr Zeit)
        for i in range(3):
            gc.collect()
            time.sleep(0.2)  # Laengerer Sleep fuer bessere GC-Effizienz
        
        free_mem = gc.mem_free()
        log_message(log_path, "[Memory] Notfall-Cleanup beendet: {} bytes frei".format(free_mem), force=True)
        return free_mem
        
    except Exception as e:
        log_message(log_path, "[Memory Cleanup Fehler] {}".format(str(e)))
        return 0


def check_and_cleanup_low_memory(log_path=None, threshold=8192, cooldown_s=300):
    """Sanfter Low-Memory-Manager mit Hysterese und Cooldown.
    - Fuehrt zuerst eine zusaetzliche GC aus, wenn der Schwellwert unterschritten wird.
    - Loest erst dann Notfall-Cleanup aus, wenn weiterhin zu wenig frei ist und
      seit dem letzten Notfall-Cleanup mindestens cooldown_s vergangen sind.
    """
    global _low_strikes, _last_emergency_ts, _last_low_log_ts
    try:
        import time
        free = gc.mem_free()
        if free >= threshold:
            # Nur nach anhaltendem Low zunaechst Recovery loggen
            if _low_strikes >= 2:
                log_message(log_path, "[Memory LOW] Erholt nach GC: {}KB frei".format(free//1024))
            _low_strikes = 0
            return free

        # Erster Treffer -> zusaetzliche GC und erneut pruefen
        _low_strikes += 1
        if _low_strikes == 1:
            gc.collect()
            free2 = gc.mem_free()
            if free2 >= threshold:
                _low_strikes = 0
                return free2
            free = free2

        # Notfall-Cleanup nur mit Cooldown
        now = time.time()
        if (now - _last_emergency_ts) >= cooldown_s:
            log_message(log_path, "[EMERGENCY] Kritischer Speichermangel: {}KB frei!".format(free//1024), force=True)
            free_after = emergency_cleanup(log_path)
            _last_emergency_ts = now
            _low_strikes = 0
            return free_after
        else:
            # Cooldown aktiv: nur einmal pro Cooldown-Fenster loggen
            if (now - _last_low_log_ts) >= cooldown_s:
                log_message(log_path, "[Memory LOW] Anhaltend (Cooldown aktiv): {}KB frei".format(free//1024))
                _last_low_log_ts = now
            return free
    except Exception as e:
        log_message(log_path, "[LowMemory Manager Fehler] {}".format(str(e)))
        return gc.mem_free()


def get_memory_stats():
    """Gibt aktuelle Memory-Stats zurueck"""
    try:
        return {
            'free': gc.mem_free(),
            'allocated': gc.mem_alloc(),
            'gc_count': _gc_counter
        }
    except Exception:
        return {'free': 0, 'allocated': 0, 'gc_count': 0}


def dump_memory_history(log_path=None):
    """Gibt komplette Speicher-Historie aus fuer Diagnose"""
    log_message(log_path, "[Memory History] Letzte {} Messungen:".format(len(_memory_history)), force=True)
    
    for i, sample in enumerate(_memory_history):
        import time
        base_time = _memory_history[0][0] if _memory_history else 0
        rel_time = sample[0] - base_time
        log_message(log_path, "  #{}: +{:.0f}s -> {}KB frei ({})".format(
            i+1, rel_time, sample[1]//1024, sample[2]), force=True)
    
    if _boot_memory:
        current = gc.mem_free()
        total_loss = _boot_memory - current
        log_message(log_path, "[Memory Summary] Boot: {}KB, Jetzt: {}KB, Verlust: {}KB".format(
            _boot_memory//1024, current//1024, total_loss//1024), force=True)


def analyze_memory_objects(log_path=None):
    """Analysiert welche Python-Objekte den meisten Speicher verbrauchen"""
    try:
        # Einfache Objektzaehlung (MicroPython hat kein sys.getsizeof)
        import time
        before_analysis = gc.mem_free()
        
        # Erstelle Test-Objekte um Overhead zu messen
        test_dict = {'test': 'value', 'number': 42}
        test_list = [1, 2, 3, 4, 5]
        test_string = "Memory analysis test string" * 10
        
        after_objects = gc.mem_free()
        object_overhead = before_analysis - after_objects
        
        del test_dict, test_list, test_string
        gc.collect()
        after_cleanup = gc.mem_free()
        cleanup_recovered = after_cleanup - after_objects
        
        log_message(log_path, "[Memory Objects] Test-Objekt Overhead: {} bytes".format(object_overhead), force=True)
        log_message(log_path, "[Memory Objects] Cleanup wiederhergestellt: {} bytes".format(cleanup_recovered), force=True)
        
        # Zeige GC-Statistiken wenn verfuegbar
        try:
            log_message(log_path, "[Memory Objects] Aktuell allokiert: {} bytes".format(gc.mem_alloc()), force=True)
        except AttributeError:
            pass  # mem_alloc nicht in allen MicroPython Versionen verfuegbar
            
    except Exception as e:
        log_message(log_path, "[Memory Objects Fehler] {}".format(str(e)))