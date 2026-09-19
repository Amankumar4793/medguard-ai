import json


def test_health_check_endpoint(client):
    """Test GET /api/health returns 200 with healthy status and metadata."""
    response = client.get('/api/health')
    assert response.status_code == 200

    data = json.loads(response.data)
    assert data['status'] == 'healthy'
    assert data['service'] == 'AI-Based Security System in Healthcare'
    assert data['version'] == '1.0.0'
    assert data['database'] == 'connected'
    assert 'uptime_seconds' in data


def test_404_error_handler(client):
    """Test that requesting nonexistent route returns clean JSON 404 response."""
    response = client.get('/api/non_existent_route')
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['success'] is False
    assert data['error'] == 'Not Found'
