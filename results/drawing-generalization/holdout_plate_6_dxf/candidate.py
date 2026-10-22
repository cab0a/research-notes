# Editable reconstruction recipe, not recovered authoring history.
from research_notes.drawing_generalization import export
FAMILY='plate'
PARAMETERS={'width': 90.0, 'length': 54.0, 'thickness': 14.0, 'holes': [{'x': 20.7, 'y': 14.04, 'diameter': 7.5}, {'x': 60.3, 'y': 37.26, 'diameter': 9.0}, {'x': 64.8, 'y': 14.58, 'diameter': 5.0}]}
OPENING='top'
SOURCE_SHA256='85325f0568c399d52a0119c0ce8ed266bf680a0c65be07026c12ce9a28ec8478'
if __name__=='__main__':
    import sys
    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])
