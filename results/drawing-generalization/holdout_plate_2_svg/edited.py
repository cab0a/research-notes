# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 6.5, 'x': 18.71, 'y': 16.9}, {'diameter': 7.4, 'x': 51.59, 'y': 44.85}], 'length': 65.0, 'thickness': 12.0, 'width': 82.0}
OPENING='top'
SOURCE_SHA256='ae607841abbe0f069407fefa75368da6626e58bb7891e0822469f2e26948a094'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
