# worker_manager.py - Runs background tasks on a QThreadPool.
# Tasks run asynchronously on pooled worker threads so the UI never stalls behind
# slow I/O or process scans. Tasks with identical keys are deduplicated via run_exclusive().
import logging
import threading
from collections.abc import Callable
from typing import Any

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

    def __init__(
        self,
        target: Callable,
        *args,
        pass_progress: bool = False,
        cleanup_callback: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.pass_progress = pass_progress
        self.cleanup_callback = cleanup_callback
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        """Executes the target function and emits signals on completion/error."""
        try:
            call_kwargs = dict(self.kwargs)
            if self.pass_progress:
                call_kwargs["progress_signal"] = self.signals.progress
            result = self.target(*self.args, **call_kwargs)
            try:
                self.signals.finished.emit(result)
            except RuntimeError:
                pass
        except Exception as e:
            target_name = getattr(self.target, "__name__", repr(self.target))
            logger.exception(f"Exception in worker thread for target {target_name}")
            try:
                self.signals.error.emit(e)
            except RuntimeError:
                pass
        except BaseException as e:
            target_name = getattr(self.target, "__name__", repr(self.target))
            logger.critical(f"BaseException in worker thread for target {target_name}: {e}")
            try:
                self.signals.error.emit(RuntimeError(f"Worker critical error: {type(e).__name__}: {e}"))
            except RuntimeError:
                pass
            raise
        finally:
            if self.cleanup_callback:
                try:
                    self.cleanup_callback()
                except Exception as e:
                    logger.error(f"Exception in worker cleanup callback: {e}")


class WorkerManager(QObject):
    """Manages a thread pool for all background tasks."""

    def __init__(self, parent: QObject | None = None, max_threads: int = 4):
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
        self._is_shutting_down = False
        self._shutdown_budget_ms = 5000
        logger.info(f"WorkerManager initialized with a pool of {max_threads} threads.")

    def run_task(
        self,
        target: Callable,
        *args,
        pass_progress: bool = False,
        cleanup_callback: Callable[[], None] | None = None,
        on_finished: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        **kwargs,
    ) -> bool:
        """Queues a task on the pool. Callbacks fire on the GUI thread.
        Returns True if started, False if refused."""
        if self._is_shutting_down:
            logger.warning("WorkerManager is shutting down; refusing new task.")
            if cleanup_callback:
                try:
                    cleanup_callback()
                except Exception as e:
                    logger.debug(f"Error in refused task cleanup_callback: {e}")
            return False

        pass_prog = pass_progress or (on_progress is not None)
        worker = Worker(
            target,
            *args,
            pass_progress=pass_prog,
            cleanup_callback=cleanup_callback,
            **kwargs,
        )
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
        return True

    def run_exclusive(
        self,
        key: str,
        target: Callable,
        *args,
        pass_progress: bool = False,
        on_finished: Callable[[Any], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        **kwargs,
    ) -> bool:
        """Like run_task, but refuses to start if a task with the same key is
        still running. Returns True if started, False if skipped."""
        if self._is_shutting_down:
            logger.warning(
                f"WorkerManager is shutting down; refusing exclusive task '{key}'."
            )
            return False

        with self._keys_lock:
            if key in self._active_keys:
                logger.debug(f"Skipping exclusive task '{key}' — already running.")
                return False
            self._active_keys.add(key)

        def cleanup():
            with self._keys_lock:
                self._active_keys.discard(key)

        return self.run_task(
            target,
            *args,
            pass_progress=pass_progress,
            cleanup_callback=cleanup,
            on_finished=on_finished,
            on_error=on_error,
            on_progress=on_progress,
            **kwargs,
        )

    def _release_signals(self, signals: WorkerSignals):
        with self._signals_lock:
            self._active_signals.discard(signals)

    def cleanup(self, timeout_ms: int = 5000) -> bool:
        """Waits for running tasks to finish when the application exits."""
        if self._is_shutting_down:
            if self._pool.activeThreadCount() == 0:
                return True
            wait_time = max(timeout_ms, self._shutdown_budget_ms)
            done = self._pool.waitForDone(wait_time)
            if not done:
                logger.warning(
                    f"Background tasks did not finish within {wait_time}ms during final shutdown. "
                    f"Abandoned {self._pool.activeThreadCount()} task(s)."
                )
            return done

        self._is_shutting_down = True
        self._shutdown_budget_ms = timeout_ms
        logger.info("--- YMU shutting down, waiting for background tasks... ---")
        self._pool.clear()
        done = self._pool.waitForDone(timeout_ms)
        with self._keys_lock:
            self._active_keys.clear()
        with self._signals_lock:
            self._active_signals.clear()
        if not done:
            remaining = self._pool.activeThreadCount()
            logger.warning(
                f"Background tasks did not finish within {timeout_ms}ms during shutdown. Abandoned {remaining} task(s)."
            )
        else:
            logger.info("--- YMU shut down successfully---")
        return done
