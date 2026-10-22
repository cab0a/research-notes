# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'features': [{'axis': 'z', 'counter_depth': 6.0, 'counter_diameter': 12.5, 'diameter': 6.5, 'entry': 'positive', 'kind': 'counterbore', 'u': 28.0, 'v': 24.0}], 'length': 60.0, 'thickness': 20.0, 'width': 84.0}
SOURCE_SHA256='5ff76fe2f7cdfcd74367c6fad9f89d69c4053b27b61437561df356971939af52'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
