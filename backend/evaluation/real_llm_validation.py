import os
import json
import time
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Load .env into os.environ for OpenAI SDK
load_dotenv()

from fastapi.testclient import TestClient

from backend.main import app
from backend.api.deps import get_tutor_engine

client = TestClient(app)

class ValidationEngine:
    def __init__(self):
        self.output_dir = Path("docs/examples/real_llm_validation")
        self.reports_dir = Path("data/evaluation/reports")
        
        # Load baseline
        baseline_path = self.reports_dir / "regression_report.json"
        if baseline_path.exists():
            with open(baseline_path, "r") as f:
                self.baseline_data = json.load(f)
        else:
            self.baseline_data = {"results": []}
            
        self.baseline_map = {r["query"]: r for r in self.baseline_data.get("results", [])}
        
    def run(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        datasets = [
            Path("backend/evaluation/datasets/mathematics.json"),
            Path("backend/evaluation/datasets/physics.json"),
            Path("backend/evaluation/datasets/chemistry.json")
        ]
        
        # Initialize app startup manually since we need access to app.state
        with TestClient(app) as client:
            # Intercept engine answer
            original_engine = app.state.factory.tutor_engine
            intercepted_internal_resp = {}
            
            class InterceptingEngine:
                def answer(self, query, profile, context):
                    resp = original_engine.answer(query, profile, context)
                    intercepted_internal_resp["data"] = resp
                    return resp
                    
            app.dependency_overrides[get_tutor_engine] = lambda: InterceptingEngine()
            
            all_results = []
            global_idx = 1
            
            successful_requests = 0
            total_queries = 0
            verification_passed = 0
            citation_preserved = 0
            
            total_latency = 0.0
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_cost = 0.0
            
            for dataset_path in datasets:
                if not dataset_path.exists():
                    continue
                with open(dataset_path, "r") as f:
                    data = json.load(f)[:5]
                    
                for item in data:
                    query = item["query"]
                    total_queries += 1
                    
                    req_payload = {
                        "query": query,
                        "student_profile": {}
                    }
                    
                    start_time = time.time()
                    
                    # Make real HTTP POST request
                    api_resp = client.post("/api/v1/tutor/ask", json=req_payload)
                    
                    latency = time.time() - start_time
                    total_latency += latency
                    
                    q_dir = self.output_dir / f"{global_idx:03d}"
                    q_dir.mkdir(parents=True, exist_ok=True)
                    
                    with open(q_dir / "request.json", "w") as f:
                        json.dump(req_payload, f, indent=2)
                        
                    if api_resp.status_code == 200:
                        successful_requests += 1
                        api_json = api_resp.json()
                        
                        with open(q_dir / "response.json", "w") as f:
                            json.dump(api_json, f, indent=2)
                            
                        internal_resp = intercepted_internal_resp.get("data")
                        if internal_resp:
                            # Write tutor plan
                            if hasattr(internal_resp, "tutor_plan") and internal_resp.tutor_plan:
                                with open(q_dir / "tutor_plan.json", "w") as f:
                                    json.dump(internal_resp.tutor_plan.model_dump(), f, indent=2)
                            
                            # Write prompt doc
                            if hasattr(internal_resp, "rendered_response") and internal_resp.rendered_response:
                                prompt_doc = getattr(internal_resp.rendered_response, "prompt_document", None)
                                if prompt_doc:
                                    with open(q_dir / "prompt_document.json", "w") as f:
                                        json.dump(prompt_doc if isinstance(prompt_doc, dict) else (prompt_doc.model_dump() if hasattr(prompt_doc, "model_dump") else str(prompt_doc)), f, indent=2)
                                
                                with open(q_dir / "rendered.md", "w") as f:
                                    f.write(internal_resp.rendered_response.text)
                                    
                            # Write verification
                            if hasattr(internal_resp, "verification_report") and internal_resp.verification_report:
                                with open(q_dir / "verification.json", "w") as f:
                                    json.dump(internal_resp.verification_report.model_dump(), f, indent=2)
                                    
                        if api_json.get("verification_passed"):
                            verification_passed += 1
                        if len(api_json.get("citations", [])) > 0:
                            citation_preserved += 1
                            
                        baseline = self.baseline_map.get(query)
                        
                        result_entry = {
                            "query": query,
                            "success": True,
                            "actual_concept": api_json.get("primary_concept"),
                            "verification_passed": api_json.get("verification_passed"),
                            "citations": len(api_json.get("citations", [])),
                            "latency_s": latency,
                            "baseline_match": (baseline["actual_concept"] == api_json.get("primary_concept")) if baseline else None
                        }
                        all_results.append(result_entry)
                    else:
                        all_results.append({
                            "query": query,
                            "success": False,
                            "status_code": api_resp.status_code,
                            "error": api_resp.text
                        })
                        print(f"Error: {api_resp.text}", flush=True)
                    
                    print(f"[{global_idx}] {query} -> {api_resp.status_code}", flush=True)
                    global_idx += 1
                    
            report = {
                "total_queries": total_queries,
                "successful_requests": successful_requests,
                "verification_pass_rate": (verification_passed / successful_requests * 100) if successful_requests else 0,
                "citation_preservation_rate": (citation_preserved / successful_requests * 100) if successful_requests else 0,
                "average_latency_s": (total_latency / total_queries) if total_queries else 0,
                "token_usage": {
                    "prompt": total_prompt_tokens,
                    "completion": total_completion_tokens
                },
                "estimated_cost": total_cost,
                "provider": "openrouter",
                "model": "gpt-oss-120b",
                "results": all_results
            }
            
            with open(self.reports_dir / "real_llm_validation.json", "w") as f:
                json.dump(report, f, indent=2)
                
            print("Validation complete.")
        
if __name__ == "__main__":
    engine = ValidationEngine()
    engine.run()
