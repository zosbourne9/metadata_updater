class LabelManager:
    """Manages music label validation and categorization."""
    
    def __init__(self):
        # Initialize major label groups with their subsidiaries
        self.major_labels = {
            # Universal Music Group
            'universal': [
                'universal', 'umg', 'interscope', 'geffen', 'aftermath',
                'def jam', 'island', 'republic', 'motown', 'polydor',
                'capitol', 'virgin', 'emi', 'blue note', 'verve',
                'deutsche grammophon', 'cash money', 'astralwerks',
                'schoolboy', 'xo', 'mad decent', '10k projects'
            ],
            
            # Sony Music
            'sony': [
                'sony', 'columbia', 'epic', 'rca', 'arista',
                'legacy', 'jive', 'so so def', 'bad boy',
                'zoo entertainment', 'portrait', 'provident',
                'ruff ryders', 'priority', 'j records'
            ],
            
            # Warner Music Group
            'warner': [
                'warner', 'atlantic', 'elektra', 'nonesuch',
                'parlophone', 'reprise', 'rhino', 'roadrunner',
                'sire', '300 entertainment', 'asylum', 'nettwerk',
                'fueled by ramen', 'big beat'
            ],
            
            # Top Independent Labels
            'independent': [
                'roc-a-fella', 'death row', 'young money',
                'cold chillin', 'tommy boy', 'ruthless',
                'raw fusion', 'rap-a-lot', 'no limit',
                'cash money', 'bad boy', 'loud records',
                'stax', 'def american', 'death row',
                'stones throw', 'mass appeal', 'fool\'s gold'
            ],
            
            # Historic Labels
            'historic': [
                'okeh', 'vee-jay', 'chess', 'specialty',
                'sun', 'king', 'imperial', 'prestige',
                'brunswick', 'specialty', 'peacock'
            ]
        }
        
        # Create a flat set of all label names for quick lookup
        self.all_labels = {label.lower() for labels in self.major_labels.values() 
                          for label in labels}
        
        # Keep track of new labels found
        self.suggested_labels = set()
        
        # Mapping of label variations
        self.label_variations = {
            'def jam recordings': 'def jam',
            'death row records': 'death row',
            'ruffhouse': 'ruffhouse records',
            'bad boy entertainment': 'bad boy',
            'young money entertainment': 'young money',
            'tommy boy records': 'tommy boy'
        }

    def add_label(self, label_name: str, category: str = 'independent'):
        """Add a new label to the appropriate category."""
        if category in self.major_labels:
            label_name = label_name.lower()
            if label_name not in self.all_labels:
                self.major_labels[category].append(label_name)
                self.all_labels.add(label_name)
                print(f"Added {label_name} to {category} category")
                return True
        return False

    def suggest_label(self, label_name: str):
        """Record a suggested label for future review."""
        label_name = label_name.lower()
        if label_name not in self.all_labels:
            self.suggested_labels.add(label_name)
            print(f"Added {label_name} to suggested labels for review")

    def is_major_label(self, label_name: str) -> bool:
        """Check if a label is recognized as major."""
        # Normalize the label name
        label_name = label_name.lower()
        
        # Check variations first
        if label_name in self.label_variations:
            label_name = self.label_variations[label_name]
        
        # Direct match check
        if label_name in self.all_labels:
            return True
            
        # Partial match check
        for major_label in self.all_labels:
            if major_label in label_name:
                return True
        
        # Record unrecognized labels for review
        self.suggest_label(label_name)
        return False

    def get_label_category(self, label_name: str) -> str:
        """Get the category of a label."""
        label_name = label_name.lower()
        for category, labels in self.major_labels.items():
            if any(label in label_name for label in labels):
                return category
        return "unknown"

    def get_suggested_labels(self) -> set:
        """Get the set of suggested labels for review."""
        return self.suggested_labels

    def clear_suggested_labels(self):
        """Clear the set of suggested labels."""
        self.suggested_labels.clear()