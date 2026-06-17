from flask import Blueprint

from ..service.analysis_service import AnalysisService
from ..service.extraction_service import ExtractionService
from .analysis_api import AnalysisAPIs
from .extraction_api import ExtractionAPIs


def register_apis(app):
    extraction_bp = Blueprint("extractions", __name__, url_prefix="/extractions")
    extraction_service = ExtractionService()
    extraction_apis = ExtractionAPIs(extraction_service)
    extraction_apis.add_url_rules(extraction_bp)
    app.register_blueprint(extraction_bp)

    analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")
    analysis_service = AnalysisService()
    analysis_apis = AnalysisAPIs(analysis_service)
    analysis_apis.add_url_rules(analysis_bp)
    app.register_blueprint(analysis_bp)
