# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 80.0, 'length': 60.0, 'thickness': 24.0, 'features': [{'kind': 'bore', 'axis': 'x', 'u': 28.0, 'v': 12.0, 'diameter': 8.0, 'extent': 'blind', 'depth': 22.0, 'entry': 'positive'}]}
SOURCE_SHA256='7cb9ee7a632f143f6fb3d69c52ac50f6c1e56c944e2edb3425bbcd4865e1fbf4'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
