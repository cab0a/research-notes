# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'z', 'counter_depth': 6.0, 'counter_diameter': 12.5, 'diameter': 6.5, 'entry': 'positive', 'kind': 'counterbore', 'u': 28.0, 'v': 24.0}], 'length': 60.0, 'thickness': 20.0, 'width': 84.0}
SOURCE_SHA256='6d12d70ff2cb294e5db0c38ea42fc1a169d4daab2b2d85317d0ca2dfb6a1422f'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
