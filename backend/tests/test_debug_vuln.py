import pytest

def test_debug_vuln(test_client):
    vuln_id = 'eeeeeeee-eeee-eeee-eeee-000000000000'
    response = test_client.get(
        f'/api/v1/vulnerabilities/{vuln_id}',
        headers={'Authorization': 'Bearer test_jwt_token'}
    )
    print('\nSTATUS:', response.status_code)
    print('BODY:', response.text[:1000])
    assert True
