# worker_manager.py - Manages the QThread and executes functions in the background.
import logging
from PySide6.QtCore import QObject, QThread, Signal, Slot, QMetaObject, Qt
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class Worker(QObject):
    """A generic worker that runs a target function in a separate thread."""

    finished = Signal(object)
    error = Signal(Exception)
    progress = Signal(int)

    def __init__(self, target: Callable, *args, **kwargs):
        super().__init__()
        self.target = target
        self.args = args
        self.kwargs = kwargs

    @Slot()
    def run(self):
        """Executes the target function and emits signals upon completion or error."""
        try:
            result = self.target(
                *self.args, progress_signal=self.progress, **self.kwargs
            )
            self.finished.emit(result)
        except Exception as e:
            logger.exception(
                f"Exception in worker thread for target {self.target.__name__}"
            )
            self.error.emit(e)


class WorkerManager(QObject):
    """Manages a single, reusable thread for all background tasks."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._thread = QThread()
        self._thread.start()
        self.active_workers = set()
        logger.info(
            f"WorkerManager initialized with thread: {self._thread.currentThread()}"
        )

    def run_task(
        self,
        target: Callable,
        *args,
        on_finished: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        **kwargs,
    ):
        """Creates a worker, keeps it alive, and queues its task."""
        worker = Worker(target, *args, **kwargs)
        worker.moveToThread(self._thread)

        self.active_workers.add(worker)

        if on_finished:
            worker.finished.connect(on_finished)
        if on_error:
            worker.error.connect(on_error)
        if on_progress:
            worker.progress.connect(on_progress)

        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.error.connect(lambda: self._on_worker_finished(worker))

        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)

        QMetaObject.invokeMethod(worker, "run", Qt.ConnectionType.QueuedConnection)  # type: ignore

    def _on_worker_finished(self, worker: Worker):
        """Slot to remove the worker from the active set once it's done."""
        logger.debug(f"Worker {worker} finished. Removing from active set.")
        self.active_workers.discard(worker)

    def cleanup(self):
        """Stops the managed thread cleanly when the application exits."""
        if self._thread.isRunning():
            logger.info("--- YMU shut down successfully---")
            self._thread.quit()
            self._thread.wait()
