# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.
from research_notes.drawing_machining import export
PARAMETERS={'width': 80.0, 'length': 60.0, 'thickness': 24.0, 'features': [{'kind': 'bore', 'axis': 'x', 'u': 28.0, 'v': 12.0, 'diameter': 8.0, 'extent': 'through'}]}
SOURCE_SHA256='aa6be31d1073f352bf30d1be5c933e4830e925996078bda89e8bd38c36832553'
if __name__=='__main__':
    import sys
    export(PARAMETERS,sys.argv[1])
