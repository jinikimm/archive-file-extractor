from flask import jsonify, request, send_file

from ..error_handler import ValidationError


class AnalysisAPIs:
    def __init__(self, service):
        self.analysis_service = service

    def api_create_analysis_job(self):
        file = request.files.get("archive")
        result = self.analysis_service.submit_analysis_job(file)
        return jsonify(result), 202

    def api_get_analysis_job_status(self, job_id):
        result = self.analysis_service.get_analysis_job_status(job_id)
        return jsonify(result), 200

    def api_list_analysis_results(self, job_id):
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

        result = self.analysis_service.list_analysis_results(job_id, limit, offset)
        return jsonify(result), 200

    def api_download_analysis_results(self, job_id):
        csv_path = self.analysis_service.get_analysis_csv_path(job_id)
        return send_file(csv_path, as_attachment=True), 200

    def add_url_rules(self, bp):
        bp.add_url_rule("/", view_func=self.api_create_analysis_job, methods=["POST"])
        bp.add_url_rule(
            "/<job_id>", view_func=self.api_get_analysis_job_status, methods=["GET"]
        )
        bp.add_url_rule(
            "/<job_id>/results",
            view_func=self.api_list_analysis_results,
            methods=["GET"],
        )
        bp.add_url_rule(
            "/<job_id>/results/download",
            view_func=self.api_download_analysis_results,
            methods=["GET"],
        )
