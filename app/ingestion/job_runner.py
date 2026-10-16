from concurrent.futures import ThreadPoolExecutor


class ThreadPoolJobRunner:
    """Background job runner using a thread pool.

    Each submitted job is wrapped in a Flask app context so that SQLAlchemy,
    current_app, etc. work correctly inside worker threads.

    To swap to Celery: create CeleryJobRunner implementing the same interface
    (submit, init_app), and change get_job_runner() to return it based on config.
    """

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._app = None

    def init_app(self, app):
        """Store the real Flask app object (not the LocalProxy).
        Called once from create_app() after all extensions are initialized."""
        self._app = app

    def submit(self, fn, *args, **kwargs):
        """Wrap fn in an app context before submitting to the thread pool."""
        app = self._app
        if app is None:
            raise RuntimeError('ThreadPoolJobRunner.init_app() was not called.')

        def run_with_context():
            with app.app_context():
                fn(*args, **kwargs)

        self._executor.submit(run_with_context)


_runner = ThreadPoolJobRunner()


def get_job_runner() -> ThreadPoolJobRunner:
    return _runner
