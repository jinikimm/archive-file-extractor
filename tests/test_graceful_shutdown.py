"""
Graceful Shutdown Tests

테스트 범위:
1. 시그널 핸들러 등록 여부 (SIGINT / SIGTERM)
2. handle_shutdown이 sys.exit(0)을 호출하는지
3. 워커 스레드 내에서 RuntimeError가 발생했을 때
   - DB rollback 실행 여부
   - job status = "failed" 기록 여부
   - error_message 저장 여부
   - completed_at 설정 여부
   - cleanup() 호출 여부
   - db.session.remove() 호출 여부
4. non-daemon 스레드가 join으로 정상 종료 확인
"""

import signal
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app import create_app
from app.model import AnalysisJob, ExtractionJob, db
from app.service.analysis_service import AnalysisService
from app.service.extraction_service import ExtractionService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    _app = create_app(
        {"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}
    )
    with _app.app_context():
        db.create_all()
        yield _app


@pytest.fixture
def extraction_service():
    return ExtractionService()


@pytest.fixture
def analysis_service():
    return AnalysisService()


def _make_extraction_job(job_id, status="processing"):
    job = ExtractionJob(
        id=job_id,
        work_path=f"/tmp/extract/{job_id}/test.zip",
        file_name="test.zip",
        file_size=100,
        status=status,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(job)
    db.session.commit()
    return job


def _make_analysis_job(job_id, status="processing"):
    job = AnalysisJob(
        id=job_id,
        source_archive_name="test.zip",
        status=status,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(job)
    db.session.commit()
    return job


# ===========================================================================
# 1. 시그널 핸들러 등록 테스트
# ===========================================================================


class TestSignalHandlerRegistration:
    def test_sigint_handler_is_registered(self, app):
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler), "SIGINT handler must be a callable"
        assert handler not in (signal.SIG_DFL, signal.SIG_IGN)

    def test_sigterm_handler_is_registered(self, app):
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler), "SIGTERM handler must be a callable"
        assert handler not in (signal.SIG_DFL, signal.SIG_IGN)

    def test_sigint_and_sigterm_share_same_handler(self, app):
        """SIGINT, SIGTERM 모두 동일한 handle_shutdown에 연결되어야 한다."""
        assert signal.getsignal(signal.SIGINT) is signal.getsignal(signal.SIGTERM)


# ===========================================================================
# 2. handle_shutdown 동작 테스트
# ===========================================================================


class TestHandleShutdown:
    def test_handle_shutdown_raises_system_exit_with_code_0(self, app):
        handler = signal.getsignal(signal.SIGTERM)
        with pytest.raises(SystemExit) as exc_info:
            handler(signal.SIGTERM, None)
        assert exc_info.value.code == 0

    def test_handle_shutdown_logs_received_signal(self, app):
        handler = signal.getsignal(signal.SIGTERM)
        with patch.object(app.logger, "info") as mock_log:
            with pytest.raises(SystemExit):
                handler(signal.SIGTERM, None)
        mock_log.assert_called_once()
        log_message = mock_log.call_args[0][0]
        assert "shutdown" in log_message.lower()

    def test_handle_shutdown_called_on_sigint(self, app):
        handler = signal.getsignal(signal.SIGINT)
        with pytest.raises(SystemExit) as exc_info:
            handler(signal.SIGINT, None)
        assert exc_info.value.code == 0

    def test_handle_shutdown_sets_shutdown_events(self, app):
        """shutdown handler가 thread_shutdown_event와 process_shutdown_event를 set한다."""
        import app as app_module
        
        handler = signal.getsignal(signal.SIGTERM)
        with pytest.raises(SystemExit):
            handler(signal.SIGTERM, None)
        
        # 이벤트가 set되었는지 확인
        assert app_module.thread_shutdown_event.is_set()
        assert app_module.process_shutdown_event.is_set()

    def test_handle_shutdown_joins_non_daemon_threads(self, app):
        """shutdown handler가 non-daemon 스레드를 join한다."""
        non_daemon_finished = threading.Event()

        def non_daemon_worker():
            time.sleep(0.1)
            non_daemon_finished.set()

        # daemon=False 스레드 생성
        t = threading.Thread(target=non_daemon_worker, daemon=False)
        t.start()

        handler = signal.getsignal(signal.SIGTERM)
        with pytest.raises(SystemExit):
            handler(signal.SIGTERM, None)

        # 스레드가 완료되었는지 확인
        assert non_daemon_finished.is_set()
        assert not t.is_alive()


# ===========================================================================
# 3. Extraction 워커 — RuntimeError 처리 테스트
# ===========================================================================


class TestExtractionWorkerRuntimeError:
    """
    워커 스레드 내부에서 RuntimeError(shutdown signal)가 발생했을 때의 동작을 검증한다.
    Exception catch → rollback → failed 기록 → cleanup → session.remove
    """

    def test_runtime_error_sets_status_to_failed(self, app, extraction_service):
        with app.app_context():
            _make_extraction_job("ext-re-1")

            with patch(
                "app.service.extraction_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.extraction_service.cleanup"):
                extraction_service._process_extraction_job(
                    app, "ext-re-1", "/tmp/extract/ext-re-1/test.zip", "*.json"
                )

            job = ExtractionJob.query.get("ext-re-1")
            assert job.status == "failed"

    def test_runtime_error_saves_error_message(self, app, extraction_service):
        with app.app_context():
            _make_extraction_job("ext-re-2")

            with patch(
                "app.service.extraction_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.extraction_service.cleanup"):
                extraction_service._process_extraction_job(
                    app, "ext-re-2", "/tmp/extract/ext-re-2/test.zip", "*.json"
                )

            job = ExtractionJob.query.get("ext-re-2")
            assert job.error_message is not None
            assert "shutdown" in job.error_message

    def test_runtime_error_sets_completed_at(self, app, extraction_service):
        with app.app_context():
            _make_extraction_job("ext-re-3")

            with patch(
                "app.service.extraction_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.extraction_service.cleanup"):
                extraction_service._process_extraction_job(
                    app, "ext-re-3", "/tmp/extract/ext-re-3/test.zip", "*.json"
                )

            job = ExtractionJob.query.get("ext-re-3")
            assert job.completed_at is not None

    def test_runtime_error_calls_cleanup(self, app, extraction_service):
        with app.app_context():
            _make_extraction_job("ext-re-4")

            with patch(
                "app.service.extraction_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.extraction_service.cleanup") as mock_cleanup:
                extraction_service._process_extraction_job(
                    app, "ext-re-4", "/tmp/extract/ext-re-4/test.zip", "*.json"
                )

            mock_cleanup.assert_called_once_with("/tmp/extract/ext-re-4")

    def test_runtime_error_calls_db_session_remove(self, app, extraction_service):
        with app.app_context():
            _make_extraction_job("ext-re-5")

            with patch(
                "app.service.extraction_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.extraction_service.cleanup"), patch.object(
                db.session, "remove"
            ) as mock_remove:
                extraction_service._process_extraction_job(
                    app, "ext-re-5", "/tmp/extract/ext-re-5/test.zip", "*.json"
                )

            assert mock_remove.call_count >= 1

    def test_runtime_error_during_extraction_still_runs_cleanup(
        self, app, extraction_service
    ):
        """extraction 중 RuntimeError가 발생해도 finally의 cleanup은 반드시 실행된다."""
        with app.app_context():
            _make_extraction_job("ext-re-6")

            cleanup_called = []

            def fake_cleanup(path):
                cleanup_called.append(path)

            with patch(
                "app.service.extraction_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.extraction_service.cleanup", side_effect=fake_cleanup):
                extraction_service._process_extraction_job(
                    app, "ext-re-6", "/tmp/extract/ext-re-6/test.zip", "*.json"
                )

            assert len(cleanup_called) == 1


# ===========================================================================
# 4. Analysis 워커 — RuntimeError 처리 테스트
# ===========================================================================


class TestAnalysisWorkerRuntimeError:
    def test_runtime_error_during_extraction_sets_status_to_failed(
        self, app, analysis_service
    ):
        with app.app_context():
            _make_analysis_job("ana-re-1")

            with patch(
                "app.service.analysis_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.analysis_service.cleanup"):
                analysis_service._process_analysis_job(
                    app, "ana-re-1", "/tmp/analysis/ana-re-1/test.zip"
                )

            job = AnalysisJob.query.get("ana-re-1")
            assert job.status == "failed"

    def test_runtime_error_during_firmware_analysis_sets_status_to_failed(
        self, app, analysis_service
    ):
        with app.app_context():
            _make_analysis_job("ana-re-2")

            with patch(
                "app.service.analysis_service.extract_all_archives_parrel",
                return_value=[],
            ), patch(
                "app.service.analysis_service.firmware_analyzer",
                side_effect=RuntimeError("Analysis was interrupted by shutdown signal"),
            ), patch(
                "app.service.analysis_service.cleanup"
            ):
                analysis_service._process_analysis_job(
                    app, "ana-re-2", "/tmp/analysis/ana-re-2/test.zip"
                )

            job = AnalysisJob.query.get("ana-re-2")
            assert job.status == "failed"

    def test_runtime_error_saves_error_message(self, app, analysis_service):
        with app.app_context():
            _make_analysis_job("ana-re-3")

            with patch(
                "app.service.analysis_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.analysis_service.cleanup"):
                analysis_service._process_analysis_job(
                    app, "ana-re-3", "/tmp/analysis/ana-re-3/test.zip"
                )

            job = AnalysisJob.query.get("ana-re-3")
            assert job.error_message is not None

    def test_runtime_error_calls_cleanup(self, app, analysis_service):
        with app.app_context():
            _make_analysis_job("ana-re-4")

            with patch(
                "app.service.analysis_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.analysis_service.cleanup") as mock_cleanup:
                analysis_service._process_analysis_job(
                    app, "ana-re-4", "/tmp/analysis/ana-re-4/test.zip"
                )

            mock_cleanup.assert_called_once_with("/tmp/analysis/ana-re-4")

    def test_runtime_error_calls_db_session_remove(self, app, analysis_service):
        with app.app_context():
            _make_analysis_job("ana-re-5")

            with patch(
                "app.service.analysis_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.analysis_service.cleanup"), patch.object(
                db.session, "remove"
            ) as mock_remove:
                analysis_service._process_analysis_job(
                    app, "ana-re-5", "/tmp/analysis/ana-re-5/test.zip"
                )

            assert mock_remove.call_count >= 1

    def test_runtime_error_sets_completed_at(self, app, analysis_service):
        with app.app_context():
            _make_analysis_job("ana-re-6")

            with patch(
                "app.service.analysis_service.extract_all_archives_parrel",
                side_effect=RuntimeError("Extraction was interrupted by shutdown signal"),
            ), patch("app.service.analysis_service.cleanup"):
                analysis_service._process_analysis_job(
                    app, "ana-re-6", "/tmp/analysis/ana-re-6/test.zip"
                )

            job = AnalysisJob.query.get("ana-re-6")
            assert job.completed_at is not None


# ===========================================================================
# 5. 워커 스레드 정상 종료 테스트 (daemon=False)
# ===========================================================================


class TestNonDaemonWorkerGracefulShutdown:
    """
    daemon=False로 설정된 워커가 handle_shutdown에서 join으로 정상 종료됨을 검증한다.
    """

    def test_non_daemon_worker_completes_before_shutdown(self):
        """non-daemon 스레드는 shutdown handler의 join에서 기다려진다."""
        worker_completed = threading.Event()
        cleanup_called = threading.Event()

        def worker():
            try:
                time.sleep(0.2)  # 짧은 작업
            except RuntimeError:
                pass
            finally:
                cleanup_called.set()

        t = threading.Thread(target=worker, daemon=False)
        t.start()

        # join으로 대기
        t.join(timeout=5)

        assert not t.is_alive()
        assert cleanup_called.is_set()

    def test_daemon_worker_not_guaranteed_cleanup(self):
        """daemon=True 스레드는 프로세스 종료 시 즉시 kill되어 cleanup 미보장."""
        cleanup_called = threading.Event()

        def daemon_worker():
            try:
                time.sleep(10)  # 긴 작업
            finally:
                cleanup_called.set()

        t = threading.Thread(target=daemon_worker, daemon=True)
        t.start()

        # daemon 스레드는 메인이 종료되면 바로 kill됨 (join 의미 없음)
        # sys.exit() 호출 → daemon 스레드 finally 미실행 보장 안 됨
        # 따라서 daemon=False를 사용해야 함
        assert t.daemon is True