# worker_manager.py - Runs background tasks on a QThreadPool.
# Tasks may run in parallel, so the UI never stalls behind a slow task (e.g. a
# large download blocking process scans). Thread safety is favoured over
# maximum parallelism: shared state is guarded and duplicate work is skipped
# via run_exclusive().
import logging
import threading
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """Signals for a Worker. QRunnable cannot own signals itself, so they live
    on a separate QObject that the manager keeps alive until completion."""

    finished = Signal(object)
    error = Signal(Exception)
    progress = Signal(int)


class Worker(QRunnable):
    """A generic runnable that runs a target function in the thread pool."""

    def __init__(self, target: Callable, *args, **kwargs):
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        """Executes the target function and emits signals on completion/error."""
        try:
            result = self.target(
                *self.args, progress_signal=self.signals.progress, **self.kwargs
            )
            self.signals.finished.emit(result)
        except Exception as e:
            target_name = getattr(self.target, "__name__", repr(self.target))
            logger.exception(f"Exception in worker thread for target {target_name}")
            self.signals.error.emit(e)


class WorkerManager(QObject):
    """Manages a thread pool for all background tasks."""

    def __init__(self, parent: Optional[QObject] = None, max_threads: int = 4):
        super().__init__(parent)
        self._pool = QThreadPool()
        self._pool.setMaxThreadCount(max_threads)
        # Keep a strong reference to each WorkerSignals until its task ends,
        # otherwise autoDelete could collect it while a queued signal is in
        # flight.
        self._active_signals: set[WorkerSignals] = set()
        self._signals_lock = threading.Lock()
        # Guards run_exclusive keys so a duplicate task (e.g. a timer-driven
        # process scan) is skipped while one is already running.
        self._active_keys: set[str] = set()
        self._keys_lock = threading.Lock()
        logger.info(f"WorkerManager initialized with a pool of {max_threads} threads.")

    def run_task(
        self,
        target: Callable,
        *args,
        on_finished: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        **kwargs,
    ):
        """Queues a task on the pool. Callbacks fire on the GUI thread."""
        worker = Worker(target, *args, **kwargs)
        signals = worker.signals

        with self._signals_lock:
            self._active_signals.add(signals)

        conn = Qt.ConnectionType.QueuedConnection
        if on_finished:
            signals.finished.connect(on_finished, conn)
        if on_error:
            signals.error.connect(on_error, conn)
        if on_progress:
            signals.progress.connect(on_progress, conn)

        signals.finished.connect(lambda _: self._release_signals(signals), conn)
        signals.error.connect(lambda _: self._release_signals(signals), conn)

        self._pool.start(worker)

    def run_exclusive(
        self,
        key: str,
        target: Callable,
        *args,
        on_finished: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        **kwargs,
    ) -> bool:
        """Like run_task, but refuses to start if a task with the same key is
        still running. Returns True if started, False if skipped."""
        with self._keys_lock:
            if key in self._active_keys:
                logger.debug(f"Skipping exclusive task '{key}' — already running.")
                return False
            self._active_keys.add(key)

        def release_and_call(cb):
            def wrapped(value):
                # Release the key before running the user callback so a
                # callback that re-queues the same key is not blocked.
                with self._keys_lock:
                    self._active_keys.discard(key)
                if cb:
                    cb(value)

            return wrapped

        # Ensure the key is released even if no callback was provided.
        def ensure_release(_):
            with self._keys_lock:
                self._active_keys.discard(key)

        wrapped_finished = (
            release_and_call(on_finished) if on_finished else ensure_release
        )
        wrapped_error = release_and_call(on_error) if on_error else ensure_release

        self.run_task(
            target,
            *args,
            on_finished=wrapped_finished,
            on_error=wrapped_error,
            on_progress=on_progress,
            **kwargs,
        )
        return True

    def _release_signals(self, signals: WorkerSignals):
        with self._signals_lock:
            self._active_signals.discard(signals)

    def cleanup(self):
        """Waits for running tasks to finish when the application exits."""
        logger.info("--- YMU shutting down, waiting for background tasks... ---")
        self._pool.waitForDone(5000)
        logger.info("--- YMU shut down successfully---")
