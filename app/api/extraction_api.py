from flask import Blueprint, jsonify, request

from ..error_handler import ValidationError


class ExtractionAPIs:
    def __init__(self, service):
        self.extraction_service = service

    def api_create_extraction_job(self):
        file = request.files.get("archive")
        pattern = request.form.get("pattern", "*.json")
        result = self.extraction_service.submit_extraction_job(file, pattern)
        return jsonify(result), 202

    def api_get_extraction_job_status(self, job_id):
        result = self.extraction_service.get_extraction_job_status(job_id)
        return jsonify(result), 200

    def api_list_extraction_results(self, job_id):
        try:
            limit = min(int(request.args.get("limit", 10)), 100)
            offset = int(request.args.get("offset", 0))
        except ValueError:
            raise ValidationError(
                details=[
                    {"field": "query", "message": "limit and offset must be integers"}
                ]
            )
        if limit < 0 or offset < 0:
            raise ValidationError(
                details=[
                    {
                        "field": "query",
                        "message": "limit and offset must be non-negative",
                    }
                ]
            )

        result = self.extraction_service.list_extraction_results(job_id, limit, offset)
        return jsonify(result), 200

    def add_url_rules(self, bp):
        bp.add_url_rule("/", view_func=self.api_create_extraction_job, methods=["POST"])
        bp.add_url_rule(
            "/<job_id>", view_func=self.api_get_extraction_job_status, methods=["GET"]
        )
        bp.add_url_rule(
            "/<job_id>/results",
            view_func=self.api_list_extraction_results,
            methods=["GET"],
        )
