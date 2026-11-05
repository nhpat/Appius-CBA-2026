from prospector.names import normalize, similarity
from prospector.score import peer_score as peerScore, validate


def test_peerCutoffAcceptsConnecticutCollision():
    client = {'peers': ['Connecticut Public Health Association']}
    grant = {'bmf_name': None, 'recipient_name': 'Connecticut Association of Health Plans'}
    config = {'fuzzy_threshold': 90, 'one_match': 0.5, 'two_plus': 1.0}
    assert peerScore([grant], client, config) == (0.5, client['peers'])
    config['fuzzy_threshold'] = 95
    assert peerScore([grant], client, config) == (0, [])


def test_seedCutoffMissesVerifiedFormerName():
    seed = 'New York Health Foundation'
    formerName = 'New York State Health Foundation'
    boundary = similarity(normalize(seed), normalize(formerName))
    client = {'validation_seeds': [seed]}
    prospect = {'name': formerName, 'tier': 'B', 'form': '990PF', 'rank': 1, 'score': 60}
    assert validate(client, [prospect], [])[0]['found'] == 'N'
    assert validate(client, [prospect], [], threshold=boundary)[0]['status'] == 'OK'


def test_normalizationCanEraseIdentityDistinctions():
    assert similarity(normalize('Example Trust'), normalize('Example Fund')) == 100
