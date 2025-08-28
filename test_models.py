"""
Quick test to verify the JobResponse and JobStatus models work correctly.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to Python path
src_path = Path('src')
sys.path.insert(0, str(src_path))

from langfuse_observability.shared.models import JobResponse, JobStatus, TraceRegistrationRequest

def test_job_models():
    """Test that JobResponse and JobStatus models work correctly."""
    
    print("🧪 Testing Pydantic Models")
    print("=" * 40)
    
    # Test JobResponse
    print("🔬 Testing JobResponse...")
    job_response = JobResponse(
        job_id="test-job-123",
        status="pending",
        message="Job queued successfully"
    )
    print(f"✅ JobResponse created: {job_response.job_id} - {job_response.status}")
    
    # Test JobStatus
    print("🔬 Testing JobStatus...")
    job_status = JobStatus(
        job_id="test-job-123",
        status="processing",
        created_at=datetime.now(),
        started_at=datetime.now(),
        progress={"processed": 5, "total": 10}
    )
    print(f"✅ JobStatus created: {job_status.job_id} - {job_status.status}")
    print(f"   Progress: {job_status.progress}")
    
    # Test TraceRegistrationRequest (existing)
    print("🔬 Testing TraceRegistrationRequest...")
    trace_request = TraceRegistrationRequest(
        input_text="Test input",
        agent_id="test-agent",
        agent_alias_id="test-alias",
        session_id="test-session",
        output_text="Test output",
        traces=[{"test": "trace"}]
    )
    print(f"✅ TraceRegistrationRequest created: {trace_request.agent_id}")
    
    print("\n🎉 All models work correctly!")
    print("✅ Import error should now be resolved")
    
    return True

if __name__ == "__main__":
    test_job_models()