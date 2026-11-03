"""GPU memory and power sampled with nvidia-smi during a run (METHODOLOGY.md 8.6).

`nvidia-smi --query-gpu=index,memory.used,power.draw --format=csv,noheader,nounits -lms <interval>` runs for the
whole run, on this machine or, when the model server is another machine, on that machine over ssh
(AIBENCH_SERVER_HOST). Every execution then gets the peak VRAM, the average power and the energy of its own time
window. Without nvidia-smi (no NVIDIA GPU, a Mac, OpenRouter) the sampler reports itself unavailable and the columns
stay empty: nothing fails.
"""
import shutil
import subprocess
import threading
import time

QUERY = ["nvidia-smi", "--query-gpu=index,memory.used,power.draw", "--format=csv,noheader,nounits"]
EMPTY = {"peak_vram_mib": "", "avg_power_w": "", "energy_wh": ""}


def _num(x):
    try:
        return float(x)
    except ValueError:
        return None  # "[N/A]" on cards that do not report power


class Sampler:
    def __init__(self, server_host=None, interval_ms=500, gpu_index=0, command=None, clock=time.monotonic,
                 first_sample_timeout=5.0):
        self.interval_ms, self.gpu_index, self.clock = interval_ms, str(gpu_index), clock
        self.first_sample_timeout = first_sample_timeout
        self.ready = threading.Event()  # set on the first sample, or when nvidia-smi stops writing
        query = QUERY + ["-lms", str(interval_ms)]
        self.command = command or (["ssh", "-o", "BatchMode=yes", server_host, " ".join(query)] if server_host
                                   else query)
        self.samples, self.status, self.proc, self.thread = [], "not started", None, None
        self.lock = threading.Lock()

    def start(self):
        if not shutil.which(self.command[0]):
            self.status = f"unavailable: {self.command[0]} not found"
            return self
        try:
            self.proc = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                         stdin=subprocess.DEVNULL)
        except OSError as e:
            self.status = f"unavailable: {type(e).__name__}"
            return self
        self.status = "ok"
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()
        # nvidia-smi (more so over ssh) takes a moment to print its first line: without this wait, an execution
        # that ends before it gets no GPU columns. A silent nvidia-smi holds the run for at most the timeout.
        self.ready.wait(self.first_sample_timeout)
        return self

    def _read(self):
        try:
            for line in self.proc.stdout:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) != 3 or parts[0] != self.gpu_index:
                    continue
                mem, power = _num(parts[1]), _num(parts[2])
                if mem is None:
                    continue
                with self.lock:
                    self.samples.append((self.clock(), mem, power))
                self.ready.set()
        except ValueError:
            pass  # stdout closed by stop()
        finally:
            self.ready.set()

    def stop(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            if self.thread:
                self.thread.join(timeout=5)
            self.proc.stdout.close()
        if self.status == "ok" and not self.samples:
            self.status = "unavailable: nvidia-smi gave no samples (no NVIDIA GPU or driver?)"
        return self

    def _between(self, t0, t1):
        with self.lock:
            inside = [s for s in self.samples if t0 <= s[0] <= t1]
            if not inside:  # a short execution between two samples: the last sample before its end
                before = [s for s in self.samples if s[0] <= t1 and t1 - s[0] <= 2 * self.interval_ms / 1000]
                inside = before[-1:]
        return inside

    def window(self, t0, t1):
        """Peak VRAM (MiB), average power (W) and energy (Wh) between two clock() readings."""
        inside = self._between(t0, t1)
        if not inside:
            return dict(EMPTY)
        powers = [p for _, _, p in inside if p is not None]
        avg = sum(powers) / len(powers) if powers else None
        return {"peak_vram_mib": int(max(m for _, m, _ in inside)),
                "avg_power_w": "" if avg is None else round(avg, 1),
                "energy_wh": "" if avg is None else round(avg * max(t1 - t0, 0) / 3600, 6)}

    def summary(self):
        with self.lock:
            s = list(self.samples)
        out = {"status": self.status, "interval_ms": self.interval_ms, "samples": len(s)}
        if s:
            powers = [p for _, _, p in s if p is not None]
            out.update(peak_vram_mib=int(max(m for _, m, _ in s)),
                       avg_power_w=round(sum(powers) / len(powers), 1) if powers else None,
                       peak_power_w=round(max(powers), 1) if powers else None)
        return out


class Disabled:
    """Stands in for a Sampler when sampling does not apply (simulated runs, OpenRouter)."""

    def __init__(self, reason):
        self.status = f"not sampled: {reason}"

    def start(self):
        return self

    def stop(self):
        return self

    def window(self, t0, t1):
        return dict(EMPTY)

    def summary(self):
        return {"status": self.status}
