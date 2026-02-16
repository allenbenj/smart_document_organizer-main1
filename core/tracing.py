"""
OpenTelemetry tracing bootstrap for Smart Document Organizer.

- Non-fatal, best-effort initialization (will not break startup if OTEL libs missing)
- Instruments FastAPI, requests, and logging when available
- Exposes `init_tracing(app, service_name)` called from `Start.py`

"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def init_tracing(app: Optional[object] = None, service_name: str = "smart_document_organizer") -> bool:
    """Initialize OpenTelemetry tracing (best-effort).

    - If OTLP endpoint is set via OTEL_EXPORTER_OTLP_ENDPOINT, use OTLP exporter.
    - Otherwise fall back to ConsoleSpanExporter for local/dev visibility.
    - Safe no-op if required OTEL packages are not installed.
    """
    try:
        # Core SDK pieces
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        # Exporters (OTLP via gRPC preferred when configured)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_available = True
        except Exception:
            OTLPSpanExporter = None
            otlp_available = False

        # Instrumentations
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        except Exception:
            FastAPIInstrumentor = None
        try:
            from opentelemetry.instrumentation.requests import RequestsInstrumentor
        except Exception:
            RequestsInstrumentor = None
        try:
            from opentelemetry.instrumentation.logging import LoggingInstrumentor
        except Exception:
            LoggingInstrumentor = None

        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", os.getenv("OTEL_ENDPOINT", "")).strip()
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Choose exporter
        exporter = None
        if endpoint and otlp_available:
            try:
                exporter = OTLPSpanExporter(endpoint=endpoint)
                logger.info("OTLP exporter configured: %s", endpoint)
            except Exception as e:
                logger.warning("Failed to configure OTLP exporter (%s) -- falling back to console: %s", endpoint, e)
                exporter = ConsoleSpanExporter()
        else:
            exporter = ConsoleSpanExporter()

        provider.add_span_processor(BatchSpanProcessor(exporter))

        # Instrument common libraries (best-effort)
        try:
            if RequestsInstrumentor is not None:
                RequestsInstrumentor().instrument()
        except Exception:
            logger.debug("Requests instrumentation unavailable or failed", exc_info=True)

        try:
            if LoggingInstrumentor is not None:
                LoggingInstrumentor().instrument(set_logging_format=True)
        except Exception:
            logger.debug("Logging instrumentation unavailable or failed", exc_info=True)

        # Instrument FastAPI app if provided
        if app is not None and FastAPIInstrumentor is not None:
            try:
                FastAPIInstrumentor().instrument_app(app)
            except Exception:
                logger.debug("FastAPI instrumentation failed", exc_info=True)

        logger.info("Tracing initialized (service=%s)", service_name)
        return True

    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Tracing libraries not available or initialization failed: %s", exc)
        return False
