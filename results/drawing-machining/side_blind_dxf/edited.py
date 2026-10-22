# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'x', 'depth': 23.0, 'diameter': 8.5, 'entry': 'positive', 'extent': 'blind', 'kind': 'bore', 'u': 28.0, 'v': 12.0}], 'length': 60.0, 'thickness': 26.0, 'width': 84.0}
SOURCE_SHA256='7cb9ee7a632f143f6fb3d69c52ac50f6c1e56c944e2edb3425bbcd4865e1fbf4'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
