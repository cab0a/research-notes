# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 80.0, 'length': 60.0, 'thickness': 18.0, 'features': [{'kind': 'counterbore', 'axis': 'z', 'u': 28.0, 'v': 24.0, 'diameter': 6.0, 'counter_diameter': 12.0, 'counter_depth': 5.0, 'entry': 'positive'}]}
SOURCE_SHA256='5ff76fe2f7cdfcd74367c6fad9f89d69c4053b27b61437561df356971939af52'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
