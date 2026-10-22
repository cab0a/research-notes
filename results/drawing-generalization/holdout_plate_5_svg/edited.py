# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 8.0, 'x': 21.93, 'y': 13.0}, {'diameter': 8.6, 'x': 60.97, 'y': 34.5}], 'length': 50.0, 'thickness': 15.0, 'width': 96.0}
OPENING='top'
SOURCE_SHA256='ce9dbf4137d98ff92b1eb23092c215e03b077471e24ddd0608f3fc765c0e4ccc'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
