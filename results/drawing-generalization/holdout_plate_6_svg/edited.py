# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'holes': [{'diameter': 8.5, 'x': 21.7, 'y': 14.04}, {'diameter': 9.0, 'x': 60.3, 'y': 37.26}, {'diameter': 5.0, 'x': 64.8, 'y': 14.58}], 'length': 54.0, 'thickness': 16.0, 'width': 95.0}
OPENING='top'
SOURCE_SHA256='af520fb78ebb932cfa72f3a2af19b3bac9ce2b53d408385b25a137c6b3f5b4fa'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
