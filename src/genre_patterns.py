# Create a new file called genre_patterns.py

ADDITIONAL_PATTERNS = {
    'dancehall': {
        'musical_patterns': [
            # Additional common dancehall phrases and terms
            r'(?i)dance\s*hall',
            r'(?i)big\s*tune',
            r'(?i)pull\s*up',
            r'(?i)selector',
            r'(?i)sound\s*boy',
            r'(?i)yard',
            r'(?i)bless\s*up'
        ],
        'artist_locations': [
            r'(?i)kingston',
            r'(?i)jamaica',
            r'(?i)port\s*more',
            r'(?i)montego\s*bay'
        ]
    },
    'soca': {
        'musical_patterns': [
            # Additional soca-specific terms
            r'(?i)fete',
            r'(?i)mas',
            r'(?i)bacchanal',
            r'(?i)jumbie',
            r'(?i)wine\s*down',
            r'(?i)carnival\s*time'
        ],
        'artist_locations': [
            r'(?i)trinidad',
            r'(?i)tobago',
            r'(?i)port\s*of\s*spain',
            r'(?i)barbados',
            r'(?i)grenada'
        ]
    },
    'afrobeats': {
        'musical_patterns': [
            # Additional afrobeats indicators
            r'(?i)afro\s*(?:beats|pop|fusion)',
            r'(?i)naija',
            r'(?i)pon\s*pon',
            r'(?i)zanku',
            r'(?i)gwara\s*gwara',
            r'(?i)azonto'
        ],
        'artist_locations': [
            r'(?i)lagos',
            r'(?i)accra',
            r'(?i)nigeria',
            r'(?i)ghana',
            r'(?i)south\s*africa'
        ]
    }
}

def update_genre_patterns(detector):
    """Update the enhanced genre detector with additional patterns."""
    for genre, patterns in ADDITIONAL_PATTERNS.items():
        if genre in detector.genre_patterns:
            detector.genre_patterns[genre].update(patterns)
        else:
            detector.genre_patterns[genre] = patterns